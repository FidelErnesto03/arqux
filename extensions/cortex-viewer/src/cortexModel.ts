/**
 * cortexModel.ts — pure document model for CORTEX 1.0.
 *
 * Parses the document's own declarations (glossary sigils, $0 enums,
 * section tree, sigil usages) so language providers never need a
 * subprocess for IntelliSense. The codec stays the authority on
 * validity — this model only mirrors the *declared* surface.
 */

export interface SigilDecl {
  /** e.g. "OBJ" — the sigil head. */
  sigil: string;
  /** e.g. "item" in OBJ:item — the declared instance name. */
  inst: string;
  /** Raw attr map inside braces. */
  attrs: Record<string, string>;
  /** Contract field names from fields:"a:text|b:int". */
  fields: string[];
  /** 0-based line of the glossary declaration. */
  line: number;
}

export interface EnumDecl {
  name: string;
  values: string[];
}

export interface SectionInfo {
  /** "3" or "3.2" — without the $. */
  id: string;
  title: string;
  capa: string;
  line: number;
}

export interface CortexModel {
  sigils: SigilDecl[];
  sigilByInst: Map<string, SigilDecl>; // key "OBJ:item"
  enums: EnumDecl[];
  enumValues: string[];
  sections: SectionInfo[];
  /** Line where the first $N (N>0) section starts; -1 if none. */
  firstSectionLine: number;
  /** Line of $0:KERNEL; -1 if absent. */
  kernelLine: number;
  /** Line of $0:format{...}; -1 if absent. */
  formatLine: number;
}

const SIGIL_DECL_RE = /^([A-Z][A-Z0-9_]*):([A-Za-z_][\w-]*)\s*\{/;
const SECTION_RE = /^\$(\d+(?:\.\d+)?)\s*:\s*([^:]*?)(?::([A-Z][A-Z0-9_]*))?\s*$/;
const ENUM_RE = /^\$0:enum_([A-Za-z_][\w-]*)\s*\{/;
const ATTR_LINE_RE = /^[A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*\s*\{/;
const BRACE_RE = /\{([\s\S]*)\}\s*$/;

/** Split `k:v,k2:"a,b"` on top-level commas (quote-aware). */
export function splitTopLevel(s: string, sep = ','): string[] {
  const out: string[] = [];
  let depth = 0;
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
    if (c === '{' || c === '[' || c === '(') { depth++; cur += c; continue; }
    if (c === '}' || c === ']' || c === ')') { depth--; cur += c; continue; }
    if (c === sep && depth === 0) { out.push(cur); cur = ''; continue; }
    cur += c;
  }
  if (cur.trim() !== '' || out.length > 0) { out.push(cur); }
  return out;
}

export function parseAttrs(attrText: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of splitTopLevel(attrText)) {
    const m = /^\s*([A-Za-z_][\w-]*)\s*:\s*([\s\S]*?)\s*$/.exec(part);
    if (m) {
      let v = m[2];
      if (v.startsWith('"') && v.endsWith('"')) { v = v.slice(1, -1); }
      out[m[1]] = v;
    }
  }
  return out;
}

function fieldNames(fieldsAttr: string | undefined): string[] {
  if (!fieldsAttr) { return []; }
  return fieldsAttr
    .split('|')
    .map((f) => f.split(':')[0].trim())
    .filter((f) => f.length > 0);
}

export function parseDoc(text: string): CortexModel {
  const model: CortexModel = {
    sigils: [],
    sigilByInst: new Map(),
    enums: [],
    enumValues: [],
    sections: [],
    firstSectionLine: -1,
    kernelLine: -1,
    formatLine: -1,
  };

  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) { continue; }

    if (trimmed === '$0:KERNEL') { model.kernelLine = i; continue; }
    if (trimmed.startsWith('$0:format')) {
      if (model.formatLine === -1) { model.formatLine = i; }
      continue;
    }

    const em = ENUM_RE.exec(trimmed);
    if (em) {
      const bm = BRACE_RE.exec(trimmed);
      const attrs = bm ? parseAttrs(bm[1]) : {};
      const values = (attrs.values ?? '')
        .split('|')
        .map((v) => v.trim())
        .filter(Boolean);
      model.enums.push({ name: em[1], values });
      model.enumValues.push(...values);
      continue;
    }

    const sm = SECTION_RE.exec(trimmed);
    if (sm) {
      model.sections.push({
        id: sm[1],
        title: (sm[2] ?? '').trim(),
        capa: sm[3] ?? '',
        line: i,
      });
      if (sm[1] !== '0' && model.firstSectionLine === -1) {
        model.firstSectionLine = i;
      }
      continue;
    }

    const dm = SIGIL_DECL_RE.exec(trimmed);
    // Glossary declarations live in $0 — before the first $N>0 section.
    // Same-shaped lines later in the doc are *usages*, not declarations.
    if (dm && ATTR_LINE_RE.test(trimmed) && model.firstSectionLine === -1) {
      const bm = BRACE_RE.exec(trimmed);
      const attrs = bm ? parseAttrs(bm[1]) : {};
      const decl: SigilDecl = {
        sigil: dm[1],
        inst: dm[2],
        attrs,
        fields: fieldNames(attrs.fields),
        line: i,
      };
      model.sigils.push(decl);
      model.sigilByInst.set(`${dm[1]}:${dm[2]}`, decl);
    }
  }
  return model;
}

