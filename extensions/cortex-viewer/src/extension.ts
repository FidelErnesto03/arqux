/**
 * extension.ts — lifecycle and orchestration for arqux-cortex-viewer.
 *
 * Wiring: document changes (debounced 250ms, UI-01) → bridge.inspect()
 * (validate + to-hcortex + hash + loss-report in parallel) → diagnostics
 * + status bar + preview panel. Preview edits flow back through the
 * SEC-06 gate: from-hcortex → validate → loss-report, abort on loss.
 */
import * as vscode from 'vscode';
import * as path from 'path';
import {
  ExecuteCommandRequest, LanguageClient, LanguageClientOptions,
  ServerOptions, TransportKind,
} from 'vscode-languageclient/node';
import { CodecBridge, INSTALL_HINT, parseHash, parseLossReport } from './codecBridge';
import { lineOfSection, parseCodecErrors, sectionAtLine } from './diagnostics';
import { sigilTokenAt } from './cortexModel';
import { inlineDecorationOptions } from './server/core';
import { PreviewPanel } from './previewPanel';
import { renderHcortexBody } from './webviewKit';

function debounceMs(): number {
  return vscode.workspace.getConfiguration('cortex')
    .get<number>('debounceMs', 250);
}

let bridge: CodecBridge;
let statusBar: vscode.StatusBarItem;
let installNotified = false;
/** cortex-ls client — owns language intelligence since 0.3.0. */
let lspClient: LanguageClient | undefined;
/** The document whose HCORTEX the preview is showing right now. */
let previewedDoc: vscode.TextDocument | undefined;
const debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();
/** Last inspect() badges — surfaced by cortex.statusMenu quickpick. */
let lastBadges: {
  valid: boolean; hashShort: string; hashFull: string;
  lossCount: number; runtime: string;
} | undefined;

// ---- 0.4.0-A: inline diagnostics (Error Lens style, client-side) ----
const decoError = vscode.window.createTextEditorDecorationType({
  after: { margin: '0 0 0 2em', color: '#f14c4c', fontStyle: 'italic' },
});
const decoWarning = vscode.window.createTextEditorDecorationType({
  after: { margin: '0 0 0 2em', color: '#cca700', fontStyle: 'italic' },
});

function inlineDiagnosticsEnabled(): boolean {
  return vscode.workspace.getConfiguration('cortex')
    .get<boolean>('inlineDiagnostics', true);
}

/** Apply EOL decorations from the LS-published diagnostics (filtered). */
function applyInlineDecorations(): void {
  const enabled = inlineDiagnosticsEnabled();
  for (const editor of vscode.window.visibleTextEditors) {
    if (editor.document.languageId !== 'cortex'
        || editor.document.uri.scheme !== 'file') { continue; }
    if (!enabled) {
      editor.setDecorations(decoError, []);
      editor.setDecorations(decoWarning, []);
      continue;
    }
    const diags = vscode.languages.getDiagnostics(editor.document.uri);
    const errors: vscode.DecorationOptions[] = [];
    const warnings: vscode.DecorationOptions[] = [];
    for (const spec of inlineDecorationOptions(diags)) {
      if (spec.line >= editor.document.lineCount) { continue; }
      const eol = editor.document.lineAt(spec.line).range.end;
      const opt: vscode.DecorationOptions = {
        range: new vscode.Range(eol, eol),
        renderOptions: {
          after: { contentText: `  ◈ ${spec.message}` },
        },
      };
      (spec.severity === 'error' ? errors : warnings).push(opt);
    }
    editor.setDecorations(decoError, errors);
    editor.setDecorations(decoWarning, warnings);
  }
}

// ---- 0.4.1: workspace-wide validation (BLP-004) ----
const wsDiagCollection =
  vscode.languages.createDiagnosticCollection('cortex-workspace');
let wsOutput: vscode.OutputChannel | undefined;

/**
 * cortex.validateWorkspace — asks cortex-ls to validate every indexed
 * .cortex (open docs shadow disk) and aggregates results into Problems
 * + an output report.
 */
