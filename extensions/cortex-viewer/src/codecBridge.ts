/**
 * codecBridge.ts — secure adapter to the codec-cortex toolchain.
 *
 * SEC-01: no child_process exec family, no shell:true. Every invocation uses
 * spawn() with an argument array and pipes the document via stdin (`-`
 * file argument), which eliminates command injection.
 *
 * Resolution follows the $3 RUNTIME_BRIDGE contract: Rust → Go → Python
 * → Node, each with its own timeout; the last fallback surfaces an
 * install notification payload instead of a runtime.
 */
import { spawn } from 'child_process';

export type CodecCommand =
  | 'parse'
  | 'validate'
  | 'hash'
  | 'to-hcortex'
  | 'from-hcortex'
  | 'loss-report'
  | 'canonicalize';

export interface CodecResult {
  ok: boolean;
  exitCode: number | null;
  stdout: string;
  stderr: string;
  runtime: string;
  /** Infra-level failure (spawn error / timeout / usage error). */
  infraError?: string;
  elapsedMs: number;
}

interface RuntimeSpec {
  priority: number;
  name: string;
  command: string;
  baseArgs: string[];
  timeoutMs: number;
  /** Subcommand used for validation when `validate` is unavailable. */
  validateSub: string;
}

const RUNTIMES: RuntimeSpec[] = [
  { priority: 1, name: 'cortex',                 command: 'cortex',            baseArgs: [],                    timeoutMs: 1500, validateSub: 'validate' },
  { priority: 2, name: 'codec-cortex',           command: 'codec-cortex',      baseArgs: [],                    timeoutMs: 1500, validateSub: 'validate' },
  { priority: 3, name: 'python3 -m codec_cortex', command: 'python3',          baseArgs: ['-m', 'codec_cortex'], timeoutMs: 2500, validateSub: 'validate' },
  { priority: 4, name: 'codec-cortex-node',      command: 'codec-cortex-node', baseArgs: [],                    timeoutMs: 2000, validateSub: 'parse' },
];

const PROBE_DOC =
  '$0:KERNEL\n' +
  '$0:format{cortex:1.0,encoding:UTF-8}\n' +
  '$1: PROBE\n';

function runOnce(
  spec: RuntimeSpec,
  subcommand: string,
  stdinText: string,
  timeoutMs: number
): Promise<CodecResult> {
  return new Promise((resolve) => {
    const start = Date.now();
    let child;
    try {
      child = spawn(spec.command, [...spec.baseArgs, subcommand, '-'], {
        shell: false,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (err) {
      resolve({
        ok: false,
        exitCode: null,
        stdout: '',
        stderr: '',
        runtime: spec.name,
        infraError: `spawn failed: ${String(err)}`,
        elapsedMs: Date.now() - start,
      });
      return;
    }

    let stdout = '';
    let stderr = '';
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) { return; }
      settled = true;
      child.kill('SIGKILL');
      resolve({
        ok: false,
        exitCode: null,
        stdout,
        stderr,
        runtime: spec.name,
        infraError: `timeout after ${timeoutMs}ms`,
        elapsedMs: Date.now() - start,
      });
    }, timeoutMs);

    child.stdout.on('data', (d: Buffer) => { stdout += d.toString('utf8'); });
    child.stderr.on('data', (d: Buffer) => { stderr += d.toString('utf8'); });

    child.on('error', (err) => {
      if (settled) { return; }
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: false,
        exitCode: null,
        stdout,
        stderr,
        runtime: spec.name,
        infraError: `spawn error: ${err.message}`,
        elapsedMs: Date.now() - start,
      });
    });

    child.on('close', (code) => {
      if (settled) { return; }
      settled = true;
      clearTimeout(timer);
      resolve({
        ok: code === 0,
        exitCode: code,
        stdout,
        stderr,
        runtime: spec.name,
        elapsedMs: Date.now() - start,
      });
    });

    child.stdin.on('error', () => { /* EPIPE on early exit — close event settles */ });
    child.stdin.write(stdinText);
    child.stdin.end();
  });
}

function isInfraFailure(res: CodecResult): boolean {
  if (res.infraError) { return true; }
  // exit 2 = CLI usage error across all surfaces → try next runtime.
  return res.exitCode === 2;
}

export class CodecBridge {
  private chain: RuntimeSpec[] = [];
  private resolving: Promise<RuntimeSpec[]> | null = null;
  private customCommand = '';

