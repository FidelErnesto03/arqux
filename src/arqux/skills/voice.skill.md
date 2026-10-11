---
skill_id: arqux-voice
name: arqux.voice
version: "1.3.0"
status: active
kind: extension
usage: skill
layer: 3
blp_ref: BLP-015
---

# Skill: arqux.voice — harness-agnostic voice participation

## §1: IDENTITY

IDN:voice{name:"arqux.voice", purpose:"Give any MCP-capable agent ears, a
voice, and governed meeting notes over a fully local audio pipeline",
version:"1.3.0", status:"active", blp:"BLP-015"}

## §2: WHAT IT IS

`arqux-voice` is an MCP stdio server shipping 10 tools. Any harness that
speaks MCP can listen to the room, speak when addressed, and persist a
per-meeting Markdown transcript — with zero cloud dependencies:

capture (pw-cat) -> Silero VAD v5 (onnx) -> smart-turn v3 EOT
-> faster-whisper (CPU int8) -> echo guard / voice commands / gate
-> [the agent, via MCP] -> Kokoro/Piper TTS -> pw-play

Two modes: solo (mic only, gate always, speakers) and meet (mic +
sink monitor, gate mention, VirtualMic injection — no meeting bot).

Listening states: `on` · `silent` (passive: notes only, never replies) ·
`wake` (soft-suspended: nothing stored, wake phrase only) · `off`
(capture killed; reactivate with meeting_stop + meeting_start).

## §3: MOUNT

```json
{"mcpServers": {"arqux-voice":
  {"command": "arqux", "args": ["voice-serve"]}}}
```

Requires `pip install "arqux[voice]"` and models under
`$ARQUX_VOICE_MODELS`, `<repo>/.voice/models`, or
`~/.local/share/arqux/voice/models`. Verify with `arqux voice-doctor`.

Input device: `$ARQUX_VOICE_MIC` selects the capture device (node.name,
id, or a substring of its description). Unset → the WirePlumber default
source. A machine may expose several mics (internal, DMIC, jack,
Bluetooth) — list them with `voice_devices` or `arqux voice-doctor`.

## §4: TOOLS

| tool               | purpose                                                        |
|--------------------|----------------------------------------------------------------|
| voice_listen       | 1:1 long-poll next utterance (auto-starts solo session)         |
| voice_say          | 1:1 speak text aloud                                           |
| meeting_start      | begin session {name, mode, agent, lang, announce, patterns, voice, mic} — prewarms models in background; agent selects its identity voice; `mic` overrides `$ARQUX_VOICE_MIC` for the session |
| meeting_listen     | long-poll next *addressed* utterance {speaker,text,ts,match}   |
| meeting_say        | speak into the call (VirtualMic) or speakers (solo); interrupt=true cuts current playback |
| meeting_transcript | incremental transcript read {tail_n, since_ts}                 |
| meeting_note       | append structured note [decision\|action\|note]                  |
| meeting_status     | uptime, entries, pending queue, listening state, virtual-mic state, prewarm |
| meeting_stop       | finalize transcript, release devices, destroy VirtualMic       |
| voice_devices      | list input devices {id,name,description,default,level} + live probe |
| voice_configure    | retune gate patterns / mode at runtime                          |

`*_listen` long-polls up to `timeout_s` (default 20, cap 120).
Non-addressed speech is still transcribed — it is simply never queued.

## §4c: INPUT DEVICE SELECTION

Three levels, all simple to change (no code edits):

1. Persistent — `$ARQUX_VOICE_MIC` (e.g. in the harness MCP config
   `environment`). Accepts node.name, id, or description substring.
2. Per session — `meeting_start(mic="<name|id|substring>")` overrides 1.
3. Discovery — `voice_devices` (or `arqux voice-doctor`) lists every
   `Audio/Source` with a live level, so the choice is data-driven.

Resolution order: exact id → exact node.name → case-insensitive
substring of name/description → pass-through as a raw pw-cat target.
Unknown selectors pass through unchanged.

DC-block: `PcmSource.read` removes the per-chunk mean, neutralising the
constant DC bias some DMIC/ALSA paths emit (e.g. ASUS ACP6x, +0.136).
Without it the DC suppresses Silero VAD (0 segments); with it, VAD+STT
work on any device. The fix is device-agnostic — switching mics keeps it.

Runtime switch & health: `voice_configure(mic=...)` reopens the capture on
a new device mid-session (no restart). `meeting_status` and any `*_listen`
timeout report `mic_health` {device, alive, state(ok|recovering|dead),
ac_rms, dc, vad_fires, last_voice_ago_s, recoveries}. A watchdog reopens the
capture — advancing a device fallback chain — when the process dies or AC
stays at digital silence. It NEVER restarts system services; it surfaces a
hint instead (e.g. restart WirePlumber with authorization).

Escalation ladder (no voice detected): (1) preventive reopen after 90 s;
(2) opt-in system recovery — `$ARQUX_VOICE_AUTO_RECOVER=wireplumber`
authorizes the watchdog to restart the user WirePlumber service (the only
known cure for the intermittently stuck DMIC ACP6x) after 180 s, with a
300 s cooldown. Default OFF: unset means the system only advises.

## §4b: VOICES, CADENCE & FLUIDITY (as-built)

- Identity voices (neutral latino, Kokoro-82M ONNX): alfred=em_blend_alfred
  (72/28 alex+santa, length_scale 1.10), heimdall=em_santa@1.05,
  jarvis=em_blend_jarvis (55/45, @0.92), seshat=ef_dora. `meeting_start(voice=...)`
  overrides: "kokoro:em_alex" or a bare Piper voice name.
