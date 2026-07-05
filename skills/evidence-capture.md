# evidence-capture — Record evidence efficiently without bloating tokens

## When to use
- You are an executor completing a task (`task.complete`).
- You are an executor hitting a blocker (`task.fail`).
- You want to record a decision or intermediate artifact.

## What to do

1. **Pick the right `kind`.**
   - `note` — short progress note (1-2 sentences).
   - `artifact` — link to a produced artifact (file path, URL, commit hash).
   - `decision` — a decision was made; record the rationale.
   - `metric` — a measurable value (coverage %, latency, etc.).
   - `blocker` — something is blocking progress; record the cause.

2. **Keep payloads short.**
   The `payload` field is a string. Aim for ≤200 characters. If you need
   more detail, link to a file: `payload="see src/api/health.py#L42"`.

3. **Use CORTEX-OUT in the payload.**
   Format metrics as `key=value` pairs:
   ```
   payload="coverage=87% tests=12/14 failing=0"
   ```

4. **All evidence goes to the brain's # PULSE section.**
   There is no separate `pulse.jsonl` file. Every `evidence.record` call
   appends to the project brain's `# PULSE` section. This keeps the
   project mind in one place — every agent bound to the project sees
   the same evidence trail.

5. **Record evidence at meaningful moments, not on every step.**
   - When you start a task (kind=note).
   - When you hit a decision point (kind=decision).
   - When you produce an artifact (kind=artifact).
   - When you complete (kind=artifact or kind=metric).
   - When you block (kind=blocker).

## Examples

```
evidence.record task_id="T-001" kind="note"     payload="started Redis integration"
evidence.record task_id="T-001" kind="decision" payload="using redis-py 5.x for async support"
evidence.record task_id="T-001" kind="artifact" payload="src/api/health.py@a1b2c3d"
evidence.record task_id="T-001" kind="metric"   payload="coverage=87% tests=12/14 failing=0"
evidence.record task_id="T-001" kind="blocker"  payload="Redis unavailable on staging"
```

## Anti-patterns

- ❌ Recording evidence after every line of code (too noisy).
- ❌ Using `kind=note` for everything (loses signal).
- ❌ Long prose payloads (wastes tokens — link to a file instead).
- ❌ Trying to write to a `pulse.jsonl` file directly (it doesn't exist;
  use the `evidence.record` handler).

## References
- `AGENTS.md` §8 (CORTEX-OUT output protocol)
- `AGENTS.md` §4 (evidence.* handlers)
- `AGENTS.md` §9 (The project brain — PULSE section)
- `AGENTS.md` §13 (MCP is the only governance interface)
