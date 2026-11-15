/**
 * providers.ts — language intelligence for .cortex documents.
 *
 * Completion (glossary sigils, %enums, attr keys), hover (sigil contract
 * + error catalog), document symbols (outline), quick fixes, and the
 * canonical formatter. All document knowledge comes from cortexModel
 * (pure) — no subprocess per keystroke.
 */
import * as vscode from 'vscode';
import { CodecBridge } from './codecBridge';
import {
  buildSigilDecl, collectSemanticTokens, errorCodeAt, findSigilRefs,
  formatDeclText, glossaryInsertLine, parseAttrs, parseDoc,
  parseErrorCatalog, sectionFoldRanges, sigilTokenAt,
  TOKEN_MODIFIERS, TOKEN_TYPES,
} from './cortexModel';

const DOC_SELECTOR: vscode.DocumentSelector = { language: 'cortex', scheme: 'file' };

let errorCatalog: Map<string, string[]> | null = null;

/** Lazy-load the normative error catalog: bundled copy first, workspace fallback. */
async function loadErrorCatalog(context: vscode.ExtensionContext): Promise<void> {
  if (errorCatalog !== null) { return; }
  errorCatalog = new Map();
  const bundled = vscode.Uri.joinPath(context.extensionUri, 'data', 'errors-1.0.md');
  try {
    const bytes = await vscode.workspace.fs.readFile(bundled);
    const parsed = parseErrorCatalog(Buffer.from(bytes).toString('utf8'));
    if (parsed.size > 0) { errorCatalog = parsed; return; }
  } catch { /* fall through to workspace search */ }
  const files = await vscode.workspace.findFiles('**/errors-1.0.md', '**/node_modules/**', 3);
  for (const f of files) {
    const bytes = await vscode.workspace.fs.readFile(f);
    const parsed = parseErrorCatalog(Buffer.from(bytes).toString('utf8'));
    if (parsed.size > 0) { errorCatalog = parsed; return; }
  }
}

export function registerProviders(context: vscode.ExtensionContext, bridge: CodecBridge): void {
  void loadErrorCatalog(context);

  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      DOC_SELECTOR, new CortexCompletionProvider(), '%', '{', ':'
    ),
    vscode.languages.registerHoverProvider(DOC_SELECTOR, new CortexHoverProvider()),
    vscode.languages.registerDocumentSymbolProvider(DOC_SELECTOR, new CortexSymbolProvider()),
    vscode.languages.registerCodeActionsProvider(
      DOC_SELECTOR, new CortexFixProvider(),
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
    ),
    vscode.languages.registerDocumentFormattingEditProvider(
      DOC_SELECTOR, new CortexFormatter(bridge)
    ),
    vscode.languages.registerDefinitionProvider(
      DOC_SELECTOR, new CortexDefinitionProvider()),
    vscode.languages.registerReferenceProvider(
      DOC_SELECTOR, new CortexReferenceProvider()),
    vscode.languages.registerRenameProvider(
      DOC_SELECTOR, new CortexRenameProvider()),
    vscode.languages.registerDocumentSemanticTokensProvider(
      DOC_SELECTOR, new CortexSemanticTokensProvider(),
      new vscode.SemanticTokensLegend([...TOKEN_TYPES], [...TOKEN_MODIFIERS])),
    vscode.languages.registerFoldingRangeProvider(
      DOC_SELECTOR, new CortexFoldingProvider()),
  );
}

// ------------------------------ completion ------------------------------

