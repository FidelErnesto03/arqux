/**
 * server/server.ts — cortex-ls: LSP server for CORTEX 1.0 (stdio).
 *
 * ADR-0.3.0 (LSP-DESIGN.md): the language intelligence lives in a
 * dedicated server over JSON-RPC/stdio so any LSP client (VS Code,
 * Neovim, Zed, JetBrains) can reuse it. core.ts holds the pure
 * handlers; this file owns transport, the document store, and the
 * debounced codec validation that feeds publishDiagnostics.
 *
 * SEC: the codec bridge spawns with shell:false + stdin piping — same
 * contract as the extension host side. No network, no telemetry.
 */
import {
  createConnection, ProposedFeatures, TextDocuments,
  InitializeParams, InitializeResult, TextDocumentSyncKind,
  DidChangeConfigurationNotification, FileChangeType,
} from 'vscode-languageserver/node';
import { TextDocument } from 'vscode-languageserver-textdocument';
import { readFileSync } from 'fs';
import { join } from 'path';
import { CodecBridge } from '../codecBridge';
import { parseErrorCatalog } from '../cortexModel';
import * as core from './core';
import { scanCortexFiles, WorkspaceIndex } from './workspaceIndex';

const connection = createConnection(ProposedFeatures.all);
const documents = new TextDocuments(TextDocument);
const bridge = new CodecBridge();
/** 0.4.1: in-memory uri → model index (BLP-004). */
let wsIndex = new WorkspaceIndex([]);

let debounceMs = 250;
const diagTimers = new Map<string, ReturnType<typeof setTimeout>>();

connection.onInitialize((params: InitializeParams): InitializeResult => {
  // workspace index roots (containment for all fs access — H-02)
  wsIndex = new WorkspaceIndex(
    (params.workspaceFolders ?? []).map((f) => f.uri));
  const opts = (params.initializationOptions ?? {}) as {
    toolchainPath?: string;
    debounceMs?: number;
  };
  if (opts.toolchainPath) { bridge.setCustomCommand(opts.toolchainPath); }
  if (typeof opts.debounceMs === 'number' && opts.debounceMs >= 0) {
    debounceMs = opts.debounceMs;
  }
  loadErrorCatalog();

  return {
    capabilities: {
      textDocumentSync: TextDocumentSyncKind.Incremental,
      completionProvider: { triggerCharacters: ['%', '{', ':'] },
      hoverProvider: true,
      documentSymbolProvider: true,
      codeActionProvider: { codeActionKinds: ['quickfix'] },
      documentFormattingProvider: true,
      definitionProvider: true,
      referencesProvider: true,
      renameProvider: { prepareProvider: true },
      semanticTokensProvider: {
        legend: core.SEMANTIC_LEGEND,
        full: true,
      },
      foldingRangeProvider: true,
      inlayHintProvider: { resolveProvider: false },
      codeLensProvider: { resolveProvider: false },
      signatureHelpProvider: { triggerCharacters: ['{', ',', ':'] },
      selectionRangeProvider: true,
      workspaceSymbolProvider: true,
      documentLinkProvider: { resolveProvider: false },
      executeCommandProvider: { commands: ['cortex/validateWorkspace'] },
    },
  };
});

connection.onInitialized(() => {
  void connection.client.register(
    DidChangeConfigurationNotification.type, { section: 'cortex' });
  // Initial corpus scan — contained to workspaceFolders (H-02).
  for (const root of wsIndex.roots) {
    for (const f of scanCortexFiles(root)) {
      if (!wsIndex.get(f.uri)) { wsIndex.set(f.uri, f.text); }
    }
  }
  connection.console.log(
    `cortex-ls: workspace index populated (${wsIndex.size} docs)`);
});

/** File watcher invalidation — same containment as the scan. */
connection.onDidChangeWatchedFiles((params) => {
  for (const ch of params.changes) {
    if (!ch.uri.endsWith('.cortex')) { continue; }
    if (ch.type === FileChangeType.Deleted) {
      wsIndex.delete(ch.uri);
      continue;
    }
    const p = wsIndex.uriToPath(ch.uri);
    if (!p) { continue; }                    // outside roots → skip
    if (documents.get(ch.uri)) { continue; } // open doc is authority
    try {
      wsIndex.set(ch.uri, readFileSync(p, 'utf8'));
    } catch { wsIndex.delete(ch.uri); }
  }
});

connection.onDidChangeConfiguration((change) => {
  const cfg = (change?.settings?.cortex ?? {}) as {
    toolchainPath?: string; debounceMs?: number;
  };
  if (typeof cfg.toolchainPath === 'string') {
    bridge.setCustomCommand(cfg.toolchainPath);
  }
  if (typeof cfg.debounceMs === 'number' && cfg.debounceMs >= 0) {
    debounceMs = cfg.debounceMs;
  }
});