async function validateWorkspace(): Promise<void> {
  if (!lspClient) {
    void vscode.window.showWarningMessage('cortex-ls no está activo.');
    return;
  }
  wsOutput ??= vscode.window.createOutputChannel('CORTEX Workspace');
  wsOutput.clear();
  wsOutput.appendLine('cortex.validateWorkspace — validando corpus…');
  const res = await lspClient.sendRequest(ExecuteCommandRequest.type, {
    command: 'cortex/validateWorkspace', arguments: [],
  }) as {
    results: { uri: string; diagnostics: unknown[] }[];
    truncated?: boolean;
  };
  wsDiagCollection.clear();
  let total = 0;
  for (const r of res.results ?? []) {
    const diags = (r.diagnostics as Parameters<
      typeof lspClient.protocol2CodeConverter.asDiagnostic>[0][])
      .map((d) => lspClient!.protocol2CodeConverter.asDiagnostic(d));
    wsDiagCollection.set(vscode.Uri.parse(r.uri), diags);
    total += diags.length;
    wsOutput.appendLine(`${vscode.Uri.parse(r.uri).fsPath}: ${diags.length}`);
    for (const d of diags) {
      wsOutput.appendLine(
        `  L${d.range.start.line + 1}: ${d.message}`);
    }
  }
  wsOutput.appendLine(
    `— ${res.results?.length ?? 0} doc(s) con problemas, ${total} total` +
    (res.truncated ? ' (TRUNCADO a 200 docs)' : ''));
  wsOutput.show(true);
  void vscode.window.showInformationMessage(
    `CORTEX workspace: ${total} problema(s) en ` +
    `${res.results?.length ?? 0} documento(s).`);
}

/** cortex.statusMenu — enriched status bar quickpick. */
async function statusMenu(): Promise<void> {
  const diags = vscode.window.activeTextEditor
    ? vscode.languages.getDiagnostics(vscode.window.activeTextEditor.document.uri)
    : [];
  const codecDiags = diags.filter((d) => d.source === 'codec-cortex');
  const items: vscode.QuickPickItem[] = [
    {
      label: `$(error) Diagnósticos: ${codecDiags.length}`,
      description: codecDiags.length
        ? codecDiags[0].message.slice(0, 60) : 'sin errores',
    },
    {
      label: `$(server) Runtime: ${lastBadges?.runtime ?? 'desconocido'}`,
      description: 'cadena de resolución del toolchain',
    },
    {
      label: `$(key) Hash: ${lastBadges?.hashFull ?? '—'}`,
      description: 'sha256 C14N completo',
    },
    { label: '', kind: vscode.QuickPickItemKind.Separator },
    {
      label: '$(gear) Configurar toolchainPath…',
      description: 'abre Settings (cortex.toolchainPath)',
      alwaysShow: true,
    },
    {
      label: `$(eye) Inline diagnostics: ${inlineDiagnosticsEnabled() ? 'on' : 'off'}`,
      description: 'toggle cortex.inlineDiagnostics',
      alwaysShow: true,
    },
  ];
  const pick = await vscode.window.showQuickPick(items, {
    placeHolder: 'CORTEX — estado del documento',
  });
  if (!pick) { return; }
  if (pick.label.includes('toolchainPath')) {
    void vscode.commands.executeCommand(
      'workbench.action.openSettings', 'cortex.toolchainPath');
  } else if (pick.label.includes('Inline diagnostics')) {
    const cfg = vscode.workspace.getConfiguration('cortex');
    void cfg.update('inlineDiagnostics',
      !inlineDiagnosticsEnabled(), vscode.ConfigurationTarget.Global);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  bridge = new CodecBridge();
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  context.subscriptions.push(statusBar);

  applySettings();
  startLanguageServer(context);

  context.subscriptions.push(
    vscode.commands.registerCommand('cortex.openPreview', () =>
      openPreview(vscode.ViewColumn.Active, context.extensionUri)),
    vscode.commands.registerCommand('cortex.openPreviewToSide', () =>
      openPreview(vscode.ViewColumn.Beside, context.extensionUri)),
    vscode.commands.registerCommand('cortex.verifyHash', verifyHash),
    vscode.commands.registerCommand('cortex.applyHumanEdit', applyHumanEditCommand),
    vscode.commands.registerCommand('cortex.exportPreview', exportPreview),
    vscode.commands.registerCommand('cortex.statusMenu', statusMenu),
    vscode.commands.registerCommand(
      'cortex.validateWorkspace', validateWorkspace),
    decoError, decoWarning, wsDiagCollection,
  );
  statusBar.command = 'cortex.statusMenu';

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.languageId !== 'cortex') { return; }
      scheduleRefresh(e.document, context.extensionUri);
    }),
    vscode.window.onDidChangeTextEditorSelection((e) => {
      if (e.textEditor.document.languageId !== 'cortex') { return; }
      const text = e.textEditor.document.getText();
      const line = e.selections[0].active.line;
      const col = e.selections[0].active.character;
      const sec = sectionAtLine(text, line);
      if (sec) { PreviewPanel.instance?.scrollToSection(sec); }
      const sigTok = sigilTokenAt(text, line, col);
      PreviewPanel.instance?.setActive(sec ?? '', sigTok?.token ?? '');
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (doc.languageId === 'cortex') {
        debounceTimers.delete(doc.uri.toString());
      }
    }),
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor?.document.languageId === 'cortex') {
        scheduleRefresh(editor.document, context.extensionUri, 0);
      }
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('cortex')) { applySettings(); }
      if (e.affectsConfiguration('cortex.inlineDiagnostics')) {
        applyInlineDecorations();
      }
    }),
    vscode.languages.onDidChangeDiagnostics(() => applyInlineDecorations()),
    vscode.window.onDidChangeVisibleTextEditors(() => applyInlineDecorations()),
    vscode.workspace.onWillSaveTextDocument((e) => {
      if (e.document.languageId !== 'cortex') { return; }
      const on = vscode.workspace.getConfiguration('cortex')
        .get<boolean>('formatOnSave', false);
      if (on) { e.waitUntil(canonicalizeEdits(e.document)); }
    }),
  );

  const editor = vscode.window.activeTextEditor;
  if (editor?.document.languageId === 'cortex') {
    scheduleRefresh(editor.document, context.extensionUri, 0);
  }
}