class CortexCompletionProvider implements vscode.CompletionItemProvider {
  provideCompletionItems(
    doc: vscode.TextDocument,
    pos: vscode.Position
  ): vscode.CompletionItem[] {
    const model = parseDoc(doc.getText());
    const line = doc.lineAt(pos.line).text;
    const before = line.slice(0, pos.character);
    const items: vscode.CompletionItem[] = [];

    // % → enum values
    if (before.endsWith('%')) {
      for (const e of model.enums) {
        for (const v of e.values) {
          const it = new vscode.CompletionItem(v, vscode.CompletionItemKind.EnumMember);
          it.detail = `enum ${e.name}`;
          items.push(it);
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
        const it = new vscode.CompletionItem(k, vscode.CompletionItemKind.Field);
        it.insertText = new vscode.SnippetString(`${k}:"$1"`);
        it.detail = decl ? `field of ${m![1]}` : 'contract attr';
        items.push(it);
      }
      return items;
    }

    // Line start / after $ → declarations + sigil usages
    if (/^\s*[A-Z]*$/.test(before) || before.endsWith('$')) {
      for (const s of model.sigils) {
        const it = new vscode.CompletionItem(
          `${s.sigil}:${s.inst}`, vscode.CompletionItemKind.Class);
        it.detail = s.attrs.desc ?? 'declared sigil';
        it.insertText = new vscode.SnippetString(
          `${s.sigil}:${s.inst}{${s.fields.map((f, i) => `${f}:"\${${i + 1}:${f}}"`) .join(',')}}`);
        items.push(it);
      }
      const sec = new vscode.CompletionItem('new section', vscode.CompletionItemKind.Snippet);
      sec.insertText = new vscode.SnippetString('\\$${1:2}: ${2:TITLE}');
      sec.detail = 'CORTEX section header';
      items.push(sec);
    }
    return items;
  }
}

// -------------------------------- hover ---------------------------------

class CortexHoverProvider implements vscode.HoverProvider {
  provideHover(doc: vscode.TextDocument, pos: vscode.Position): vscode.Hover | null {
    const text = doc.getText();

    const sigTok = sigilTokenAt(text, pos.line, pos.character);
    if (sigTok) {
      const model = parseDoc(text);
      const [sigil] = sigTok.token.split(':');
      const decl = model.sigilByInst.get(sigTok.token)
        ?? model.sigils.find((s) => s.sigil === sigil);
      if (decl) {
        const exact = model.sigilByInst.has(sigTok.token);
        const md = new vscode.MarkdownString();
        md.appendMarkdown(exact
          ? `**${sigTok.token}** — sigilo declarado\n\n`
          : `**${sigTok.token}** — instancia no declarada (contrato de \`${decl.sigil}:${decl.inst}\`)\n\n`);
        md.appendMarkdown('| attr | value |\n|---|---|\n');
        for (const [k, v] of Object.entries(decl.attrs)) {
          md.appendMarkdown(`| ${k} | \`${v}\` |\n`);
        }
        if (decl.fields.length) {
          md.appendMarkdown(`\nFields: ${decl.fields.map((f) => `\`${f}\``).join(' ')}`);
        }
        md.appendMarkdown(`\n\n_glosario, línea ${decl.line + 1}_`);
        return new vscode.Hover(
          md, new vscode.Range(pos.line, sigTok.start, pos.line, sigTok.end));
      }
      // No glossary decl — but the line itself may carry inline attrs
      // (e.g. AXM:x{...} inside a section): show them as instance data.
      const lineText = doc.lineAt(pos.line).text;
      const brace = /\{([\s\S]*)\}\s*$/.exec(lineText);
      const inline = brace ? parseAttrs(brace[1]) : {};
      if (Object.keys(inline).length > 0) {
        const md = new vscode.MarkdownString();
        md.appendMarkdown(
          `**${sigTok.token}** — instancia inline (sin decl en glosario)\n\n`);
        md.appendMarkdown('| attr | value |\n|---|---|\n');
        for (const [k, v] of Object.entries(inline)) {
          md.appendMarkdown(`| ${k} | \`${v}\` |\n`);
        }
        return new vscode.Hover(
          md, new vscode.Range(pos.line, sigTok.start, pos.line, sigTok.end));
      }
      const md = new vscode.MarkdownString(
        `**${sigTok.token}** — ⚠ sigilo sin declaración en el glosario`);
      return new vscode.Hover(
        md, new vscode.Range(pos.line, sigTok.start, pos.line, sigTok.end));
    }

    const codeTok = errorCodeAt(text, pos.line, pos.character);
    if (codeTok && errorCatalog?.has(codeTok.code)) {
      const emitters = errorCatalog.get(codeTok.code)!;
      const md = new vscode.MarkdownString(
        `**${codeTok.code}** — catálogo CORTEX 1.0\n\nEmitido por: ${emitters.join(', ')}`);
      return new vscode.Hover(
        md, new vscode.Range(pos.line, codeTok.start, pos.line, codeTok.end));
    }

    const sec = /^\$(\d+(?:\.\d+)?)\s*:/.exec(doc.lineAt(pos.line).text);
    if (sec && pos.character <= sec[0].length) {
      return new vscode.Hover(`Sección §${sec[1]} — CORTEX 1.0`);
    }
    return null;
  }
}

// -------------------------------- symbols -------------------------------

