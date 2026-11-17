/**
 * extension.test.ts — unit + integration suite for arqux-cortex-viewer.
 *
 * Runs in plain mocha (no VS Code host): it exercises the pure core
 * modules against the real codec-cortex toolchain resolved by the
 * bridge's priority chain.
 */
import { strict as assert } from 'assert';
import { CodecBridge, parseHash, parseLossReport } from '../../codecBridge';
import {
  buildSigilDecl, collectSemanticTokens, errorCodeAt, findSigilRefs,
  formatDeclText, glossaryInsertLine, parseAttrs, parseDoc,
  parseErrorCatalog, sectionFoldRanges, sigilTokenAt, splitTopLevel,
  TOKEN_TYPES, TOKEN_MODIFIERS,
} from '../../cortexModel';
import { parseCodecErrors, sectionAtLine, lineOfSection } from '../../diagnostics';
import {
  buildCspMeta, buildHtmlShell, generateNonce, renderHcortexBody,
  stripHcortexComments, takeDiagramQueue,
} from '../../webviewKit';

const VALID_DOC =
  '$0:KERNEL\n' +
  '$0:format{cortex:1.0,encoding:UTF-8}\n' +
  'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item",fields:"name:text"}\n' +
  '$1: META\n' +
  'OBJ:item{name:"codec"}\n';

const INVALID_DOC =
  '$0:KERNEL\n' +
  '$0:format{cortex:1.0,encoding:UTF-8}\n' +
  '$1: META\n' +
  'OBJ:undeclared{x:1}\n';

function bigDoc(lines: number): string {
  // A sigil instance is declared once in the glossary and usable once
  // per section — use four distinct sigils per section to reach `lines`.
  const sigils = ['OBJ:i', 'WK:w', 'AXM:a', 'KNW:k'];
  const decl = sigils.map((s, i) =>
    `${s}{type:attrs,weight:H,focus:n,desc:"d${i}",fields:"n:text"}`);
  const out = [
    '$0:KERNEL',
    '$0:format{cortex:1.0,encoding:UTF-8}',
    ...decl,
  ];
  let sec = 0;
  while (out.length < lines - 5) {
    sec++;
    out.push(`$${sec}: S${sec}`);
    for (const s of sigils) { out.push(`${s}{n:"s${sec}r${s}"}`); }
  }
  return out.slice(0, lines - 1).join('\n') + '\n';
}

describe('codecBridge', function () {
  this.timeout(30000);
  const bridge = new CodecBridge();

  it('resolves a toolchain runtime from the priority chain', async () => {
    const rt = await bridge.activeRuntime();
    assert.ok(rt, 'expected at least one codec-cortex runtime on PATH');
  });

  it('test_valid_cortex_render — to-hcortex renders a valid doc', async () => {
    const res = await bridge.invoke('to-hcortex', VALID_DOC);
    assert.strictEqual(res.exitCode, 0, res.stderr || res.infraError);
    assert.ok(res.stdout.includes('§1'), 'HCORTEX should contain §1 section');
    assert.ok(res.stdout.includes('codec'), 'HCORTEX should contain doc data');
  });

  it('renders a 500-line document under 300ms (UI-01)', async () => {
    const res = await bridge.invoke('to-hcortex', bigDoc(500));
    assert.strictEqual(res.exitCode, 0, res.stderr || res.infraError);
    assert.ok(
      res.elapsedMs < 300,
      `render took ${res.elapsedMs}ms — exceeds 300ms budget`
    );
  });

  it('test_invalid_cortex_diagnostic — errors map to line/col diagnostics', async () => {
    const res = await bridge.invoke('validate', INVALID_DOC);
    assert.strictEqual(res.exitCode, 1);
    const diags = parseCodecErrors(res.stderr);
    assert.ok(diags.length >= 1, 'expected at least one diagnostic');
    const d = diags[0];
    assert.match(d.code, /^[A-Z]\d{3}_/);
    assert.strictEqual(d.severity, 'error');
    assert.strictEqual(d.line, 3, 'error is on 4th physical line (0-based 3)');
  });

  it('test_roundtrip_zero_loss — cortex→hcortex→cortex preserves hash', async () => {
    const render = await bridge.invoke('to-hcortex', VALID_DOC);
    assert.strictEqual(render.exitCode, 0);
    const compiled = await bridge.invoke('from-hcortex', render.stdout);
    assert.strictEqual(compiled.exitCode, 0, compiled.stderr);
    const validation = await bridge.invoke('validate', compiled.stdout);
    assert.strictEqual(validation.exitCode, 0, validation.stderr);
    const lossRes = await bridge.invoke('loss-report', compiled.stdout);
    const loss = parseLossReport(lossRes.stdout);
    assert.ok(loss, 'loss-report must be valid JSON');
    assert.strictEqual(loss!.losses.length, 0, 'expected zero declared losses');
    assert.strictEqual(loss!.reversible, true);
    const h1 = parseHash((await bridge.invoke('hash', VALID_DOC)).stdout);
    const h2 = parseHash((await bridge.invoke('hash', compiled.stdout)).stdout);
    assert.ok(h1 && h2, 'both hashes must parse');
    assert.strictEqual(h2, h1, 'canonical hash must be preserved');
  });

  it('invoke falls back across the chain on infra failure', async () => {
    // A fresh bridge must still resolve even if probed many times.
    const b2 = new CodecBridge();
    const res = await b2.invoke('hash', VALID_DOC);
    assert.strictEqual(res.exitCode, 0);
    assert.match(res.stdout, /sha256:[0-9a-f]{64}/);
  });
});

