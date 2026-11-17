/**
 * diagramRenderer.ts — local diagram → SVG for the HCORTEX preview.
 *
 * Detects plantuml/mermaid sources inside cuerpo strings and renders
 * them via locally installed CLIs (never network — SEC):
 *   - `plantuml -pipe -tsvg` (stdin → stdout)
 *   - `mmdc -i <tmp>.mmd -o <tmp>.svg` (mermaid-cli)
 *
 * Results are cached by sha256(lang+source) — a diagram renders once
 * per distinct source, not per preview refresh. Missing/failed
 * renderers degrade to the clean source fallback (no exceptions).
 */
import { spawn } from 'child_process';
import { createHash } from 'crypto';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

export type DiagramLang = 'puml' | 'mermaid';

const cache = new Map<string, string | null>();
const TIMEOUT_MS = 15_000;

function key(lang: DiagramLang, source: string): string {
  return createHash('sha256').update(`${lang}:${source}`).digest('hex');
}

function run(cmd: string, args: string[], input: string): Promise<string> {
  return new Promise((resolvePromise) => {
    const p = spawn(cmd, args, { shell: false, timeout: TIMEOUT_MS });
    let out = '';
    p.stdout.on('data', (d) => { out += d; });
    p.on('error', () => resolvePromise(''));
    p.on('close', (code) => resolvePromise(code === 0 ? out : ''));
    p.stdin.on('error', () => { /* EPIPE on early exit — ignore */ });
    p.stdin.write(input);
    p.stdin.end();
  });
}

/** plantuml/mermaid SVG is local tool output — strip scripts defensively. */
function sanitizeSvg(svg: string): string {
  const open = svg.indexOf('<svg');
  if (open < 0) { return ''; }
  const close = svg.lastIndexOf('</svg>');
  const body = close > open ? svg.slice(open, close + 6) : svg.slice(open);
  return body
    .replace(/<script[\s\S]*?(<\/script>|\/>)/gi, '')
    .replace(/on\w+="[^"]*"/g, '');
}

async function plantumlSvg(source: string): Promise<string> {
  const src = /@start/.test(source)
    ? source
    : `@startuml\n${source}\n@enduml\n`;
  const out = await run('plantuml', ['-pipe', '-tsvg'], src);
  return out.includes('<svg') ? sanitizeSvg(out) : '';
}

async function mermaidSvg(source: string): Promise<string> {
  const dir = mkdtempSync(join(tmpdir(), 'cortex-dgm-'));
  try {
    const inp = join(dir, 'd.mmd');
    const outp = join(dir, 'd.svg');
    writeFileSync(inp, source, 'utf8');
    const res = await run('mmdc', ['-i', inp, '-o', outp, '-b', 'transparent'], '');
    void res;
    let svg = '';
    try { svg = readFileSync(outp, 'utf8'); } catch { return ''; }
    return svg.includes('<svg') ? sanitizeSvg(svg) : '';
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/**
 * Render one diagram source to sanitized inline SVG.
 * Returns '' when the tool is absent or the render fails — callers
 * keep the textual fallback.
 */
export async function renderDiagram(
  lang: DiagramLang, source: string
): Promise<string> {
  const k = key(lang, source);
  if (cache.has(k)) { return cache.get(k) ?? ''; }
  const svg = lang === 'puml'
    ? await plantumlSvg(source)
    : await mermaidSvg(source);
  cache.set(k, svg || null);
  return svg;
}
