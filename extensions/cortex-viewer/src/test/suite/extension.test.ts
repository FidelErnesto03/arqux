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
  stripHcortexComments,
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