class CortexSymbolProvider implements vscode.DocumentSymbolProvider {
  provideDocumentSymbols(doc: vscode.TextDocument): vscode.DocumentSymbol[] {
    const model = parseDoc(doc.getText());
    const out: vscode.DocumentSymbol[] = [];

    if (model.kernelLine >= 0 || model.formatLine >= 0) {
      const start = model.kernelLine >= 0 ? model.kernelLine : 0;
      const end = model.firstSectionLine >= 0
        ? model.firstSectionLine - 1
        : doc.lineCount - 1;
      const kernel = new vscode.DocumentSymbol(
        '$0 KERNEL + glosario', '',
        vscode.SymbolKind.Namespace,
        new vscode.Range(start, 0, Math.max(start, end), 0),
        new vscode.Range(start, 0, start, 10));
      for (const s of model.sigils) {
        kernel.children.push(new vscode.DocumentSymbol(
          `${s.sigil}:${s.inst}`, s.attrs.type ?? '',
          vscode.SymbolKind.Interface,
          new vscode.Range(s.line, 0, s.line, doc.lineAt(s.line).text.length),
          new vscode.Range(s.line, 0, s.line, s.sigil.length + 1 + s.inst.length)));
      }
      out.push(kernel);
    }

    for (const sec of model.sections) {
      const nextSec = model.sections.find(
        (s) => s.line > sec.line && !s.id.startsWith(sec.id + '.'));
      const end = (nextSec ? nextSec.line : doc.lineCount) - 1;
      const sym = new vscode.DocumentSymbol(
        `§${sec.id} ${sec.title}`.trim(),
        sec.capa,
        vscode.SymbolKind.Module,
        new vscode.Range(sec.line, 0, end, 0),
        new vscode.Range(sec.line, 0, sec.line, doc.lineAt(sec.line).text.length));
      out.push(sym);
    }
    return out;
  }
}

// ------------------------------ quick fixes -----------------------------

class CortexFixProvider implements vscode.CodeActionProvider {
  provideCodeActions(
    doc: vscode.TextDocument,
    _range: vscode.Range,
    context: vscode.CodeActionContext
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];
    for (const diag of context.diagnostics) {
      if (diag.source !== 'codec-cortex') { continue; }
      const code = String(diag.code ?? '');

      // Undeclared sigil → declare it in the glossary
      const sigMatch = /Undeclared sigil:\s*([A-Z][A-Z0-9_]*)/.exec(diag.message);
      if (code.startsWith('I001') && sigMatch) {
        const usageLine = doc.lineAt(diag.range.start.line).text;
        const inst = /([A-Z][A-Z0-9_]*):([A-Za-z_][\w-]*)/.exec(usageLine);
        const declLine = inst
          ? buildSigilDecl(inst[1], inst[2])
          : `${sigMatch[1]}:item{type:attrs,weight:M,focus:name,desc:"TODO",fields:"name:text"}`;
        const model = parseDoc(doc.getText());
        const at = glossaryInsertLine(model, doc.lineCount);
        const action = new vscode.CodeAction(
          `Declarar ${inst ? inst[0] : sigMatch[1]} en el glosario`,
          vscode.CodeActionKind.QuickFix);
        action.diagnostics = [diag];
        action.isPreferred = true;
        action.edit = new vscode.WorkspaceEdit();
        action.edit.insert(doc.uri, new vscode.Position(at, 0), declLine + '\n');
        actions.push(action);
      }

      // Missing $0:format → insert it
      if (/FORMAT_REQUIRED|G005|G010/.test(code)) {
        const action = new vscode.CodeAction(
          'Insertar $0:format{cortex:1.0,encoding:UTF-8}',
          vscode.CodeActionKind.QuickFix);
        action.diagnostics = [diag];
        action.isPreferred = true;
        action.edit = new vscode.WorkspaceEdit();
        const model = parseDoc(doc.getText());
        const at = model.kernelLine >= 0 ? model.kernelLine + 1 : 0;
        action.edit.insert(doc.uri, new vscode.Position(at, 0), formatDeclText() + '\n');
        actions.push(action);
      }

      // Missing KERNEL → insert
      if (/KERNEL|G001/.test(code) && code !== 'G010') {
        const action = new vscode.CodeAction(
          'Insertar $0:KERNEL', vscode.CodeActionKind.QuickFix);
        action.diagnostics = [diag];
        action.edit = new vscode.WorkspaceEdit();
        action.edit.insert(doc.uri, new vscode.Position(0, 0), '$0:KERNEL\n');
        actions.push(action);
      }

      // Missing desc in glossary decl → append desc:""
      if (code.startsWith('G020')) {
        const line = doc.lineAt(diag.range.start.line).text;
        const close = line.lastIndexOf('}');
        if (close > 0) {
          const action = new vscode.CodeAction(
            'Añadir desc:"" al sigilo', vscode.CodeActionKind.QuickFix);
          action.diagnostics = [diag];
          action.edit = new vscode.WorkspaceEdit();
          action.edit.insert(
            doc.uri, new vscode.Position(diag.range.start.line, close), ',desc:"TODO"');
          actions.push(action);
        }
      }
    }
    return actions;
  }
}

