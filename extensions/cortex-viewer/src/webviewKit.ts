/**
 * webviewKit.ts — pure webview helpers: nonce generation, strict CSP,
 * and the markdown-it pipeline that renders HCORTEX into sanitized HTML.
 *
 * SEC-02: CSP `default-src 'none'` + per-render 32-byte nonce.
 * SEC-03: markdown-it with html:false — raw HTML inside .cortex text can
 *         never reach the DOM; entities are escaped by the renderer.
 *
 * Pure module: no `vscode` import so tests can exercise it headless.
 */
import { randomBytes } from 'crypto';
import MarkdownIt from 'markdown-it';

/** 32-byte nonce, fresh per render (SEC-02). */
export function generateNonce(): string {
  return randomBytes(32).toString('base64');
}

export function buildCspMeta(cspSource: string, nonce: string): string {
  return (
    `default-src 'none'; ` +
    `style-src ${cspSource}; ` +
    `script-src 'nonce-${nonce}'; ` +
    `img-src ${cspSource} https:;`
  );
}

/** markdown-it instance with heading anchors for §N scroll sync. */
export function createRenderer(): MarkdownIt {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    typographer: false,
    breaks: false,
  });

  const defaultHeadingOpen =
    md.renderer.rules.heading_open ??
    ((tokens: any[], idx: number, _o: any, _e: any, self: any) =>
      self.renderToken(tokens, idx, _o));

  md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
    const inline = tokens[idx + 1];
    const m = inline && inline.type === 'inline'
      ? inline.content.match(/§\s*(\d+(?:\.\d+)?)/)
      : null;
    if (m) {
      tokens[idx].attrSet('id', `sec-${m[1]}`);
      tokens[idx].attrSet('class', 'hc-sec');
      tokens[idx].attrSet('data-sec', m[1]);
    }
    return defaultHeadingOpen(tokens, idx, options, env, self);
  };

  return md;
}

/**
 * Strip HCORTEX structural comments (`<!-- HCORTEX … -->`,
 * `<!-- glossary -->`, `<!-- schema:N -->`…) before rendering — they are
 * codec metadata, not content. The raw stream keeps them; export paths
 * that need provenance re-inject them.
 */
export function stripHcortexComments(hcortex: string): string {
  return hcortex.replace(/<!--[\s\S]*?-->/g, '');
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Split `k:v,k2:"a,b"` on top-level commas (quote-aware). */
function splitAttrs(s: string): string[] {
  const out: string[] = [];
  let inStr = false;
  let cur = '';
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inStr) {
      cur += c;
      if (c === '"' && s[i - 1] !== '\\') { inStr = false; }
      continue;
    }
    if (c === '"') { inStr = true; cur += c; continue; }
    if (c === ',') { out.push(cur); cur = ''; continue; }
    cur += c;
  }
  if (cur.trim() || out.length) { out.push(cur); }
  return out;
}

function kvPairs(attrText: string): [string, string][] {
  return splitAttrs(attrText)
    .map((p) => {
      const m = /^\s*([A-Za-z_][\w-]*)\s*:\s*([\s\S]*?)\s*$/.exec(p);
      if (!m) { return null; }
      let v = m[2];
      if (v.startsWith('"') && v.endsWith('"')) { v = v.slice(1, -1); }
      return [m[1], v] as [string, string];
    })
    .filter((x): x is [string, string] => !!x);
}

/**
 * Structured glossary render: the raw decl lines between
 * `<!-- glossary -->` and `<!-- /glossary -->` become a readable panel —
 * $0 declarations as chips, each sigil as a table row.
 */
