/**
 * server/core.ts — transport-free LSP handlers for CORTEX 1.0.
 *
 * Every function is pure: it takes document text + LSP params and
 * returns LSP types. server.ts binds them to the connection; tests
 * exercise them directly without a JSON-RPC transport.
 *
 * The codec stays the authority on validity — cortexModel mirrors the
 * declared surface; diagnostics come from `validate` via the bridge.
 */
import {
  CodeAction, CodeActionKind, CompletionItem, CompletionItemKind,
  Diagnostic, DiagnosticSeverity, DocumentSymbol, FoldingRange,
  FoldingRangeKind, InsertTextFormat, Location, Position, Range,
  SymbolKind, TextEdit, WorkspaceEdit,
} from 'vscode-languageserver-types';
import {
  buildSigilDecl, collectSemanticTokens, errorCodeAt, findSigilRefs,
  formatDeclText, glossaryInsertLine, parseAttrs, parseDoc,
  sectionFoldRanges, sigilTokenAt, TOKEN_MODIFIERS, TOKEN_TYPES,
} from '../cortexModel';
import { parseCodecErrors } from '../diagnostics';

/** Legend shared between server capability and semanticTokensData(). */
export const SEMANTIC_LEGEND = {
  tokenTypes: [...TOKEN_TYPES],
  tokenModifiers: [...TOKEN_MODIFIERS],
};

// ------------------------------ diagnostics ------------------------------

/** codec stderr → publishDiagnostics payload (severity/source/code). */
export function diagnosticsFromCodec(stderr: string, lineCount: number): Diagnostic[] {
  return parseCodecErrors(stderr).map((d) => {
    const line = Math.min(d.line, Math.max(0, lineCount - 1));
    return Diagnostic.create(
      Range.create(
        Position.create(line, d.col),
        Position.create(line, d.col + 1)),
      d.message,
      d.severity === 'warning' ? DiagnosticSeverity.Warning : DiagnosticSeverity.Error,
      d.code,
      'codec-cortex');
  });
}

// ------------------------------ completion -------------------------------