export function deactivate(): Promise<void> | undefined {
  for (const t of debounceTimers.values()) { clearTimeout(t); }
  debounceTimers.clear();
  PreviewPanel.instance?.dispose();
  return lspClient?.stop();
}

/**
 * cortex-ls (ADR-0.3.0): all language intelligence runs in the server —
 * diagnostics, completion, hover, symbols, formatting, quick fixes,
 * definition, references, rename, semantic tokens and folding.
 */
function startLanguageServer(context: vscode.ExtensionContext): void {
  const serverModule = context.asAbsolutePath(
    path.join('out', 'server', 'server.js'));
  const serverOptions: ServerOptions = {
    run: {
      module: serverModule,
      transport: TransportKind.stdio,
      args: ['--stdio'],
    },
    debug: {
      module: serverModule,
      transport: TransportKind.stdio,
      args: ['--stdio'],
      options: { execArgv: ['--nolazy', '--inspect=6009'] },
    },
  };
  const cfg = vscode.workspace.getConfiguration('cortex');
  const clientOptions: LanguageClientOptions = {
    documentSelector: [{ language: 'cortex', scheme: 'file' }],
    synchronize: {
      configurationSection: 'cortex',
      // 0.4.1: feeds didChangeWatchedFiles → workspace index invalidation
      fileEvents: vscode.workspace.createFileSystemWatcher('**/*.cortex'),
    },
    initializationOptions: {
      toolchainPath: cfg.get<string>('toolchainPath', ''),
      debounceMs: cfg.get<number>('debounceMs', 250),
    },
  };
  lspClient = new LanguageClient(
    'cortex-ls', 'CORTEX Language Server',
    serverOptions, clientOptions);
  context.subscriptions.push({ dispose: () => { void lspClient?.stop(); } });
  void lspClient.start();
}

function applySettings(): void {
  const cfg = vscode.workspace.getConfiguration('cortex');
  bridge.setCustomCommand(cfg.get<string>('toolchainPath', ''));
}

/** Format Document + format-on-save: canonical bytes from the codec. */
async function canonicalizeEdits(doc: vscode.TextDocument): Promise<vscode.TextEdit[]> {
  const res = await bridge.invoke('canonicalize', doc.getText());
  if (res.exitCode !== 0 || !res.stdout) { return []; }
  const out = res.stdout.endsWith('\n') ? res.stdout : res.stdout + '\n';
  if (out === doc.getText()) { return []; }
  const last = doc.lineAt(doc.lineCount - 1);
  return [vscode.TextEdit.replace(
    new vscode.Range(new vscode.Position(0, 0), last.range.end), out)];
}

function scheduleRefresh(
  doc: vscode.TextDocument,
  extensionUri: vscode.Uri,
  delay = debounceMs()
): void {
  const key = doc.uri.toString();
  const prev = debounceTimers.get(key);
  if (prev) { clearTimeout(prev); }
  debounceTimers.set(key, setTimeout(() => {
    debounceTimers.delete(key);
    void refreshDocument(doc, extensionUri);
  }, delay));
}