/** Parse the code↔surface map table from errors-1.0.md. */
export function parseErrorCatalog(text: string): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const line of text.split(/\r?\n/)) {
    const m = /^\|\s*([A-Z]\d{3}_[A-Z0-9_]+)\s*\|(.+)\|\s*$/.exec(line.trim());
    if (!m) { continue; }
    const surfaces = m[2]
      .split('|')
      .map((c) => c.trim())
      .filter((c) => c === 'x')
      .length;
    const cols = m[2].split('|').map((c) => c.trim());
    const names = ['python', 'go', 'node', 'rust', 'bash'];
    const emitters = cols
      .map((c, i) => (c === 'x' ? names[i] : null))
      .filter((x): x is string => !!x);
    out.set(m[1], emitters);
    void surfaces;
  }
  return out;
}

// ---------- pure edit builders (for quick fixes) ----------

/**
 * Where to insert a glossary declaration: right before the first
 * $N (N>0) section, else at end of document. Returns 0-based line.
 */
export function glossaryInsertLine(model: CortexModel, lineCount: number): number {
  return model.firstSectionLine >= 0 ? model.firstSectionLine : lineCount;
}

export function buildSigilDecl(sigil: string, inst: string): string {
  return `${sigil}:${inst}{type:attrs,weight:M,focus:name,desc:"TODO: describe ${sigil}:${inst}",fields:"name:text"}`;
}

/** Build the text to insert for a missing $0:format declaration. */
export function formatDeclText(): string {
  return '$0:format{cortex:1.0,encoding:UTF-8}';
}

/** Word/sigil-instance under a position, for hover/completion ranges. */
export function sigilTokenAt(text: string, line: number, col: number): { token: string; start: number; end: number } | null {
  const l = text.split(/\r?\n/)[line] ?? '';
  const re = /[A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(l)) !== null) {
    if (col >= m.index && col <= m.index + m[0].length) {
      return { token: m[0], start: m.index, end: m.index + m[0].length };
    }
  }
  return null;
}

/** Error-code token at position (e.g. G010_FORMAT_REQUIRED). */
export function errorCodeAt(text: string, line: number, col: number): { code: string; start: number; end: number } | null {
  const l = text.split(/\r?\n/)[line] ?? '';
  const re = /[A-Z]\d{3}_[A-Z0-9_]+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(l)) !== null) {
    if (col >= m.index && col <= m.index + m[0].length) {
      return { code: m[0], start: m.index, end: m.index + m[0].length };
    }
  }
  return null;
}

