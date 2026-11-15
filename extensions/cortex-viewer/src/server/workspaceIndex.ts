/**
 * server/workspaceIndex.ts — in-memory workspace index for cortex-ls.
 *
 * BLP-004 (0.4.0-B): uri → parsed CortexModel map feeding workspace
 * symbols, workspace validation and enum document links.
 *
 * SEC (audit H-02): filesystem reads are contained —
 *   - never follows symlinks (withFileTypes + isSymbolicLink skip)
 *   - every path is verified under a declared workspaceFolder root
 *   - capped at MAX_FILES files / MAX_BYTES per file
 * No persistence — the disk stays the authority.
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, resolve, sep } from 'path';
import { parseDoc, CortexModel } from '../cortexModel';

/** file:// URI → fsPath (file-scheme only; returns '' otherwise). */
export function fileUriToPath(uri: string): string {
  if (!uri.startsWith('file://')) { return ''; }
  let p = uri.slice('file://'.length);
  // file:///C:/… → /C:/… → strip leading slash on win drive
  p = decodeURIComponent(p);
  if (/^\/[A-Za-z]:/.test(p)) { p = p.slice(1); }
  return p;
}

/** fsPath → file:// URI. */
export function pathToFileUri(fsPath: string): string {
  return 'file://' + encodeURI(fsPath).replace(/\?/g, '%3F');
}

export const MAX_FILES = 500;
export const MAX_BYTES = 1024 * 1024; // 1 MB

export interface IndexedSigil {
  token: string;   // "OBJ:item"
  line: number;
  uri: string;
  isDecl: boolean;
}

export interface IndexedSection {
  id: string;      // "1" (without §)
  title: string;
  line: number;
  uri: string;
}

export class WorkspaceIndex {
  private models = new Map<string, CortexModel>();
  private texts = new Map<string, string>();
  /** workspaceFolder fsPaths (absolute, resolved) — containment roots. */
  readonly roots: string[];

  constructor(workspaceFolderUris: string[] = []) {
    this.roots = workspaceFolderUris
      .map((u) => {
        const p = fileUriToPath(u);
        return p ? resolve(p) : '';
      })
      .filter(Boolean);
  }

  /** fsPath is under at least one declared root (H-02 containment). */
  isUnderRoot(fsPath: string): boolean {
    if (this.roots.length === 0) { return true; } // single-file mode
    const p = resolve(fsPath);
    return this.roots.some(
      (r) => p === r || p.startsWith(r + sep));
  }

  /** uri → contained fsPath, or null when outside roots. */
  uriToPath(uri: string): string | null {
    const p = fileUriToPath(uri);
    return p && this.isUnderRoot(p) ? p : null;
  }

  set(uri: string, text: string): void {
    this.texts.set(uri, text);
    this.models.set(uri, parseDoc(text));
  }

  delete(uri: string): void {
    this.texts.delete(uri);
    this.models.delete(uri);
  }

  get(uri: string): CortexModel | undefined {
    return this.models.get(uri);
  }

  text(uri: string): string | undefined {
    return this.texts.get(uri);
  }

  get size(): number { return this.models.size; }

  /** All indexed URIs (open docs + scanned files). */
  uris(): string[] { return [...this.models.keys()]; }

  /** Flat sigil usage index (decl + usages) across all models. */
  sigilIndex(): IndexedSigil[] {
    const out: IndexedSigil[] = [];
    for (const [uri, m] of this.models) {
      for (const s of m.sigils) {
        out.push({ token: `${s.sigil}:${s.inst}`, line: s.line, uri, isDecl: true });
      }
      // usages: every sigil token post-glossary
      const text = this.texts.get(uri) ?? '';
      const lines = text.split(/\r?\n/);
      const re = /([A-Z][A-Z0-9_]*:[A-Za-z_][\w-]*)/g;
      for (let i = m.firstSectionLine < 0 ? lines.length : m.firstSectionLine;
           i < lines.length; i++) {
        const l = lines[i];
        if (l.trimStart().startsWith('#')) { continue; }
        re.lastIndex = 0;
        let mm: RegExpExecArray | null;
        while ((mm = re.exec(l)) !== null) {
          out.push({ token: mm[1], line: i, uri, isDecl: false });
        }
      }
    }
    return out;
  }

  /** Flat section index across all models. */
  sectionIndex(): IndexedSection[] {
    const out: IndexedSection[] = [];
    for (const [uri, m] of this.models) {
      for (const s of m.sections) {
        out.push({ id: s.id, title: s.title, line: s.line, uri });
      }
    }
    return out;
  }
}

/**
 * Safe recursive scan: *.cortex files under `root`, contained,
 * symlink-free, capped. Returns [{fsPath, uri, text}].
 */
export function scanCortexFiles(root: string): {
  fsPath: string; uri: string; text: string;
}[] {
  const out: { fsPath: string; uri: string; text: string }[] = [];
  const rootR = resolve(root);
  const walk = (dir: string): void => {
    if (out.length >= MAX_FILES) { return; }
    let ents;
    try { ents = readdirSync(dir, { withFileTypes: true }); }
    catch { return; }
    for (const e of ents) {
      if (out.length >= MAX_FILES) { return; }
      if (e.isSymbolicLink()) { continue; }      // H-02: never follow
      const p = join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name === 'node_modules' || e.name.startsWith('.')) { continue; }
        walk(p);
      } else if (e.isFile() && e.name.endsWith('.cortex')) {
        const rp = resolve(p);
        if (!(rp === rootR || rp.startsWith(rootR + sep))) { continue; }
        try {
          const st = statSync(rp);
          if (st.size > MAX_BYTES) { continue; } // H-02: size cap
          const text = readFileSync(rp, 'utf8');
          out.push({
            fsPath: rp,
            uri: pathToFileUri(rp),
            text,
          });
        } catch { /* unreadable → skip */ }
      }
    }
  };
  walk(rootR);
  return out;
}