function renderGlossary(block: string): string {
  const lines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const chips: string[] = [];
  const rows: string[] = [];
  const STD = ['type', 'weight', 'focus', 'desc', 'fields'];

  for (const line of lines) {
    const dm = /^([A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*)\s*\{([\s\S]*)\}\s*$/.exec(line);
    if (dm) {
      const attrs = kvPairs(dm[2]);
      const get = (k: string) => attrs.find(([a]) => a === k)?.[1] ?? '';
      const extra = attrs.filter(([a]) => !STD.includes(a))
        .map(([a, v]) => `${a}:${v}`).join(' · ');
      rows.push(
        `<tr><td><code>${escapeHtml(dm[1])}</code></td>` +
        STD.map((k) => `<td>${escapeHtml(get(k))}</td>`).join('') +
        `<td class="g-extra">${escapeHtml(extra)}</td></tr>`);
      continue;
    }
    const zd = /^(\$0:[A-Za-z_]+)\s*\{?([\s\S]*?)\}?\s*$/.exec(line);
    if (zd) {
      chips.push(
        `<span class="g-chip"><b>${escapeHtml(zd[1])}</b>` +
        (zd[2] ? ` ${escapeHtml(zd[2])}` : '') + `</span>`);
      continue;
    }
    chips.push(`<span class="g-chip">${escapeHtml(line)}</span>`);
  }

  return (
    `<section class="hc-glossary"><h2 class="g-title">§0 · Glosario</h2>` +
    `<div class="g-chips">${chips.join('')}</div>` +
    (rows.length
      ? `<table class="g-sigils"><thead><tr>` +
        `<th>sigilo</th><th>type</th><th>weight</th><th>focus</th>` +
        `<th>desc</th><th>fields</th><th>otros</th></tr></thead>` +
        `<tbody>${rows.join('')}</tbody></table>`
      : '') +
    `</section>`);
}

/** sigil inst → declared {type, weight} from the glossary block. */
function sigilInfo(block: string): Map<string, { type: string; weight: string }> {
  const out = new Map<string, { type: string; weight: string }>();
  for (const line of block.split(/\r?\n/)) {
    const dm = /^\s*([A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*)\s*\{([\s\S]*)\}\s*$/.exec(line);
    if (!dm) { continue; }
    const attrs = kvPairs(dm[2]);
    out.set(dm[1], {
      type: attrs.find(([a]) => a === 'type')?.[1] ?? '',
      weight: attrs.find(([a]) => a === 'weight')?.[1] ?? '',
    });
  }
  return out;
}

function unquote(v: string): string {
  const t = v.trim();
  return t.startsWith('"') && t.endsWith('"') && t.length >= 2
    ? t.slice(1, -1)
    : t;
}

/** Split a markdown table row on `|` outside quotes. */
function tableCells(row: string): string[] {
  const cells: string[] = [];
  let inStr = false;
  let cur = '';
  const body = row.trim().replace(/^\|/, '').replace(/\|$/, '');
  for (let i = 0; i < body.length; i++) {
    const c = body[i];
    if (inStr) {
      cur += c;
      if (c === '"' && body[i - 1] !== '\\') { inStr = false; }
      continue;
    }
    if (c === '"') { inStr = true; cur += c; continue; }
    if (c === '|') { cells.push(cur); cur = ''; continue; }
    cur += c;
  }
  cells.push(cur);
  return cells.map((c) => c.trim());
}

/** Emit an HCORTEX schema table as clean HTML (unquoted values). */
function renderSchemaTable(rows: string[]): string {
  const parsed = rows
    .map(tableCells)
    .filter((cells) => !cells.every((c) => /^:?-{2,}:?$/.test(c)));
  if (parsed.length === 0) { return ''; }
  const [head, ...body] = parsed;
  return (
    `<table class="hc-table">` +
    `<thead><tr>${head.map((c) => `<th>${escapeHtml(unquote(c))}</th>`).join('')}</tr></thead>` +
    `<tbody>${body.map((r) =>
      `<tr>${r.map((c) => `<td>${escapeHtml(unquote(c))}</td>`).join('')}</tr>`
    ).join('')}</tbody></table>`);
}

const WEIGHT_CLASS: Record<string, string> = { H: 'w-h', M: 'w-m', B: 'w-b' };

/**
 * Render one `<!-- schema:N -->` block as a card per instance:
 *   <div class="hc-card w-X">  <head><code>SIGIL:inst</code> + type chip</head>
 *   content (tables → clean HTML, text → markdown-it)
 */
function renderSchema(
  inner: string,
  info: Map<string, { type: string; weight: string }>,
  md: MarkdownIt
): string {
  const chunks = inner.split(/(?=^### )/m).filter((c) => c.trim());
  const out: string[] = [];
  for (const chunk of chunks) {
    const hm = /^###\s+([A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*)\s*$/.exec(
      chunk.trimStart().split(/\r?\n/, 1)[0]);
    if (!hm) {
      out.push(md.render(chunk));
      continue;
    }
    const meta = info.get(hm[1]);
    const wc = meta ? (WEIGHT_CLASS[meta.weight] ?? '') : '';
    const rest = chunk.trimStart().split(/\r?\n/).slice(1).join('\n');

    const tableLines: string[] = [];
    const textLines: string[] = [];
    for (const l of rest.split(/\r?\n/)) {
      if (/^\s*\|/.test(l)) { tableLines.push(l); }
      else if (l.trim()) { textLines.push(l); }
    }
    const content =
      (tableLines.length ? renderSchemaTable(tableLines) : '') +
      (textLines.length ? md.render(textLines.join('\n')) : '');

    out.push(
      `<div class="hc-card ${wc}">` +
      `<div class="hc-card-head"><code class="hc-card-sig">${escapeHtml(hm[1])}</code>` +
      (meta?.type ? `<span class="w-chip" title="type">${escapeHtml(meta.type)}</span>` : '') +
      (meta?.weight ? `<span class="w-chip w-${escapeHtml(meta.weight)}" title="weight">${escapeHtml(meta.weight)}</span>` : '') +
      `</div>${content}</div>`);
  }
  return out.join('');
}

export function renderHcortexBody(hcortex: string): string {
  const md = createRenderer();
  const out: string[] = [];
  const re = /<!--\s*(glossary|schema:\d+)\s*-->([\s\S]*?)<!--\s*\/\1\s*-->/g;

  // Pre-pass: glossary info feeds schema card chips.
  const gm = re.exec(hcortex);
  re.lastIndex = 0;
  const info = gm?.[1] === 'glossary' ? sigilInfo(gm[2]) : new Map();

  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(hcortex)) !== null) {
    const before = stripHcortexComments(hcortex.slice(last, m.index));
    if (before.trim()) { out.push(md.render(before)); }
    if (m[1] === 'glossary') {
      out.push(renderGlossary(m[2]));
    } else {
      out.push(renderSchema(m[2], info, md));
    }
    last = m.index + m[0].length;
  }
  const tail = stripHcortexComments(hcortex.slice(last));
  if (tail.trim()) { out.push(md.render(tail)); }
  return out.join('');
}

export interface BadgeState {
  valid: boolean;
  canon: string;
  hashShort: string;
  hashFull: string;
  lossCount: number;
  runtime: string;
}

/**
 * Full HTML shell for the HCORTEX webview. The rendered body and badge
 * state are injected via postMessage on every refresh; only the shell
 * (CSP, css/js refs) is fixed here.
 */
export function buildHtmlShell(opts: {
  nonce: string;
  cspSource: string;
  cssUri: string;
  jsUri: string;
}): string {
  const { nonce, cspSource, cssUri, jsUri } = opts;
  const csp = buildCspMeta(cspSource, nonce);
  return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="${cssUri}">
<title>HCORTEX Preview</title>
</head>
<body>
<header id="hc-header">
  <span id="badge-state" class="badge">—</span>
  <span id="badge-canon" class="badge">Canon: —</span>
  <span id="badge-hash" class="badge badge-hash" title="SHA-256 canónico">
    <code id="hash-short">—</code>
    <button id="copy-hash" type="button" class="icon-btn" title="Copiar SHA-256 completo" aria-label="Copiar SHA-256 completo">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
    </button>
  </span>
  <span id="badge-loss" class="badge">Loss-Report: —</span>
  <span id="badge-runtime" class="badge">Runtime: —</span>
</header>
<div id="edit-result" hidden></div>
<main id="hc-body"></main>
<script nonce="${nonce}" src="${jsUri}"></script>
</body>
</html>`;
}