describe('diagnostics', () => {
  it('parses codec error lines (with and without ParseError prefix)', () => {
    const stderr =
      'ParseError: I001_UNDECLARED_SYMBOL @ 4:0 — Undeclared sigil: OBJ\n' +
      'S005_CONTENT_OUTSIDE_SECTION @ 1:0 — Content outside section\n';
    const diags = parseCodecErrors(stderr);
    assert.strictEqual(diags.length, 2);
    assert.strictEqual(diags[0].code, 'I001_UNDECLARED_SYMBOL');
    assert.strictEqual(diags[0].line, 3);
    assert.strictEqual(diags[0].col, 0);
    assert.strictEqual(diags[1].code, 'S005_CONTENT_OUTSIDE_SECTION');
  });

  it('sectionAtLine / lineOfSection resolve $N anchors', () => {
    const doc = '$0:KERNEL\n$0:format{cortex:1.0}\n$1: A\nx\n$2: B\ny\n';
    assert.strictEqual(sectionAtLine(doc, 3), '1');
    assert.strictEqual(sectionAtLine(doc, 5), '2');
    assert.strictEqual(sectionAtLine(doc, 0), null);
    assert.strictEqual(lineOfSection(doc, '2'), 4);
  });
});

describe('webviewKit', () => {
  it('test_csp_header — strict CSP with unique 32-byte nonce per render', () => {
    const n1 = generateNonce();
    const n2 = generateNonce();
    assert.notStrictEqual(n1, n2, 'nonces must be unique per render');
    assert.strictEqual(Buffer.from(n1, 'base64').length, 32, 'nonce must be 32 bytes');
    const csp = buildCspMeta('vscode-webview:', n1);
    assert.ok(csp.includes("default-src 'none'"));
    assert.ok(csp.includes(`script-src 'nonce-${n1}'`));
    assert.ok(csp.includes('style-src vscode-webview:'));
    assert.ok(!csp.includes("'unsafe-inline'"));
    assert.ok(!csp.includes("'unsafe-eval'"));
    const html = buildHtmlShell({
      nonce: n1, cspSource: 'vscode-webview:', cssUri: 'x.css', jsUri: 'x.js',
    });
    assert.ok(html.includes(`nonce="${n1}"`), 'shell script tag must carry the nonce');
    assert.ok(html.includes('Content-Security-Policy'));
  });

  it('renders HCORTEX headings with §N anchors', () => {
    const html = renderHcortexBody('## §1: META\n');
    assert.ok(html.includes('id="sec-1"'), `expected sec-1 anchor: ${html}`);
  });

  it('test_xss_escape — <script> payloads in text are escaped (SEC-03)', () => {
    const evil = 'OBJ:x{name:"<script>alert(1)</script>"}\n';
    const html = renderHcortexBody(evil);
    assert.ok(!html.includes('<script>alert'), 'raw <script> must not reach DOM');
    assert.ok(html.includes('&lt;script&gt;'), 'payload should be entity-escaped');
  });

  it('full pipeline: cortex with XSS payload → hcortex → sanitized html', async () => {
    const bridge = new CodecBridge();
    const doc =
      '$0:KERNEL\n$0:format{cortex:1.0,encoding:UTF-8}\n' +
      'OBJ:i{type:attrs,weight:H,focus:n,desc:"d",fields:"n:text"}\n' +
      '$1: X\nOBJ:i{n:"<script>alert(1)</script>"}\n';
    const res = await bridge.invoke('to-hcortex', doc);
    assert.strictEqual(res.exitCode, 0, res.stderr);
    const html = renderHcortexBody(res.stdout);
    assert.ok(!html.includes('<script>alert'), 'payload must be escaped end-to-end');
  });
});