export function completionItems(text: string, pos: Position): CompletionItem[] {
  const model = parseDoc(text);
  const line = text.split(/\r?\n/)[pos.line] ?? '';
  const before = line.slice(0, pos.character);
  const items: CompletionItem[] = [];

  // % → enum values
  if (before.endsWith('%')) {
    for (const e of model.enums) {
      for (const v of e.values) {
        items.push({
          label: v,
          kind: CompletionItemKind.EnumMember,
          detail: `enum ${e.name}`,
        });
      }
    }
    return items;
  }

  // Inside {…} → contract attr keys
  const openBrace = before.lastIndexOf('{');
  const closeBrace = before.lastIndexOf('}');
  if (openBrace > closeBrace) {
    const head = line.slice(0, openBrace);
    const m = /([A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*)\s*$/.exec(head);
    const decl = m ? model.sigilByInst.get(m[1]) : undefined;
    const keys = decl?.fields.length ? decl.fields : ['type', 'weight', 'focus', 'desc', 'fields'];
    for (const k of keys) {
      items.push({
        label: k,
        kind: CompletionItemKind.Field,
        insertText: `${k}:"$1"`,
        insertTextFormat: InsertTextFormat.Snippet,
        detail: decl ? `field of ${m![1]}` : 'contract attr',
      });
    }
    return items;
  }

  // Line start / after $ → declarations + sigil usages
  if (/^\s*[A-Z]*$/.test(before) || before.endsWith('$')) {
    for (const s of model.sigils) {
      items.push({
        label: `${s.sigil}:${s.inst}`,
        kind: CompletionItemKind.Class,
        detail: s.attrs.desc ?? 'declared sigil',
        insertText:
          `${s.sigil}:${s.inst}{${s.fields.map((f, i) => `${f}:"\${${i + 1}:${f}}"`) .join(',')}}`,
        insertTextFormat: InsertTextFormat.Snippet,
      });
    }
    items.push({
      label: 'new section',
      kind: CompletionItemKind.Snippet,
      insertText: '\\$${1:2}: ${2:TITLE}',
      insertTextFormat: InsertTextFormat.Snippet,
      detail: 'CORTEX section header',
    });
  }
  return items;
}

// --------------------------------- hover ---------------------------------

let errorCatalog: Map<string, string[]> = new Map();
export function setErrorCatalog(catalog: Map<string, string[]>): void {
  errorCatalog = catalog;
}

export function hoverResult(
  text: string,
  pos: Position
): { contents: { kind: 'markdown'; value: string }; range?: Range } | null {
  const sigTok = sigilTokenAt(text, pos.line, pos.character);
  if (sigTok) {
    const model = parseDoc(text);
    const [sigil] = sigTok.token.split(':');
    const decl = model.sigilByInst.get(sigTok.token)
      ?? model.sigils.find((s) => s.sigil === sigil);
    const range = Range.create(
      pos.line, sigTok.start, pos.line, sigTok.end);
    if (decl) {
      const exact = model.sigilByInst.has(sigTok.token);
      let md = exact
        ? `**${sigTok.token}** — sigilo declarado\n\n`
        : `**${sigTok.token}** — instancia no declarada (contrato de \`${decl.sigil}:${decl.inst}\`)\n\n`;
      md += '| attr | value |\n|---|---|\n';
      for (const [k, v] of Object.entries(decl.attrs)) {
        md += `| ${k} | \`${v}\` |\n`;
      }
      if (decl.fields.length) {
        md += `\nFields: ${decl.fields.map((f) => `\`${f}\``).join(' ')}`;
      }
      md += `\n\n_glosario, línea ${decl.line + 1}_`;
      return { contents: { kind: 'markdown', value: md }, range };
    }
    // Inline attrs fallback (AXM:x{...} inside a section, no glossary decl)
    const lineText = text.split(/\r?\n/)[pos.line] ?? '';
    const brace = /\{([\s\S]*)\}\s*$/.exec(lineText);
    const inline = brace ? parseAttrs(brace[1]) : {};
    if (Object.keys(inline).length > 0) {
      let md = `**${sigTok.token}** — instancia inline (sin decl en glosario)\n\n`;
      md += '| attr | value |\n|---|---|\n';
      for (const [k, v] of Object.entries(inline)) {
        md += `| ${k} | \`${v}\` |\n`;
      }
      return { contents: { kind: 'markdown', value: md }, range };
    }
    return {
      contents: {
        kind: 'markdown',
        value: `**${sigTok.token}** — ⚠ sigilo sin declaración en el glosario`,
      },
      range,
    };
  }

  const codeTok = errorCodeAt(text, pos.line, pos.character);
  if (codeTok && errorCatalog.has(codeTok.code)) {
    const emitters = errorCatalog.get(codeTok.code)!;
    return {
      contents: {
        kind: 'markdown',
        value: `**${codeTok.code}** — catálogo CORTEX 1.0\n\nEmitido por: ${emitters.join(', ')}`,
      },
      range: Range.create(pos.line, codeTok.start, pos.line, codeTok.end),
    };
  }

  const lineText = text.split(/\r?\n/)[pos.line] ?? '';
  const sec = /^\$(\d+(?:\.\d+)?)\s*:/.exec(lineText);
  if (sec && pos.character <= sec[0].length) {
    return {
      contents: { kind: 'markdown', value: `Sección §${sec[1]} — CORTEX 1.0` },
    };
  }
  return null;
}

// -------------------------------- symbols --------------------------------