async function refreshDocument(
  doc: vscode.TextDocument,
  extensionUri: vscode.Uri
): Promise<void> {
  const text = doc.getText();
  const result = await bridge.inspect(text);

  // State badge (validate is the authority); diagnostics now come from
  // cortex-ls via publishDiagnostics — no local collection.
  const codecDiags = parseCodecErrors(result.validate.stderr);
  const valid = result.validate.exitCode === 0;

  const hash = parseHash(result.hash.stdout);
  const loss = parseLossReport(result.loss.stdout);
  const lossCount = loss?.losses.length ?? (result.loss.ok ? 0 : -1);
  const runtime = await bridge.activeRuntime();
  if (!runtime && !installNotified) {
    installNotified = true;
    void vscode.window.showWarningMessage(
      `CORTEX toolchain no encontrado. Instala con: ${INSTALL_HINT}`
    );
  }

  const badges = {
    valid,
    canon: 'C14N-1.0',
    hashShort: hash ? `${hash.slice(0, 12)}…` : '—',
    hashFull: hash ?? '',
    lossCount,
    runtime: runtime ?? 'none',
  };
  lastBadges = badges;

  statusBar.text = valid
    ? `$(pass) CORTEX ${badges.hashShort}`
    : `$(error) CORTEX ${codecDiags.length} error(s)`;
  statusBar.tooltip = `Runtime: ${badges.runtime} · Canon: C14N-1.0`;
  statusBar.show();

  const panel = PreviewPanel.instance;
  if (panel) {
    previewedDoc = doc;
    panel.setDocumentTitle(doc.fileName);
    panel.update({
      bodyHtml: result.hcortex.ok
        ? renderHcortexBody(result.hcortex.stdout)
        : `<p class="hc-error">${escapeHtml(result.hcortex.stderr || 'to-hcortex failed')}</p>`,
      hcortex: result.hcortex.stdout,
      badges,
    });
  }
}

function openPreview(column: vscode.ViewColumn, extensionUri: vscode.Uri): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'cortex') {
    void vscode.window.showInformationMessage('Abre un documento .cortex primero.');
    return;
  }
  PreviewPanel.createOrShow(extensionUri, editor.document, column, {
    onCopyHash: (hash) => {
      if (hash) { void vscode.env.clipboard.writeText(hash); }
    },
    onRevealSection: (sectionId) => {
      // Resolve against the doc the preview is showing NOW, not the
      // editor captured at createOrShow — the user may have switched.
      const doc = previewedDoc ?? editor.document;
      const target =
        vscode.window.visibleTextEditors.find((e) => e.document === doc)
        ?? vscode.window.activeTextEditor;
      if (!target) { return; }
      const line = lineOfSection(doc.getText(), sectionId);
      if (line >= 0) {
        const pos = new vscode.Position(line, 0);
        target.selection = new vscode.Selection(pos, pos);
        target.revealRange(
          new vscode.Range(pos, pos),
          vscode.TextEditorRevealType.AtTop
        );
      }
    },
    onApplyHcortexEdit: (newHcortex) => {
      void applyHcortexEdit(
        previewedDoc ?? editor.document, newHcortex, extensionUri);
    },
  });
  scheduleRefresh(editor.document, extensionUri, 0);
}

/** cortex.verifyHash — compare doc's canonical hash with user input. */
async function verifyHash(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'cortex') { return; }
  const expected = await vscode.window.showInputBox({
    prompt: 'SHA-256 esperado (con o sin prefijo sha256:)',
    placeHolder: 'sha256:…',
  });
  if (expected === undefined) { return; }
  const res = await bridge.invoke('hash', editor.document.getText());
  const actual = parseHash(res.stdout);
  const want = expected.trim().replace(/^sha256:/i, '').toLowerCase();
  if (!actual) {
    void vscode.window.showErrorMessage(`No se pudo calcular el hash: ${res.stderr || res.infraError}`);
    return;
  }
  if (actual === want) {
    void vscode.window.showInformationMessage(`✓ Hash coincide: sha256:${actual.slice(0, 16)}…`);
  } else {
    void vscode.window.showWarningMessage(
      `✗ Hash difiere. Esperado ${want.slice(0, 16)}…, actual sha256:${actual.slice(0, 16)}…`
    );
  }
}