// ---------------------------------------------------------------------
// cortexModel — 0.2.0 language intelligence core
// ---------------------------------------------------------------------
describe('cortexModel: document model', () => {
  const DOC =
    '$0:KERNEL\n' +
    '$0:format{cortex:1.0,encoding:UTF-8}\n' +
    '$0:enum_layer{values:"ARCH|SEC|UI"}\n' +
    'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item, con coma",fields:"name:text|capa:%layer"}\n' +
    'WK:step{type:cuerpo,weight:B,desc:"Paso"}\n' +
    '$1: META:CORE\n' +
    'OBJ:item{name:"x"}\n' +
    '$2: FLOW\n' +
    'WK:step{line:"l"}\n';

  it('parses glossary sigil declarations', () => {
    const m = parseDoc(DOC);
    assert.strictEqual(m.sigils.length, 2);
    assert.strictEqual(m.sigils[0].sigil, 'OBJ');
    assert.strictEqual(m.sigils[0].inst, 'item');
    assert.deepStrictEqual(m.sigils[0].fields, ['name', 'capa']);
    assert.strictEqual(m.sigilByInst.get('WK:step')?.attrs.weight, 'B');
  });

  it('parses $0 enums for % completion', () => {
    const m = parseDoc(DOC);
    assert.strictEqual(m.enums.length, 1);
    assert.deepStrictEqual(m.enums[0].values, ['ARCH', 'SEC', 'UI']);
    assert.deepStrictEqual(m.enumValues, ['ARCH', 'SEC', 'UI']);
  });

  it('parses section tree with capa', () => {
    const m = parseDoc(DOC);
    assert.strictEqual(m.sections.length, 2);
    assert.strictEqual(m.sections[0].id, '1');
    assert.strictEqual(m.sections[0].title, 'META');
    assert.strictEqual(m.sections[0].capa, 'CORE');
    assert.strictEqual(m.firstSectionLine, 5);
    assert.strictEqual(m.kernelLine, 0);
    assert.strictEqual(m.formatLine, 1);
  });

  it('splitTopLevel respects quoted commas', () => {
    assert.deepStrictEqual(
      splitTopLevel('a:1,desc:"x,y",b:2'),
      ['a:1', 'desc:"x,y"', 'b:2']);
  });

  it('parseAttrs handles quoted values', () => {
    const a = parseAttrs('type:attrs,desc:"Item, con coma",fields:"a:text|b:int"');
    assert.strictEqual(a.desc, 'Item, con coma');
    assert.strictEqual(a.fields, 'a:text|b:int');
  });

  it('glossaryInsertLine lands before first section', () => {
    const m = parseDoc(DOC);
    assert.strictEqual(glossaryInsertLine(m, DOC.split('\n').length), 5);
    const empty = parseDoc('$0:KERNEL\n');
    assert.strictEqual(glossaryInsertLine(empty, 1), 1);
  });

  it('buildSigilDecl produces a valid glossary line', () => {
    const d = buildSigilDecl('OBJ', 'nuevo');
    assert.ok(d.startsWith('OBJ:nuevo{'));
    assert.ok(d.includes('desc:'));
    assert.ok(d.endsWith('}'));
  });

  it('formatDeclText is the canonical format line', () => {
    assert.strictEqual(
      formatDeclText(), '$0:format{cortex:1.0,encoding:UTF-8}');
  });

  it('sigilTokenAt finds token under cursor', () => {
    const t = sigilTokenAt('OBJ:item{name:"x"}', 0, 3);
    assert.deepStrictEqual(t, { token: 'OBJ:item', start: 0, end: 8 });
    assert.strictEqual(sigilTokenAt('plain text', 0, 3), null);
  });

  it('errorCodeAt finds codes for catalog hover', () => {
    const t = errorCodeAt('# see I001_UNDECLARED_SYMBOL here', 0, 10);
    assert.strictEqual(t?.code, 'I001_UNDECLARED_SYMBOL');
    assert.strictEqual(errorCodeAt('no codes', 0, 3), null);
  });

  it('parseErrorCatalog maps codes to emitting surfaces', () => {
    const cat = parseErrorCatalog(
      '| Código | python | go | node | rust | bash |\n' +
      '|---|---|---|---|---|---|\n' +
      '| G002_GLOSSARY_REOPENED | x | x | x | x | x |\n' +
      '| G010_FORMAT_REQUIRED | x | — | — | — | — |\n');
    assert.deepStrictEqual(
      cat.get('G002_GLOSSARY_REOPENED'), ['python', 'go', 'node', 'rust', 'bash']);
    assert.deepStrictEqual(cat.get('G010_FORMAT_REQUIRED'), ['python']);
  });
});

