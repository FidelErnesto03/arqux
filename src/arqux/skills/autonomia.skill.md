$0

# -- $0: AUTONOMIA SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Feature definition
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# STP   | step       | attrs      | M | Working        | Procedure step
# HDL   | handler    | attrs-pos  | M | Semantic       | Handler reference
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# LOOP  | loop       | attrs      | M | Working        | Autonomous work-cycle entry
# WAKE  | wake       | attrs      | B | Semantic       | Resurrection signal file


$1: PURPOSE

IDN:autonomia{ name:"AUTONOMOUS LOOPS", scope:"Declare, select and guarantee recurrent work cycles that survive interruption (BLP-023). An autonomous loop is a named cycle of phases registered in the project brain; a dispatcher surfaces it at every governed entry point; a watch daemon detects stalls and queues resurrection signals; commands let the Architect and the agents drive the cycle explicitly." }


$2: MODEL — THREE DOMAINS

AXM:three_domains{ The capability lives in three separate places, never mixed:
1. REGISTRY — brain.cortex §18 (LOOPS): LOOP:<name>{phases[], index, state, recurrence, max_stall, expected_duration, next, checkpoint, owner, session, claimed_by, claim_ts, retries, last_run, last_activity}. Declarative state only.
2. TRAIL — the session timelog (.arqux/timelog/SES*.cortex): every transition appends a LOOP event (activate, advance, stall, wake, deactivate, complete, remove). The timelog is the authoritative record of work.
3. TRANSPORT — .arqux/loops/*.wake: client-agnostic resurrection signal. Any governed call by any agent drains it. }

LOOP:states{ armed:"registered, not signalling", active:"dispatchable — surfaced as pending_loop", paused:"silenced by deactivate", stalled:"retries exhausted — manual review", done:"completed", removed:"tombstone (never physically deleted)" }

LOOP:recurrence{ on_bootstrap:"due whenever a governed entry runs", every_bootstrap:"re-fire every dispatch", "cooldown:<n>h":"re-fire only after n hours since last_run", on_heartbeat:"only watch ticks may fire it" }


$3: COMMANDS (loop.*)

STP:lifecycle{ Typical flow: register → activate → (dispatch surfaces pending_loop; agent advances per phase) → complete. Side paths: deactivate/pause, wake/manual push, suggest/recurrence hint, remove/tombstone. }

HDL:loop.register{ signature:"loop.register(name, phases[], recurrence?, max_stall?, expected_duration?, next_?, checkpoint?, owner?, session?, path?)", purpose:"Declare the cycle (state=armed). Mutating.", mutating:true }
HDL:loop.list{ signature:"loop.list(path?)", purpose:"List registry entries (tombstones excluded). Read-only.", readonly:true }
HDL:loop.activate{ signature:"loop.activate(name, path?)", purpose:"armed|paused|stalled → active; resets retries, seals last_activity.", mutating:true }
HDL:loop.deactivate{ signature:"loop.deactivate(name, path?)", purpose:"active → paused.", mutating:true }
HDL:loop.advance{ signature:"loop.advance(name, checkpoint?, next_?, path?)", purpose:"index+1; checkpoint persisted in §18, progress event appended to timelog. Phases are never skipped.", mutating:true }
HDL:loop.complete{ signature:"loop.complete(name, summary?, path?)", purpose:"active → done.", mutating:true }
HDL:loop.remove{ signature:"loop.remove(name, path?)", purpose:"Tombstone the entry (requires deactivate first if active). Single-writer: an in-flight advance cannot resurrect it.", mutating:true }
HDL:loop.suggest{ signature:"loop.suggest(name?, path?)", purpose:"Recurrence suggestion from the observed pattern. Read-only.", readonly:true }
HDL:loop.wake{ signature:"loop.wake(name, checkpoint?, path?)", purpose:"Queue a WAKE manually — next governed call surfaces the loop.", mutating:true }

HDL:cli.loop_watch{ signature:"arqux loop-watch --path <root> [--interval s] [--once]", purpose:"The watch daemon: own heartbeat (.arqux/loops/.watch), stall detection, atomic WAKE queueing, retries→stalled. Started by `arqux serve` or standalone; optional but recommended while autonomous loops run." }


$4: RESURRECTION CONTRACT

STP:stall_cycle{ 1_loop_dies:"Loop stops mid-execution (compression, LLM error, dropped turn). last_activity ages.",
  2_watch_detects:"tick computes budget = expected_duration(phase) else max_stall — elapsed beyond budget → stall.",
  3_wake_queued:"Watch writes .arqux/loops/<name>.wake atomically (tmp+rename), retries+1, timelog event.",
  4_drain:"Next governed call — any agent, any client, any session — drains the mailbox and returns pending_loop{loop,phase,next,reason:'stall',checkpoint}.",
  5_resume:"The receiving agent resumes from checkpoint; it does not need the Architect's word.",
  6_exhausted:"retries > max_retries (default 3, backoff retries*120s) → state=stalled + report. No infinite resurrection." }

AXM:client_agnostic{ The signal never targets a specific client: the mailbox is a governed file and the dispatcher is the delivery. Whoever shows up continues the loop. If no one ever calls, the WAKE waits — but any governed stimulus resurrects it. }


$5: HARD LIMITS

LIM:fail_silent{ severity:"blocking", limit:"The dispatcher NEVER breaks the host handler: all internal errors return None and the main response is delivered intact (V-01)." }
LIM:atomic_wake{ severity:"blocking", limit:"WAKE writes are tmp+rename atomic. Corrupt entries are quarantined, reported, and draining continues (V-03)." }
LIM:text_validation{ severity:"blocking", limit:"checkpoint/next_ are instructions aimed at a future agent: schema-validated, ≤500 chars, control chars stripped (V-04)." }
LIM:stall_budget{ severity:"blocking", limit:"Stall detection respects phase budget (expected_duration wins); max_stall is the absolute ceiling — never flag a legitimately long phase (V-05)." }
LIM:single_writer{ severity:"blocking", limit:"Loop entries mutate only via loop.* commands (crud_update force); remove is a tombstone, not a delete (V-06)." }
LIM:no_progress_in_brain{ severity:"blocking", limit:"Progress events go to the session timelog, never into brain.cortex — §18 holds the registry only." }
LIM:exclusive_delivery{ severity:"blocking", limit:"Same-project multi-execution: delivery is exclusive via lease — claimed_by/claim_ts stamped on dispatch (TTL 600s); a fresh claim by another execution defers the candidate and mutating commands return CLAIMED_BY_OTHER. A dead claimant never blocks: the lease expires and the next caller takes over. Wake drains are claimed atomically (O_EXCL marker, 120s stale self-heal). Outside the project, loops are fully isolated — separate brains, mailboxes, timelogs, watches." }


$6: LEGACY COMPATIBILITY

AXM:wrk_fallback{ When §LOOPS is empty, the dispatcher falls back to the legacy WRK:current{loop,phase,next} marker so existing recovery flows keep working. The compat helper _pending_autonomous_loop preserves its original {loop,phase,next} return shape. }