// ------------------------------ formatter -------------------------------

class CortexFormatter implements vscode.DocumentFormattingEditProvider {
  constructor(private bridge: CodecBridge) {}

  async provideDocumentFormattingEdits(
    doc: vscode.TextDocument
  ): Promise<vscode.TextEdit[]> {
    const res = await this.bridge.invoke('canonicalize', doc.getText());
    if (res.exitCode !== 0 || !res.stdout) {
      void vscode.window.showWarningMessage(
        `canonicalize falló: ${res.stderr.trim() || res.infraError || 'exit ' + res.exitCode}`);
      return [];
    }
    if (res.stdout === doc.getText()) { return []; }
    const last = doc.lineAt(doc.lineCount - 1);
    return [vscode.TextEdit.replace(
      new vscode.Range(new vscode.Position(0, 0), last.range.end),
      res.stdout.endsWith('\n') ? res.stdout : res.stdout + '\n')];
  }
}
// ------------------------- go to definition (F12) ------------------------

class CortexDefinitionProvider implements vscode.DefinitionProvider {
  provideDefinition(
    doc: vscode.TextDocument,
    pos: vscode.Position
  ): vscode.Definition | null {
    const tok = sigilTokenAt(doc.getText(), pos.line, pos.character);
    if (!tok) { return null; }
    const decl = parseDoc(doc.getText()).sigilByInst.get(tok.token);
    if (!decl) { return null; }
    return new vscode.Location(
      doc.uri, new vscode.Position(decl.line, 0));
  }
}

// ------------------------- find references (⇧F12) ------------------------

class CortexReferenceProvider implements vscode.ReferenceProvider {
  provideReferences(
    doc: vscode.TextDocument,
    pos: vscode.Position,
    _ctx: vscode.ReferenceContext
  ): vscode.Location[] {
    const tok = sigilTokenAt(doc.getText(), pos.line, pos.character);
    if (!tok) { return []; }
    return findSigilRefs(doc.getText(), tok.token)
      .map((r) => new vscode.Location(
        doc.uri, new vscode.Range(r.line, r.start, r.line, r.end)));
  }
}

// ------------------------------ rename (F2) ------------------------------

class CortexRenameProvider implements vscode.RenameProvider {
  prepareRename(
    doc: vscode.TextDocument,
    pos: vscode.Position
  ): vscode.Range | null {
    const tok = sigilTokenAt(doc.getText(), pos.line, pos.character);
    if (!tok) { return null; }
    const sigilPart = tok.token.split(':')[1];
    // Rename the instance name only — the sigil head stays.
    const instStart = tok.end - sigilPart.length;
    return new vscode.Range(pos.line, instStart, pos.line, tok.end);
  }

  provideRenameEdits(
    doc: vscode.TextDocument,
    pos: vscode.Position,
    newName: string
  ): vscode.WorkspaceEdit | null {
    const tok = sigilTokenAt(doc.getText(), pos.line, pos.character);
    if (!tok) { return null; }
    if (!/^[A-Za-z_][\w-]*$/.test(newName)) {
      throw new Error('Nombre de instancia inválido: [A-Za-z_][\\w-]*');
    }
    const edit = new vscode.WorkspaceEdit();
    for (const r of findSigilRefs(doc.getText(), tok.token)) {
      const instStart = r.end - tok.token.split(':')[1].length;
      edit.replace(
        doc.uri,
        new vscode.Range(r.line, instStart, r.line, r.end),
        newName);
    }
    return edit;
  }
}

// ---------------------------- semantic tokens ----------------------------

class CortexSemanticTokensProvider implements vscode.DocumentSemanticTokensProvider {
  provideDocumentSemanticTokens(doc: vscode.TextDocument): vscode.SemanticTokens {
    const builder = new vscode.SemanticTokensBuilder(
      new vscode.SemanticTokensLegend([...TOKEN_TYPES], [...TOKEN_MODIFIERS]));
    for (const t of collectSemanticTokens(doc.getText())) {
      builder.push(
        t.line, t.start, t.length, t.type, t.modifiers);
    }
    return builder.build();
  }
}

// ------------------------------- folding ---------------------------------

class CortexFoldingProvider implements vscode.FoldingRangeProvider {
  provideFoldingRanges(doc: vscode.TextDocument): vscode.FoldingRange[] {
    const model = parseDoc(doc.getText());
    return sectionFoldRanges(model)
      .filter((r) => (r.end === -1 ? doc.lineCount - 1 : r.end) > r.start)
      .map((r) => new vscode.FoldingRange(
        r.start,
        r.end === -1 ? doc.lineCount - 1 : r.end,
        vscode.FoldingRangeKind.Region));
  }
}

export {};
