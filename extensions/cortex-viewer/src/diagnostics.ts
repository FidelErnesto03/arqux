/**
 * diagnostics.ts — map codec-cortex error output to editor diagnostics.
 *
 * All surfaces emit errors as `CODE @ line:col — message` (Python adds a
 * `ParseError:`/`Error:` prefix). Codec lines are 1-based, columns 0-based.
 * Pure module: no `vscode` import — conversion to vscode.Diagnostic
 * happens in extension.ts.
 */

export interface CodecDiagnostic {
  code: string;
  /** 0-based line (converted from codec's 1-based). */
  line: number;
  /** 0-based column. */
  col: number;
  severity: 'error' | 'warning';
  message: string;
}

const ERROR_RE = /([A-Z]\d{3}_[A-Z0-9_]+)\s*@\s*(\d+):(\d+)\s*[—–-]\s*(.+?)\s*$/;

export function parseCodecErrors(stderr: string): CodecDiagnostic[] {
  const out: CodecDiagnostic[] = [];
  for (const rawLine of stderr.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) { continue; }
    const m = line.match(ERROR_RE);
    if (!m) { continue; }
    const [, code, lineNo, colNo, message] = m;
    const severity: 'error' | 'warning' =
      /^warning\b/i.test(line) || code.startsWith('W') ? 'warning' : 'error';
    out.push({
      code,
      line: Math.max(0, parseInt(lineNo, 10) - 1),
      col: Math.max(0, parseInt(colNo, 10)),
      severity,
      message: `${code}: ${message}`,
    });
  }
  return out;
}

/**
 * Section lookup for scroll sync: find the innermost `$N`/`$N.M` section
 * header at or above `line` (0-based). Returns the section id ("3" or
 * "3.2"), or null when the cursor sits before the first section.
 */
export function sectionAtLine(text: string, line: number): string | null {
  const lines = text.split(/\r?\n/);
  const re = /^\$(\d+(?:\.\d+)?)\s*:/;
  for (let i = Math.min(line, lines.length - 1); i >= 0; i--) {
    const m = lines[i].match(re);
    if (m && m[1] !== '0') { return m[1]; }
    if (m && m[1] === '0') { return null; } // inside kernel/glossary
  }
  return null;
}

/** Line index (0-based) of a `$N:` section header, or -1. */
export function lineOfSection(text: string, sectionId: string): number {
  const re = new RegExp(`^\\$${sectionId.replace('.', '\\.')}\\s*:`);
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    if (re.test(lines[i])) { return i; }
  }
  return -1;
}