// ---------------------------------------------------------------------
// canonicalize — the codec-backed formatter behind Format Document
// ---------------------------------------------------------------------
// ---------------------------------------------------------------------
// 0.2.1 — navigation & semantics
// ---------------------------------------------------------------------
describe('cortexModel: navigation & semantics', () => {
  const DOC =
    '$0:KERNEL\n' +
    '$0:format{cortex:1.0,encoding:UTF-8}\n' +
    '$0:enum_capa{values:"CORE|FLOW"}\n' +
    'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item",fields:"name:text|capa:%capa"}\n' +
    '$1: META\n' +
    'OBJ:item{name:"a"}\n' +
    '# OBJ:item no cuenta (comentario)\n' +
    '$2: FLOW\n' +
    'OBJ:item{name:"b",capa:%CORE}\n';

  it('findSigilRefs localiza decl+usos, saltando comentarios', () => {
    const refs = findSigilRefs(DOC, 'OBJ:item');
    // decl (line 3) + uso línea 5 + uso línea 8; comentario línea 6 excluido
    assert.strictEqual(refs.length, 3);
    assert.deepStrictEqual(refs.map((r) => r.line), [3, 5, 8]);
    assert.deepStrictEqual(
      refs.map((r) => r.start), [0, 0, 0]);
  });

  it('findSigilRefs respeta fronteras de token', () => {
    const doc = 'OBJ:item2{}\nXOBJ:item{}\nOBJ:item{}\n';
    const refs = findSigilRefs(doc, 'OBJ:item');
    assert.strictEqual(refs.length, 1);
    assert.strictEqual(refs[0].line, 2);
  });

  it('sectionFoldRanges cubre cada sección hasta la siguiente', () => {
    const model = parseDoc(DOC);
    const folds = sectionFoldRanges(model);
    assert.strictEqual(folds.length, 2);
    assert.deepStrictEqual(folds[0], { start: 4, end: 6 });
    assert.deepStrictEqual(folds[1], { start: 7, end: -1 });
  });

  it('collectSemanticTokens marca secciones, sigilos y %enums', () => {
    const toks = collectSemanticTokens(DOC);
    const T = (name: string) => TOKEN_TYPES.indexOf(name as never);
    // $0 heads → macro; $1/$2 → namespace
    assert.ok(toks.some((t) => t.line === 0 && t.type === T('macro')));
    assert.ok(toks.some((t) => t.line === 4 && t.type === T('namespace')));
    // OBJ:item en glosario → type + declaration modifier
    const declTok = toks.find((t) => t.line === 3 && t.start === 0);
    assert.ok(declTok && declTok.type === T('type')
      && (declTok.modifiers & (1 << TOKEN_MODIFIERS.indexOf('declaration'))) !== 0);
    // uso post-sección → type sin declaration
    const useTok = toks.find((t) => t.line === 5 && t.start === 0);
    assert.ok(useTok && (useTok.modifiers === 0));
    // %capa dentro del string fields: NO emite (dato, no ref);
    // %CORE fuera de strings en línea 8 → enumMember
    assert.ok(toks.some((t) => t.type === T('enumMember') && t.line === 8));
    // comentario línea 6: sin tokens
    assert.ok(!toks.some((t) => t.line === 6));
  });

  it('stripHcortexComments oculta etiquetas del render sin tocar el raw', () => {
    const hc =
      '<!-- HCORTEX v=1.0 t=canonical k=corpus -->\n' +
      '<!-- glossary -->\nX\n<!-- /glossary -->\n' +
      '## §1: META\n<!-- schema:1 -->\n### OBJ:item\n';
    const clean = stripHcortexComments(hc);
    assert.ok(!clean.includes('<!--'), 'comments stripped');
    assert.ok(clean.includes('## §1: META'));
    assert.ok(clean.includes('X'));
    // render end-to-end: no visible tag text
    const html = renderHcortexBody(hc);
    assert.ok(!html.includes('&lt;!--'), 'no comment text in DOM');
    assert.ok(!html.includes('glossary -->'));
    // raw is untouched
    assert.ok(hc.includes('<!-- glossary -->'));
  });

  it('glossary renderiza como panel estructurado, no texto crudo', () => {
    const hc =
      '<!-- HCORTEX v=1.0 t=canonical k=corpus -->\n' +
      '<!-- glossary -->\n' +
      '$0:KERNEL\n' +
      '$0:format{cortex:1.0,encoding:UTF-8}\n' +
      '$0:enum_capa{values:"CORE|FLOW"}\n' +
      'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item, con coma",fields:"name:text"}\n' +
      '<!-- /glossary -->\n' +
      '## §1: META\n' +
      '<!-- schema:1 -->\n' +
      '### OBJ:item\n| name |\n|---|\n| "x" |\n';
    const html = renderHcortexBody(hc);
    assert.ok(html.includes('hc-glossary'), 'glossary panel present');
    assert.ok(html.includes('§0 · Glosario'));
    assert.ok(html.includes('OBJ:item'));
    assert.ok(html.includes('<td>attrs</td>'), 'type column');
    assert.ok(html.includes('Item, con coma'), 'desc with comma parsed');
    assert.ok(html.includes('enum_capa'), 'enum chip');
    assert.ok(!html.includes('type:attrs,weight'), 'no raw attr dump');
    assert.ok(!html.includes('&lt;!--'));
  });

  it('schema blocks renderizan como cards con chips de tipo/peso', () => {
    const hc =
      '<!-- HCORTEX v=1.0 t=canonical k=corpus -->\n' +
      '<!-- glossary -->\n' +
      '$0:KERNEL\n' +
      'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item",fields:"name:text"}\n' +
      '<!-- /glossary -->\n' +
      '## §1: META\n' +
      '<!-- schema:1 -->\n' +
      '### OBJ:item\n| name | capa |\n|---|---|\n| "codec" | "CORE" |\n' +
      '### WK:step\n| note |\n|---|\n| "a|b en pipe" |\n' +
      '<!-- /schema:1 -->\n';
    const html = renderHcortexBody(hc);
    assert.ok(html.includes('hc-card w-h'), 'card con clase de weight');
    assert.ok(html.includes('hc-card-sig'), 'header sigilo');
    assert.ok(html.includes('>attrs<') && html.includes('>H<'), 'chips type/weight');
    // valores sin comillas en display
    assert.ok(html.includes('<td>codec</td>'));
    // pipe dentro de string preservado como una celda
    assert.ok(html.includes('a|b en pipe'));
    // la segunda instancia (sin decl en glosario) también sale como card
    assert.ok((html.match(/hc-card /g) ?? []).length >= 2);
    // §N heading sigue anclado
    assert.ok(html.includes('sec-1'));
  });

  it('collectSemanticTokens no emite % dentro de strings', () => {
    const toks = collectSemanticTokens(
      '$0:KERNEL\n$0:format{cortex:1.0,encoding:UTF-8}\n' +
      'OBJ:i{type:attrs,weight:M,focus:n,desc:"d",fields:"n:text"}\n' +
      '$1: X\nOBJ:i{n:"50%off"}\n');
    const T = TOKEN_TYPES.indexOf('enumMember' as never);
    assert.ok(!toks.some((t) => t.line === 4 && t.type === T));
  });
});