/** cortex.exportPreview — save the live HCORTEX render as .md or .html. */
async function exportPreview(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'cortex') {
    void vscode.window.showInformationMessage('Abre un documento .cortex primero.');
    return;
  }
  const res = await bridge.invoke('to-hcortex', editor.document.getText());
  if (res.exitCode !== 0 || !res.stdout) {
    void vscode.window.showErrorMessage(
      `to-hcortex falló: ${res.stderr.trim() || res.infraError || 'exit ' + res.exitCode}`);
    return;
  }
  const base = editor.document.uri.fsPath.replace(/\.cortex$/i, '');
  const uri = await vscode.window.showSaveDialog({
    defaultUri: vscode.Uri.file(`${base}.hcortex.md`),
    filters: { 'HCORTEX': ['md', 'html'] },
    saveLabel: 'Exportar preview',
  });
  if (!uri) { return; }

  const content = uri.fsPath.endsWith('.html')
    ? `<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">` +
      `<title>${escapeHtml(editor.document.fileName)}</title>` +
      `<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2em auto;padding:0 1em}` +
      `table{border-collapse:collapse}td,th{border:1px solid #999;padding:4px 8px}` +
      `.badge{display:inline-block;padding:2px 8px;border-radius:10px;background:#444;color:#fff;font-size:.8em}</style>` +
      `</head><body>\n<!-- HCORTEX source (tags preserved):\n${res.stdout.replace(/-->/g, '--\\>')}\n-->\n` +
      `${renderHcortexBody(res.stdout)}</body></html>`
    : res.stdout;
  await vscode.workspace.fs.writeFile(uri, Buffer.from(content, 'utf8'));
  void vscode.window.showInformationMessage(`Preview exportada → ${uri.fsPath}`);
}

/** Command entry point: compile the preview's current HCORTEX back. */
async function applyHumanEditCommand(): Promise<void> {
  const panel = PreviewPanel.instance;
  if (!panel) {
    void vscode.window.showInformationMessage(
      'Sin preview activa: edita una tabla HCORTEX en la vista previa.'
    );
    return;
  }
  void vscode.window.showInformationMessage(
    'Edita una celda de tabla en la preview; el cambio se aplica vía from-hcortex + loss-report.'
  );
}

/**
 * SEC-06 gate: HCORTEX → CORTEX → validate → loss-report.
 * Aborts the write when exit != 0 or loss_count > 0, surfacing the
 * exact diagnostic in the preview.
 */
async function applyHcortexEdit(
  doc: vscode.TextDocument,
  newHcortex: string,
  extensionUri: vscode.Uri
): Promise<void> {
  const panel = PreviewPanel.instance;

  const compiled = await bridge.invoke('from-hcortex', newHcortex);
  if (compiled.exitCode !== 0) {
    const detail = compiled.stderr.trim() || compiled.infraError || 'from-hcortex failed';
    panel?.reportEditResult(false, `from-hcortex: ${detail}`);
    return;
  }
  const newCortex = compiled.stdout;

  const validation = await bridge.invoke('validate', newCortex);
  if (validation.exitCode !== 0) {
    panel?.reportEditResult(false, `validate: ${validation.stderr.trim()}`);
    return;
  }

  const lossRes = await bridge.invoke('loss-report', newCortex);
  const loss = parseLossReport(lossRes.stdout);
  if (lossRes.exitCode !== 0 || !loss) {
    panel?.reportEditResult(false, `loss-report: ${lossRes.stderr.trim() || 'unparseable report'}`);
    return;
  }
  if (loss.losses.length > 0 || !loss.reversible) {
    panel?.reportEditResult(
      false,
      `Edición abortada: ${loss.losses.length} pérdida(s) declarada(s) — ${JSON.stringify(loss.losses)}`
    );
    return;
  }

  const edit = new vscode.WorkspaceEdit();
  const lastLine = doc.lineAt(doc.lineCount - 1);
  edit.replace(
    doc.uri,
    new vscode.Range(new vscode.Position(0, 0), lastLine.range.end),
    newCortex.endsWith('\n') ? newCortex : `${newCortex}\n`
  );
  const applied = await vscode.workspace.applyEdit(edit);
  if (applied) {
    panel?.reportEditResult(true, 'Edición aplicada — 0 pérdidas.');
    scheduleRefresh(doc, extensionUri, 0);
  } else {
    panel?.reportEditResult(false, 'WorkspaceEdit rechazado por VS Code.');
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