export function documentSymbols(text: string): DocumentSymbol[] {
  const model = parseDoc(text);
  const lines = text.split(/\r?\n/);
  const out: DocumentSymbol[] = [];

  if (model.kernelLine >= 0 || model.formatLine >= 0) {
    const start = model.kernelLine >= 0 ? model.kernelLine : 0;
    const end = model.firstSectionLine >= 0
      ? model.firstSectionLine - 1
      : lines.length - 1;
    const kernel: DocumentSymbol = {
      name: '$0 KERNEL + glosario',
      detail: '',
      kind: SymbolKind.Namespace,
      range: Range.create(start, 0, Math.max(start, end), 0),
      selectionRange: Range.create(start, 0, start, 10),
      children: model.sigils.map((s) => ({
        name: `${s.sigil}:${s.inst}`,
        detail: s.attrs.type ?? '',
        kind: SymbolKind.Interface,
        range: Range.create(s.line, 0, s.line, (lines[s.line] ?? '').length),
        selectionRange: Range.create(s.line, 0, s.line, s.sigil.length + 1 + s.inst.length),
      })),
    };
    out.push(kernel);
  }

  for (const sec of model.sections) {
    const nextSec = model.sections.find(
      (s) => s.line > sec.line && !s.id.startsWith(sec.id + '.'));
    const end = (nextSec ? nextSec.line : lines.length) - 1;
    out.push({
      name: `§${sec.id} ${sec.title}`.trim(),
      detail: sec.capa,
      kind: SymbolKind.Module,
      range: Range.create(sec.line, 0, end, 0),
      selectionRange: Range.create(sec.line, 0, sec.line, (lines[sec.line] ?? '').length),
    });
  }
  return out;
}

// ------------------------------ quick fixes ------------------------------

export function codeActions(
  uri: string,
  text: string,
  diagnostics: Diagnostic[]
): CodeAction[] {
  const actions: CodeAction[] = [];
  const lines = text.split(/\r?\n/);
  const model = parseDoc(text);

  for (const diag of diagnostics) {
    if (diag.source !== 'codec-cortex') { continue; }
    const code = String(diag.code ?? '');

    // Undeclared sigil → declare it in the glossary
    const sigMatch = /Undeclared sigil:\s*([A-Z][A-Z0-9_]*)/.exec(diag.message);
    if (code.startsWith('I001') && sigMatch) {
      const usageLine = lines[diag.range.start.line] ?? '';
      const inst = /([A-Z][A-Z0-9_]*):([A-Za-z_][\w-]*)/.exec(usageLine);
      const declLine = inst
        ? buildSigilDecl(inst[1], inst[2])
        : `${sigMatch[1]}:item{type:attrs,weight:M,focus:name,desc:"TODO",fields:"name:text"}`;
      const at = glossaryInsertLine(model, lines.length);
      const action = CodeAction.create(
        `Declarar ${inst ? inst[0] : sigMatch[1]} en el glosario`,
        { changes: { [uri]: [TextEdit.insert(Position.create(at, 0), declLine + '\n')] } },
        CodeActionKind.QuickFix);
      action.diagnostics = [diag];
      action.isPreferred = true;
      actions.push(action);
    }

    // Missing $0:format → insert it
    if (/FORMAT_REQUIRED|G005|G010/.test(code)) {
      const at = model.kernelLine >= 0 ? model.kernelLine + 1 : 0;
      const action = CodeAction.create(
        'Insertar $0:format{cortex:1.0,encoding:UTF-8}',
        { changes: { [uri]: [TextEdit.insert(Position.create(at, 0), formatDeclText() + '\n')] } },
        CodeActionKind.QuickFix);
      action.diagnostics = [diag];
      action.isPreferred = true;
      actions.push(action);
    }

    // Missing KERNEL → insert
    if (/KERNEL|G001/.test(code) && code !== 'G010') {
      const action = CodeAction.create(
        'Insertar $0:KERNEL',
        { changes: { [uri]: [TextEdit.insert(Position.create(0, 0), '$0:KERNEL\n')] } },
        CodeActionKind.QuickFix);
      action.diagnostics = [diag];
      actions.push(action);
    }

    // Missing desc in glossary decl → append desc:"TODO"
    if (code.startsWith('G020')) {
      const line = lines[diag.range.start.line] ?? '';
      const close = line.lastIndexOf('}');
      if (close > 0) {
        const action = CodeAction.create(
          'Añadir desc:"" al sigilo',
          { changes: { [uri]: [TextEdit.insert(
              Position.create(diag.range.start.line, close), ',desc:"TODO"')] } },
          CodeActionKind.QuickFix);
        action.diagnostics = [diag];
        actions.push(action);
      }
    }
  }
  return actions;
}