  /** cortex.toolchainPath override — tried before the priority chain. */
  setCustomCommand(cmd: string): void {
    const v = (cmd ?? '').trim();
    if (v !== this.customCommand) {
      this.customCommand = v;
      this.reset();
    }
  }

  /** Probe every runtime in contract order; keep the reachable chain. */
  async resolve(): Promise<RuntimeSpec[]> {
    if (this.chain.length > 0) { return this.chain; }
    if (this.resolving) { return this.resolving; }

    this.resolving = (async () => {
      const chain: RuntimeSpec[] = [];
      const specs: RuntimeSpec[] = this.customCommand
        ? [{ priority: 0, name: this.customCommand, command: this.customCommand, baseArgs: [], timeoutMs: 2000, validateSub: 'validate' }, ...RUNTIMES]
        : RUNTIMES;
      for (const spec of specs) {
        const probe = await runOnce(spec, spec.validateSub, PROBE_DOC, spec.timeoutMs);
        if (!isInfraFailure(probe) && probe.exitCode === 0) {
          chain.push(spec);
        }
      }
      this.chain = chain;
      this.resolving = null;
      return chain;
    })();
    return this.resolving;
  }

  /** Name of the first resolved runtime, or null if none. */
  async activeRuntime(): Promise<string | null> {
    const chain = await this.resolve();
    return chain.length > 0 ? chain[0].name : null;
  }

  /** Invalidate the cached resolution (e.g. after ENOENT on a cached runtime). */
  reset(): void {
    this.chain = [];
    this.resolving = null;
  }

  /**
   * Invoke a codec subcommand with the document piped via stdin.
   * Walks the resolved chain: infra failures (spawn error, timeout,
   * usage error) fall through to the next runtime; codec results
   * (exit 0 or 1) are returned as-is.
   */
  async invoke(command: CodecCommand, stdinText: string): Promise<CodecResult> {
    let chain = await this.resolve();
    if (chain.length === 0) {
      return {
        ok: false,
        exitCode: null,
        stdout: '',
        stderr: '',
        runtime: 'none',
        infraError: 'no codec-cortex toolchain resolved (pip install codec-cortex)',
        elapsedMs: 0,
      };
    }

    let lastInfra: CodecResult | null = null;
    for (let i = 0; i < chain.length; i++) {
      const spec = chain[i];
      const sub = command === 'validate' ? spec.validateSub : command;
      const res = await runOnce(spec, sub, stdinText, spec.timeoutMs);
      if (!isInfraFailure(res)) {
        // Demote a runtime that produced a codec-level result on retry;
        // keep resolution order stable otherwise.
        if (i > 0) { this.chain = chain.slice(i).concat(chain.slice(0, i)); }
        return res;
      }
      lastInfra = res;
    }

    // Whole chain failed at infra level: drop cache so next call re-probes.
    this.chain = [];
    return lastInfra ?? {
      ok: false, exitCode: null, stdout: '', stderr: '',
      runtime: 'none', infraError: 'toolchain chain exhausted', elapsedMs: 0,
    };
  }

  /** Convenience: run all four read pipelines in parallel. */
  async inspect(cortexText: string): Promise<{
    validate: CodecResult;
    hcortex: CodecResult;
    hash: CodecResult;
    loss: CodecResult;
  }> {
    const [validate, hcortex, hash, loss] = await Promise.all([
      this.invoke('validate', cortexText),
      this.invoke('to-hcortex', cortexText),
      this.invoke('hash', cortexText),
      this.invoke('loss-report', cortexText),
    ]);
    return { validate, hcortex, hash, loss };
  }
}

export interface LossReport {
  reversible: boolean;
  losses: unknown[];
  warnings: unknown[];
  coverage?: { complete: boolean };
  schema_version?: string;
  [key: string]: unknown;
}

export function parseLossReport(stdout: string): LossReport | null {
  try {
    const json = JSON.parse(stdout) as LossReport;
    if (typeof json.reversible !== 'boolean' || !Array.isArray(json.losses)) {
      return null;
    }
    return json;
  } catch {
    return null;
  }
}

export function parseHash(stdout: string): string | null {
  const m = stdout.match(/sha256:([0-9a-f]{64})/);
  return m ? m[1] : null;
}

/** Install-notification payload for the priority-4 fallback. */
export const INSTALL_HINT = 'pip install codec-cortex';