/** Bundled normative catalog → hover for error codes. */
function loadErrorCatalog(): void {
  // out/server/server.js → ../../data/errors-1.0.md (packaged at root)
  for (const p of [
    join(__dirname, '..', '..', 'data', 'errors-1.0.md'),
    join(__dirname, '..', '..', '..', 'data', 'errors-1.0.md'),
  ]) {
    try {
      const parsed = parseErrorCatalog(readFileSync(p, 'utf8'));
      if (parsed.size > 0) { core.setErrorCatalog(parsed); return; }
    } catch { /* try next candidate */ }
  }
}

// Open documents are the index authority — they shadow disk state.
documents.onDidOpen((e) => {
  wsIndex.set(e.document.uri, e.document.getText());
});

documents.onDidChangeContent((change) => {
  const uri = change.document.uri;
  wsIndex.set(uri, change.document.getText());
  const prev = diagTimers.get(uri);
  if (prev) { clearTimeout(prev); }
  diagTimers.set(uri, setTimeout(() => {
    diagTimers.delete(uri);
    void publishDiagnostics(change.document);
  }, debounceMs));
});

documents.onDidClose((e) => {
  diagTimers.delete(e.document.uri);
  void connection.sendDiagnostics({ uri: e.document.uri, diagnostics: [] });
});

async function publishDiagnostics(doc: TextDocument): Promise<void> {
  const res = await bridge.invoke('validate', doc.getText());
  const lineCount = doc.getText().split(/\r?\n/).length;
  const diags = res.exitCode === 0
    ? []
    : core.diagnosticsFromCodec(res.stderr, lineCount);
  void connection.sendDiagnostics({ uri: doc.uri, diagnostics: diags });
}

// ------------------------- request handlers ------------------------------

function docText(uri: string): string | null {
  return documents.get(uri)?.getText() ?? null;
}

connection.onCompletion((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? [] : core.completionItems(text, params.position);
});

connection.onHover((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? null : core.hoverResult(text, params.position);
});

connection.onDocumentSymbol((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? [] : core.documentSymbols(text);
});

connection.onCodeAction((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? []
    : core.codeActions(params.textDocument.uri, text, params.context.diagnostics);
});

connection.onDocumentFormatting(async (params) => {
  const text = docText(params.textDocument.uri);
  if (text === null) { return []; }
  const res = await bridge.invoke('canonicalize', text);
  if (res.exitCode !== 0 || !res.stdout) { return []; }
  return core.formatEdits(text, res.stdout);
});

connection.onDefinition((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? null
    : core.definitionLocation(params.textDocument.uri, text, params.position);
});

connection.onReferences((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? []
    : core.referenceLocations(params.textDocument.uri, text, params.position);
});

connection.onPrepareRename((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? null : core.prepareRenameRange(text, params.position);
});

connection.onRenameRequest((params) => {
  const text = docText(params.textDocument.uri);
  if (text === null) { return { changes: {} }; }
  return core.renameEdits(
    params.textDocument.uri, text, params.position, params.newName);
});

connection.languages.semanticTokens.on((params) => {
  const text = docText(params.textDocument.uri);
  return { data: text === null ? [] : core.semanticTokensData(text) };
});

connection.onFoldingRanges((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? [] : core.foldingRanges(text);
});

// ---------------- 0.4.0-A — info comes to you ----------------

connection.languages.inlayHint.on((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? [] : core.inlayHints(text);
});

connection.onCodeLens((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? []
    : core.codeLenses(params.textDocument.uri, text);
});

connection.onSignatureHelp((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? null
    : core.signatureHelp(text, params.position);
});

connection.onSelectionRanges((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? []
    : core.selectionRanges(text, params.positions);
});

// ---------------- 0.4.1 — workspace intelligence ----------------

connection.onWorkspaceSymbol((params) =>
  core.workspaceSymbols(wsIndex, params.query));

connection.onDocumentLinks((params) => {
  const text = docText(params.textDocument.uri);
  return text === null ? [] : core.documentLinks(text);
});

const VALIDATE_WS_MAX = 200;
const VALIDATE_WS_BUDGET_MS = 30_000;

connection.onExecuteCommand(async (params) => {
  if (params.command !== 'cortex/validateWorkspace') {
    return { results: [] };
  }
  const started = Date.now();
  const results: { uri: string; diagnostics: ReturnType<
    typeof core.diagnosticsFromCodec> }[] = [];
  let n = 0;
  for (const uri of wsIndex.uris()) {
    if (n++ >= VALIDATE_WS_MAX || Date.now() - started > VALIDATE_WS_BUDGET_MS) {
      break;
    }
    const text = wsIndex.text(uri);
    if (text === undefined) { continue; }
    const res = await bridge.invoke('validate', text);
    const diags = res.exitCode === 0
      ? []
      : core.diagnosticsFromCodec(
          res.stderr, text.split(/\r?\n/).length);
    if (diags.length) { results.push({ uri, diagnostics: diags }); }
  }
  return { results, truncated: n >= VALIDATE_WS_MAX };
});

documents.listen(connection);
connection.listen();