// ------------------------------- formatting ------------------------------

/** Whole-document replace edit for canonicalize output. */
export function formatEdits(oldText: string, newText: string): TextEdit[] {
  const out = newText.endsWith('\n') ? newText : newText + '\n';
  if (out === oldText) { return []; }
  const lines = oldText.split(/\r?\n/);
  const lastLen = (lines[lines.length - 1] ?? '').length;
  return [TextEdit.replace(
    Range.create(0, 0, lines.length - 1, lastLen), out)];
}

// ------------------------ definition / references ------------------------

export function definitionLocation(
  uri: string, text: string, pos: Position
): Location | null {
  const tok = sigilTokenAt(text, pos.line, pos.character);
  if (!tok) { return null; }
  const decl = parseDoc(text).sigilByInst.get(tok.token);
  if (!decl) { return null; }
  return Location.create(uri, Range.create(decl.line, 0, decl.line, 0));
}

export function referenceLocations(
  uri: string, text: string, pos: Position
): Location[] {
  const tok = sigilTokenAt(text, pos.line, pos.character);
  if (!tok) { return []; }
  return findSigilRefs(text, tok.token).map((r) =>
    Location.create(uri, Range.create(r.line, r.start, r.line, r.end)));
}

// -------------------------------- rename ---------------------------------

export function prepareRenameRange(text: string, pos: Position): Range | null {
  const tok = sigilTokenAt(text, pos.line, pos.character);
  if (!tok) { return null; }
  const sigilPart = tok.token.split(':')[1];
  // Rename the instance name only — the sigil head stays.
  const instStart = tok.end - sigilPart.length;
  return Range.create(pos.line, instStart, pos.line, tok.end);
}

export function renameEdits(
  uri: string, text: string, pos: Position, newName: string
): WorkspaceEdit {
  const tok = sigilTokenAt(text, pos.line, pos.character);
  if (!tok) { return { changes: {} }; }
  if (!/^[A-Za-z_][\w-]*$/.test(newName)) {
    throw new Error('Nombre de instancia inválido: [A-Za-z_][\\w-]*');
  }
  const edits: TextEdit[] = [];
  for (const r of findSigilRefs(text, tok.token)) {
    const instStart = r.end - tok.token.split(':')[1].length;
    edits.push(TextEdit.replace(
      Range.create(r.line, instStart, r.line, r.end), newName));
  }
  return { changes: { [uri]: edits } };
}

// ---------------------------- semantic tokens ----------------------------

/** Delta-encoded semantic token stream (LSP SemanticTokens.data). */
export function semanticTokensData(text: string): number[] {
  const toks = collectSemanticTokens(text)
    .sort((a, b) => a.line - b.line || a.start - b.start);
  const data: number[] = [];
  let prevLine = 0;
  let prevStart = 0;
  for (const t of toks) {
    const dLine = t.line - prevLine;
    const dStart = dLine === 0 ? t.start - prevStart : t.start;
    data.push(dLine, dStart, t.length, t.type, t.modifiers);
    prevLine = t.line;
    prevStart = t.start;
  }
  return data;
}

// -------------------------------- folding --------------------------------

export function foldingRanges(text: string): FoldingRange[] {
  const model = parseDoc(text);
  const lineCount = text.split(/\r?\n/).length;
  return sectionFoldRanges(model)
    .filter((r) => (r.end === -1 ? lineCount - 1 : r.end) > r.start)
    .map((r) => ({
      startLine: r.start,
      endLine: r.end === -1 ? lineCount - 1 : r.end,
      kind: FoldingRangeKind.Region,
    }));
}