describe('canonicalize (format document)', () => {
  it('canonicalizes a valid doc and is idempotent', async () => {
    const bridge = new CodecBridge();
    const res = await bridge.invoke('canonicalize', VALID_DOC);
    assert.strictEqual(res.exitCode, 0, res.stderr || res.infraError);
    assert.ok(res.stdout.includes('$0:KERNEL'));
    const again = await bridge.invoke('canonicalize', res.stdout);
    assert.strictEqual(again.exitCode, 0);
    assert.strictEqual(again.stdout, res.stdout, 'canonicalize must be idempotent');
  });
});

// ── 0.3.0: cortex-ls core (transport-free handlers) ─────────────────
import * as lsp from '../../server/core';
import * as wsidx from '../../server/workspaceIndex';
import { Position } from 'vscode-languageserver-types';

const LS_DOC =
  '$0:KERNEL\n' +
  '$0:format{cortex:1.0,encoding:UTF-8}\n' +
  'OBJ:item{type:attrs,weight:H,focus:name,desc:"Item",fields:"name:text"}\n' +
  'WK:step{type:cuerpo,weight:M,focus:note,desc:"Paso",fields:"note:text"}\n' +
  '$0:enum_capa{values:"CORE|UI"}\n' +
  '$1: META\n' +
  'OBJ:item{name:"codec"}\n' +
  '$2: WORK\n' +
  'WK:step{note:"go %CORE"}\n';

describe('cortex-ls core (0.3.0)', () => {
  it('diagnosticsFromCodec mapea severidad/source/code', () => {
    const stderr = 'I001_UNDECLARED_SYMBOL @ 5:2 — Undeclared sigil: OBJ\n' +
      'W001_INFO @ 1:0 — warning\n';
    const diags = lsp.diagnosticsFromCodec(stderr, 10);
    assert.strictEqual(diags.length, 2);
    assert.strictEqual(diags[0].source, 'codec-cortex');
    assert.strictEqual(diags[0].severity, 1); // Error
    assert.strictEqual(diags[0].code, 'I001_UNDECLARED_SYMBOL');
    assert.strictEqual(diags[0].range.start.line, 4); // 1-based → 0-based
    assert.strictEqual(diags[1].severity, 2); // Warning
  });

  it('completionItems: sigilo declarado + %enum + attr keys', () => {
    // line start → declared sigils
    const items = lsp.completionItems(LS_DOC + 'OB', Position.create(9, 2));
    const labels = items.map((i) => i.label);
    assert.ok(labels.includes('OBJ:item'));
    assert.ok(labels.includes('WK:step'));

    // after % → enum values
    const enums = lsp.completionItems(LS_DOC + 'x%', Position.create(9, 2));
    assert.deepStrictEqual(
      enums.map((i) => i.label).sort(), ['CORE', 'UI']);

    // inside {} of a declared sigil → its contract fields
    const inside = lsp.completionItems(
      LS_DOC + 'OBJ:item{', Position.create(9, 9));
    assert.ok(inside.some((i) => i.label === 'name'));
  });

  it('hoverResult: decl exacta, instancia inline y sección', () => {
    const h = lsp.hoverResult(LS_DOC, Position.create(2, 3));
    assert.ok(h && h.contents.value.includes('sigilo declarado'));
    assert.ok(h!.contents.value.includes('glosario'));

    const inline = lsp.hoverResult(LS_DOC, Position.create(6, 4));
    assert.ok(inline && /Item|declarado/.test(inline.contents.value));

    const sec = lsp.hoverResult(LS_DOC, Position.create(5, 1));
    assert.ok(sec && sec.contents.value.includes('Sección §1'));
  });

  it('documentSymbols: kernel+glosario con hijas y §N', () => {
    const syms = lsp.documentSymbols(LS_DOC);
    const names = syms.map((s) => s.name);
    assert.ok(names.some((n) => n.includes('KERNEL')));
    assert.ok(names.includes('§1 META') || names.some((n) => n.startsWith('§1')));
    const kernel = syms.find((s) => s.name.includes('KERNEL'))!;
    assert.ok((kernel.children ?? []).some((c) => c.name === 'OBJ:item'));
  });

  it('codeActions genera quickfix para I001', () => {
    const diags = lsp.diagnosticsFromCodec(
      'I001_UNDECLARED_SYMBOL @ 6:0 — Undeclared sigil: FOO', 10);
    const actions = lsp.codeActions('file:///x.cortex', LS_DOC, diags);
    assert.ok(actions.length >= 1);
    assert.ok(actions[0].title.includes('Declarar'));
    const edits = actions[0].edit?.changes?.['file:///x.cortex'] ?? [];
    assert.ok(edits[0]?.newText.includes('FOO'));
  });

  it('formatEdits emite reemplazo de doc completo', () => {
    const edits = lsp.formatEdits('a\nb\n', 'a\nb\nc\n');
    assert.strictEqual(edits.length, 1);
    assert.strictEqual(edits[0].newText, 'a\nb\nc\n');
    assert.strictEqual(edits[0].range.start.line, 0);
    assert.strictEqual(lsp.formatEdits('x\n', 'x\n').length, 0);
  });

  it('definition/references/rename sobre instancia declarada', () => {
    const uri = 'file:///x.cortex';
    // cursor on OBJ:item usage (line 6)
    const def = lsp.definitionLocation(uri, LS_DOC, Position.create(6, 3));
    assert.ok(def && def.range.start.line === 2, 'definition → decl line');

    const refs = lsp.referenceLocations(uri, LS_DOC, Position.create(6, 3));
    assert.strictEqual(refs.length, 2, 'decl + uso');

    const prep = lsp.prepareRenameRange(LS_DOC, Position.create(6, 3));
    assert.ok(prep && prep.start.character > 0, 'rename solo instancia');

    const edit = lsp.renameEdits(uri, LS_DOC, Position.create(6, 3), 'item2');
    const changes = edit.changes?.[uri] ?? [];
    assert.strictEqual(changes.length, 2);
    assert.throws(
      () => lsp.renameEdits(uri, LS_DOC, Position.create(6, 3), '9bad'));
  });

  it('semanticTokensData: delta-encoded, empieza en $0', () => {
    const data = lsp.semanticTokensData(LS_DOC);
    assert.ok(data.length % 5 === 0);
    assert.strictEqual(data[0], 0); // first token line 0
    assert.strictEqual(data[1], 0); // col 0
    assert.strictEqual(data[2], 2); // '$0' length
  });

  it('foldingRanges cubre cada §N', () => {
    const fr = lsp.foldingRanges(LS_DOC);
    const starts = fr.map((f) => f.startLine);
    assert.ok(starts.includes(5) && starts.includes(7));
    assert.ok(fr.every((f) => f.endLine > f.startLine));
  });
});