// ---------- 0.2.1: navigation & semantics helpers ----------

export interface LineRange {
  line: number;
  start: number;
  end: number;
}

/** All occurrences of a sigil instance `SIGIL:inst`, skipping comment lines. */
export function findSigilRefs(text: string, token: string): LineRange[] {
  const out: LineRange[] = [];
  const esc = token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(?<![\\w:])${esc}(?![\\w-])`, 'g');
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (l.trimStart().startsWith('#')) { continue; }
    let m: RegExpExecArray | null;
    re.lastIndex = 0;
    while ((m = re.exec(l)) !== null) {
      out.push({ line: i, start: m.index, end: m.index + token.length });
    }
  }
  return out;
}

/**
 * Foldable ranges: each $N section spans from its header line to the
 * line before the next sibling-or-higher section starts.
 */
export function sectionFoldRanges(model: CortexModel): { start: number; end: number }[] {
  const out: { start: number; end: number }[] = [];
  const secs = model.sections;
  for (let i = 0; i < secs.length; i++) {
    const next = secs[i + 1];
    const end = next ? next.line - 1 : -1;
    out.push({ start: secs[i].line, end });
  }
  return out;
}

export interface SemanticTok {
  line: number;
  start: number;
  length: number;
  /** index into legend tokenTypes. */
  type: number;
  /** bit flags into legend tokenModifiers. */
  modifiers: number;
}

export const TOKEN_TYPES = ['namespace', 'type', 'enumMember', 'macro'] as const;
export const TOKEN_MODIFIERS = ['declaration'] as const;

const T_NAMESPACE = TOKEN_TYPES.indexOf('namespace');
const T_TYPE = TOKEN_TYPES.indexOf('type');
const T_ENUMMEMBER = TOKEN_TYPES.indexOf('enumMember');
const T_MACRO = TOKEN_TYPES.indexOf('macro');
const M_DECL = 1 << TOKEN_MODIFIERS.indexOf('declaration');

/**
 * Semantic tokens for the whole document — pure, line-oriented.
 *  - `$N:` and `$0:` heads          → namespace / macro
 *  - `SIGIL:inst` tokens            → type (+declaration inside glossary zone)
 *  - `%name` refs outside strings   → enumMember
 */
export function collectSemanticTokens(text: string): SemanticTok[] {
  const model = parseDoc(text);
  const out: SemanticTok[] = [];
  const lines = text.split(/\r?\n/);
  const sigilRe = /[A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*/g;

  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!l.trim() || l.trimStart().startsWith('#')) { continue; }

    const sec = /^\s*(\$\d+(?:\.\d+)?)\s*:/.exec(l);
    if (sec) {
      out.push({
        line: i,
        start: l.indexOf('$'),
        length: sec[1].length,
        type: sec[1] === '$0' ? T_MACRO : T_NAMESPACE,
        modifiers: 0,
      });
    }

    // sigil tokens
    sigilRe.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = sigilRe.exec(l)) !== null) {
      const isDecl = i < model.firstSectionLine || model.firstSectionLine === -1;
      const decl = model.sigilByInst.get(m[0]);
      out.push({
        line: i,
        start: m.index,
        length: m[0].length,
        type: T_TYPE,
        modifiers: isDecl || decl?.line === i ? M_DECL : 0,
      });
    }

    // %enum refs — skip quoted segments
    let inStr = false;
    for (let c = 0; c < l.length; c++) {
      const ch = l[c];
      if (ch === '"' && l[c - 1] !== '\\') { inStr = !inStr; continue; }
      if (inStr) { continue; }
      if (ch === '%' && /[A-Za-z_]/.test(l[c + 1] ?? '')) {
        const em = /^%([A-Za-z_][\w-]*)/.exec(l.slice(c));
        if (em) {
          out.push({ line: i, start: c, length: em[0].length, type: T_ENUMMEMBER, modifiers: 0 });
          c += em[0].length - 1;
        }
      }
    }
  }
  return out;
}