- `meeting_start` prewarms STT+TTS in background — no cold start.
- EOT is two-stage: VAD closes at 650 ms silence, smart-turn v3 decides
  complete vs incomplete; incomplete segments merge (cap 30 s).
- TTS cadence: replies <=150 chars are fully pre-synthesized before any
  sound (ARMED mode — zero internal gaps/cuts); longer replies stream with
  a 110-char armed lead + deep look-ahead. Sentences merge up to 110 chars
  because Kokoro per-call overhead punishes short chunks (RTF 1.65 @18ch
  vs 1.12 @69ch). Kokoro RTF on CPU ~1.02-1.5 (slower than real-time):
  prefer SHORT voice replies for gap-free speech.
- Echo guard: the mic hears the agent's own TTS tail; utterances
  containing or >0.72-similar to the last 6 agent texts are dropped
  before the command router (prevents self-interruption).
- Barge-in requires the name ("Alfred, para") — prevents false cuts.
- `meeting_say(interrupt=true)` kills active playback immediately.

## §5: OPERATING PROTOCOL

AXM:silence_default{In meet mode the agent MUST NOT speak unless an
utterance was returned by meeting_listen (i.e. explicitly addressed).}
AXM:gate_integrity{Never widen the gate (voice_configure mode=always)
inside a live meeting without the Architect's explicit instruction.}
WK:one_to_one{procedure:(a)loop voice_listen->reason->voice_say
(b)meeting_stop on farewell or inactivity}
WK:meet{procedure:(a)meeting_start(mode=meet) — announce defaults ON
(b)loop: meeting_listen->reason->meeting_say; meeting_note for
decisions/actions (c)meeting_stop when the call ends}
WK:transcript{The .md lives in $ARQUX_VOICE_MEETINGS, else
~/workspace/meetings/ when ~/workspace exists, else
~/.local/share/arqux/voice/meetings/ — YYYY-MM-DD_<slug>.md}

## §5b: VOICE COMMANDS (contract for any harness)

Pipeline-level commands run BEFORE the gate and queueing — they work even
while the agent is speaking. Matching is accent-insensitive, lowercase-
normalized and stem-tolerant (STT garbles like "Renuda" are accepted).

| said (es)                              | action                                        |
|----------------------------------------|-----------------------------------------------|
| "Alfred, para" / "silencio" / "detente" | kill TTS playback now (barge-in)             |
| "suspende la escucha" / "pausa la escucha" | SOFT suspend: wake-phrase listening only — no transcription, no storage; voice-reactivable |
| "reanuda" / "continúa" / "sigue" (+"la escucha") | voice-reactivate from soft suspension |
| "escucha en silencio" / "modo silencio" / "solo escucha" | PASSIVE: transcribe + notes, never reply |
| "ya puedes responder" / "responde otra vez" / "sal del silencio" | leave passive mode |
| "apaga el micrófono"                   | HARD off: capture killed; reactivate via meeting_stop + meeting_start |
| "borra lo último"                      | redact last 2 non-system entries ([redactado])|
| "cancela lo pendiente"                 | drop queued utterances                        |
| "Alfred, sube/baja el volumen"         | wpctl sink volume ±10%                        |
| "Alfred, más despacio / más rápido"    | TTS length_scale ×1.25 / ×0.8 (clamp 0.6-2.0)|

Harness-interpreted: "repite", "estado", "resumen", "anota/decisión/tarea: X",
"¿me escuchas?", "¿sigues ahí?", "termina" / "cierra la sesión".

Privacy: soft suspension processes audio in RAM only for the wake phrase;
hard off processes nothing; passive mode stores the transcript but never
speaks.

## §6: ECHO & FEEDBACK SAFETY

- Monitor channel is muted while TTS plays (tts_active guard).
- The mic channel CAN capture the agent's own TTS tail — `_is_echo()`
drops it (containment or >0.72 similarity vs recent agent texts).
- Barge-in requires the name to avoid false cuts.
- The real mic is mixed into VirtualSpeaker so remote participants hear
  BOTH the human and the agent over VirtualMic.

## §7: TROUBLESHOOTING

| symptom                        | action                                        |
|--------------------------------|-----------------------------------------------|
| no utterances returned         | check mic_health in meeting_status: state/alive/ac_rms; if ac_rms≈0 or state=dead, switch device `voice_configure(mic=...)`; if the DMIC is DC-stuck, restart WirePlumber (with authorization) |
| capture dead / silent           | watchdog auto-reopens & falls back; read recoveries|
| remote can't hear the agent    | confirm "VirtualMic" selected in the call app |
| agent hears itself / echo      | echo guard drops similar text; check §6       |
| transcript missing             | check $ARQUX_VOICE_MEETINGS writability       |
| duplicate VirtualMic nodes     | provision() self-cleans stale nodes           |
| choppy STT / missing words     | capture must stream real-time (bufsize=0)     |
| long pauses / cut audio        | keep replies <=150 chars (ARMED mode); check  |
|                                | echo guard and barge-in name requirement      |
| command not obeyed             | check listening state (silent/wake/off) and   |
|                                | STT wording; stems are tolerated              |

## §8: GOVERNANCE

Built under BLP-015 (CYCLE-12). Transcripts are evidence artifacts;
decisions/action items SHOULD be mirrored into governance via
`meeting_note` + the host harness's own evidence handlers.