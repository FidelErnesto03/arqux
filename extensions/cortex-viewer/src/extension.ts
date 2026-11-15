/**
 * extension.ts — lifecycle and orchestration for arqux-cortex-viewer.
 *
 * Wiring: document changes (debounced 250ms, UI-01) → bridge.inspect()
 * (validate + to-hcortex + hash + loss-report in parallel) → diagnostics
 * + status bar + preview panel. Preview edits flow back through the
 * SEC-06 gate: from-hcortex → validate → loss-report, abort on loss.
 */
import * as vscode from 'vscode';
import { CodecBridge, INSTALL_HINT, parseHash, parseLossReport } from './codecBridge';
import { CodecDiagnostic, lineOfSection, parseCodecErrors, sectionAtLine } from './diagnostics';
import { PreviewPanel } from './previewPanel';
import { registerProviders } from './providers';
import { renderHcortexBody } from './webviewKit';

function debounceMs(): number {
  return vscode.workspace.getConfiguration('cortex')
    .get<number>('debounceMs', 250);
}

let bridge: CodecBridge;
let diagnostics: vscode.DiagnosticCollection;
let statusBar: vscode.StatusBarItem;
let installNotified = false;
/** The document whose HCORTEX the preview is showing right now. */
let previewedDoc: vscode.TextDocument | undefined;
const debounceTimers = new Map<string, ReturnType<typeof setTimeout>>();

export function activate(context: vscode.ExtensionContext): void {
  bridge = new CodecBridge();
  diagnostics = vscode.languages.createDiagnosticCollection('cortex');
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  context.subscriptions.push(diagnostics, statusBar);

  applySettings();
  registerProviders(context, bridge);

  context.subscriptions.push(
    vscode.commands.registerCommand('cortex.openPreview', () =>
      openPreview(vscode.ViewColumn.Active, context.extensionUri)),
    vscode.commands.registerCommand('cortex.openPreviewToSide', () =>
      openPreview(vscode.ViewColumn.Beside, context.extensionUri)),
    vscode.commands.registerCommand('cortex.verifyHash', verifyHash),
    vscode.commands.registerCommand('cortex.applyHumanEdit', applyHumanEditCommand),
    vscode.commands.registerCommand('cortex.exportPreview', exportPreview),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.languageId !== 'cortex') { return; }
      scheduleRefresh(e.document, context.extensionUri);
    }),
    vscode.window.onDidChangeTextEditorSelection((e) => {
      if (e.textEditor.document.languageId !== 'cortex') { return; }
      const sec = sectionAtLine(
        e.textEditor.document.getText(),
        e.selections[0].active.line
      );
      if (sec) { PreviewPanel.instance?.scrollToSection(sec); }
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      if (doc.languageId === 'cortex') {
        diagnostics.delete(doc.uri);
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
    }),
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

export function deactivate(): void {
  for (const t of debounceTimers.values()) { clearTimeout(t); }
  debounceTimers.clear();
  PreviewPanel.instance?.dispose();
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

  // Diagnostics + state badge (validate is the authority).
  const codecDiags = parseCodecErrors(result.validate.stderr);
  const valid = result.validate.exitCode === 0;
  diagnostics.set(doc.uri, codecDiags.map((d) => toVscodeDiagnostic(d, doc)));

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

function toVscodeDiagnostic(d: CodecDiagnostic, doc: vscode.TextDocument): vscode.Diagnostic {
  const maxLine = doc.lineCount - 1;
  const line = Math.min(d.line, Math.max(0, maxLine));
  const range = new vscode.Range(
    new vscode.Position(line, d.col),
    new vscode.Position(line, d.col + 1)
  );
  const diag = new vscode.Diagnostic(
    range,
    d.message,
    d.severity === 'warning'
      ? vscode.DiagnosticSeverity.Warning
      : vscode.DiagnosticSeverity.Error
  );
  diag.source = 'codec-cortex';
  diag.code = d.code;
  return diag;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