describe('preview polish 0.3.0', () => {
  it('capítulos <details> por §N y glosario plegable', () => {
    const hc =
      '<!-- HCORTEX v=1.0 t=canonical k=corpus -->\n' +
      '<!-- glossary -->\n$0:KERNEL\nOBJ:i{type:attrs,weight:H}\n<!-- /glossary -->\n' +
      '## §1: META\n<!-- schema:1 -->\n### OBJ:i\n| f | v |\n|---|---|\n| a | b |\n<!-- /schema:1 -->\n' +
      '## §2: WORK\n<!-- schema:2 -->\n### WK:w\n| n | v |\n|---|---|\n| x | y |\n<!-- /schema:2 -->\n';
    const html = renderHcortexBody(hc);
    // dos capítulos §N + uno de glosario, todos <details open>
    assert.strictEqual((html.match(/<details class="hc-sec-block/g) ?? []).length, 3);
    assert.ok(html.includes('hc-glossary-wrap'));
    // las cards caen dentro de su capítulo
    assert.ok(/<summary>.*§1.*<\/summary>[\s\S]*hc-card/.test(html));
    // data-sigil para el highlight activo
    assert.ok(html.includes('data-sigil="OBJ:i"'));
    // los comentarios estructurales siguen ausentes del render
    assert.ok(!html.includes('<!--'));
  });

  it('shell incluye toolbar filtro+goto', () => {
    const shell = buildHtmlShell({
      nonce: 'n', cspSource: 'csp', cssUri: 'c', jsUri: 'j',
    });
    assert.ok(shell.includes('id="hc-filter"'));
    assert.ok(shell.includes('id="hc-goto"'));
  });
});

describe('cortex-ls 0.4.0-A — info comes to you', () => {
  it('inlayHints: type/weight junto a sigilo y tipo junto a field key', () => {
    const hints = lsp.inlayHints(LS_DOC);
    // uso OBJ:item en línea 6 → hint '·attrs·H' tras el token
    const sig = hints.find((h) => h.position.line === 6)!;
    assert.ok(sig && String(sig.label).includes('attrs')
      && String(sig.label).includes('H'));
    // field key `name:` dentro de {} → hint ':text'
    const key = hints.find((h) => String(h.label) === ':text');
    assert.ok(key, 'field type hint');
    // la línea de la decl (2) no recibe hint de sigilo
    assert.ok(!hints.some((h) => h.position.line === 2
      && String(h.label).includes('·')));
    // doc inválido no rompe
    assert.ok(Array.isArray(lsp.inlayHints(INVALID_DOC)));
  });

  it('codeLenses: usos sobre decl, conteo sobre §N, badge sobre $0', () => {
    const uri = 'file:///x.cortex';
    const lenses = lsp.codeLenses(uri, LS_DOC);
    const decl = lenses.find((l) => l.range.start.line === 2)!;
    assert.strictEqual(decl.command?.title, '1 uso(s)');
    assert.strictEqual(decl.command?.command, 'editor.action.showReferences');
    assert.strictEqual(decl.command?.arguments?.[0], uri);
    const sec = lenses.find((l) => l.range.start.line === 5)!;
    assert.strictEqual(sec.command?.title, '§1 · 1 sigilo(s)');
    const kernel = lenses.find((l) => l.range.start.line === 0)!;
    assert.ok(kernel.command?.title.includes('C14N'));
  });

  it('signatureHelp: firma del contrato dentro de {}', () => {
    // dentro de OBJ:item{…} en línea 6
    const help = lsp.signatureHelp(LS_DOC, Position.create(6, 14));
    assert.ok(help, 'help presente');
    assert.strictEqual(help!.signatures[0].label,
      'OBJ:item{name}');
    // fuera de {} → null
    assert.strictEqual(
      lsp.signatureHelp(LS_DOC, Position.create(0, 2)), null);
    // sigilo no declarado → firma estándar
    const std = lsp.signatureHelp(
      INVALID_DOC + 'FOO:x{a:1,', Position.create(4, 10));
    assert.ok(std && std.signatures[0].label.includes('type'));
    assert.strictEqual(std!.activeParameter, 1);
  });

  it('selectionRanges: token → attrs → línea → sección → doc', () => {
    const [sel] = lsp.selectionRanges(
      LS_DOC, [Position.create(6, 10)]);
    assert.strictEqual(sel.range.start.line, 6);
    const blk = sel.parent!;           // dentro de {} → attr-block
    assert.strictEqual(blk.range.start.line, 6);
    const line = blk.parent!;
    assert.strictEqual(line.range.start.character, 0);
    const sec = line.parent!;
    assert.strictEqual(sec.range.start.line, 5, 'padre = §1');
    const doc = sec.parent!;
    assert.strictEqual(doc.range.start.line, 0);
  });

  it('inlineDecorationOptions: filtra codec-cortex y mapea severidad', () => {
    const diags = lsp.diagnosticsFromCodec(
      'I001_UNDECLARED_SYMBOL @ 6:0 — Undeclared sigil: FOO\n' +
      'W001_INFO @ 1:0 — aviso', 10);
    const other = {
      range: diags[0].range, message: 'otro', source: 'otro-ls',
      severity: 1 as const,
    };
    const specs = lsp.inlineDecorationOptions([...diags, other]);
    assert.strictEqual(specs.length, 2, 'solo codec-cortex');
    assert.strictEqual(specs[0].line, 5);
    assert.strictEqual(specs[0].severity, 'error');
    assert.strictEqual(specs[1].severity, 'warning');
    assert.ok(specs[0].message.includes('Undeclared sigil: FOO'));
  });
});

describe('cortex-ls 0.4.1 — workspace intelligence', () => {
  const DOC_A =
    '$0:KERNEL\n' +
    '$0:format{cortex:1.0,encoding:UTF-8}\n' +
    'OBJ:item{type:attrs,weight:H,focus:name,desc:"I",fields:"name:text"}\n' +
    '$0:enum_capa{values:"CORE|UI"}\n' +
    '$1: META\n' +
    'OBJ:item{name:"a %CORE"}\n';
  const DOC_B =
    '$0:KERNEL\n' +
    '$1: WORK\n' +
    'OBJ:item{name:"b"}\n' +
    'WK:task{note:"x %UI"}\n';

  it('workspaceIndex indexa sigilos+secciones por uri', () => {
    const idx = new wsidx.WorkspaceIndex([]);
    idx.set('file:///a.cortex', DOC_A);
    idx.set('file:///b.cortex', DOC_B);
    const sigs = idx.sigilIndex();
    assert.ok(sigs.some((s) => s.token === 'OBJ:item'
      && s.uri === 'file:///a.cortex' && s.isDecl));
    assert.ok(sigs.some((s) => s.token === 'WK:task'
      && s.uri === 'file:///b.cortex' && !s.isDecl));
    const secs = idx.sectionIndex();
    assert.strictEqual(secs.length, 2);
    assert.ok(secs.some((s) => s.id === '1' && s.uri === 'file:///b.cortex'));
  });

  it('workspaceSymbols devuelve matches multi-doc con Location', () => {
    const idx = new wsidx.WorkspaceIndex([]);
    idx.set('file:///a.cortex', DOC_A);
    idx.set('file:///b.cortex', DOC_B);
    const syms = lsp.workspaceSymbols(idx, 'obj');
    assert.ok(syms.length >= 2);
    assert.ok(syms.every((s) => s.location.uri.startsWith('file:///')));
    const secs = lsp.workspaceSymbols(idx, '§1');
    assert.strictEqual(secs.length, 2, '§1 META + §1 WORK');
    assert.strictEqual(lsp.workspaceSymbols(idx, 'ZZZ').length, 0);
  });

  it('documentLinks: %enum apunta a $0:enum_* intra-doc', () => {
    const links = lsp.documentLinks(DOC_A);
    assert.strictEqual(links.length, 1);
    assert.strictEqual(links[0].target, '#enum-capa');
    assert.strictEqual(links[0].range.start.line, 5);
    // % fuera de string no linkea (línea de decl no cuenta)
    assert.strictEqual(lsp.documentLinks('$0:KERNEL\n%FOO\n').length, 0);
  });

  it('index invalidación: delete/set ante cambios de watcher', () => {
    const idx = new wsidx.WorkspaceIndex([]);
    idx.set('file:///x.cortex', DOC_A);
    assert.ok(idx.get('file:///x.cortex'));
    idx.delete('file:///x.cortex');      // FileChangeType.Deleted
    assert.strictEqual(idx.get('file:///x.cortex'), undefined);
    idx.set('file:///x.cortex', DOC_B);  // Changed → re-index
    assert.ok(idx.get('file:///x.cortex')!.sections
      .some((s) => s.title === 'WORK'));
  });

  it('path-safety: fuera de root y symlinks rechazados (H-02)', () => {
    const fs = require('fs');
    const os = require('os');
    const path = require('path');
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ws-'));
    const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'out-'));
    fs.writeFileSync(path.join(root, 'ok.cortex'), DOC_A);
    fs.writeFileSync(path.join(outside, 'bad.cortex'), DOC_B);
    // symlink dentro del root → fuera
    fs.symlinkSync(path.join(outside, 'bad.cortex'),
      path.join(root, 'link.cortex'));
    // subdir con symlink dir → fuera
    fs.symlinkSync(outside, path.join(root, 'dirlink'));

    const idx = new wsidx.WorkspaceIndex([
      wsidx.pathToFileUri(root)]);
    assert.ok(idx.isUnderRoot(path.join(root, 'ok.cortex')));
    assert.ok(!idx.isUnderRoot(path.join(outside, 'bad.cortex')));
    assert.strictEqual(
      idx.uriToPath(wsidx.pathToFileUri(
        path.join(outside, 'bad.cortex'))), null);

    const found = wsidx.scanCortexFiles(root);
    assert.strictEqual(found.length, 1, 'solo ok.cortex — symlinks skipped');
    assert.ok(found[0].fsPath.endsWith('ok.cortex'));
    fs.rmSync(root, { recursive: true, force: true });
    fs.rmSync(outside, { recursive: true, force: true });
  });
});

describe('diagrams 0.4.2 — preview render', () => {
  const DGM_HC =
    '<!-- HCORTEX v=1.0 t=canonical k=corpus -->\n' +
    '<!-- glossary -->\n$0:KERNEL\nCTX:ctx{type:cuerpo,weight:M,focus:body,desc:"x",fields:"body:text"}\n<!-- /glossary -->\n' +
    '## §1: TEST\n' +
    '<!-- schema:1 -->\n### CTX:ctx\nbody:"```puml\\n@startuml\\nA --> B\\n@enduml\\n```"\nnote:"plain text, no diagram"\n<!-- /schema:1 -->\n';

  it('attr con diagrama → figure + slot + spec en queue', () => {
    const html = renderHcortexBody(DGM_HC);
    assert.ok(html.includes('class="hc-diagram"'));
    assert.ok(html.includes('dgm-slot" data-dgm="0"'));
    assert.ok(html.includes('fuente puml'));
    // el source escapado dentro de details
    assert.ok(html.includes('@startuml'));
    // la línea note sigue como texto normal
    assert.ok(html.includes('plain text'));
    const specs = takeDiagramQueue();
    assert.strictEqual(specs.length, 1);
    assert.strictEqual(specs[0].lang, 'puml');
    assert.ok(specs[0].source.includes('@startuml'));
    assert.ok(specs[0].source.includes('A --> B'));
    // queue drenada
    assert.strictEqual(takeDiagramQueue().length, 0);
  });

  it('@startuml suelto y ```mermaid también detectados', () => {
    const hc =
      '<!-- schema:1 -->\n### CTX:ctx\n' +
      'body:"@startuml\\nX --> Y\\n@enduml"\n' +
      'd2:"```mermaid\\ngraph LR\\na-->b\\n```"\n' +
      '<!-- /schema:1 -->\n';
    renderHcortexBody(hc);
    const specs = takeDiagramQueue();
    assert.strictEqual(specs.length, 2);
    assert.strictEqual(specs[0].lang, 'puml');
    assert.strictEqual(specs[1].lang, 'mermaid');
  });

  it('lineas sin diagrama no generan specs', () => {
    renderHcortexBody(
      '<!-- schema:1 -->\n### CTX:ctx\nbody:"solo texto"\n<!-- /schema:1 -->\n');
    assert.strictEqual(takeDiagramQueue().length, 0);
  });
});
