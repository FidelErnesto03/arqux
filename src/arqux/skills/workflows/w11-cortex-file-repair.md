$0

# -- $0: WORKFLOW W11 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson


IDN:w11{ name:"Cortex File Repair — Backup & Rewrite", purpose:"Repair .cortex files with blocking validation errors (E032/E034/E008) using the BLP-042 backup→rewrite protocol. For files that CODEC-CORTEX cannot auto-repair." }

AXM:backup_first{ Before ANY modification to a broken .cortex file: rename to .cortex.bck. The backup is the safety net. Never modify in-place. }

AXM:no_auto_fix_content{ The migration creates a structurally clean file but does NOT fabricate missing semantic fields (prevention, success, etc.). Historical entries retain their original data. The handler fix prevents new incomplete entries. }


$1: DETECT — Is the file broken?

STP:w11_detect{
  1:"Run `cortex verify --strict <file.cortex>`.",
  2:"Check for codes: E032 (missing required fields), E034 (empty required fields), E008 (duplicate entries).",
  3:"If files have these errors → REPAIR needed.",
  4:"If `cortex verify` passes → no action needed.",
  key_rule:"Do NOT repair files that pass verify. Only files with blocking errors need migration."
}


$2: REPAIR — Backup & Rewrite

STP:w11_repair{
  1:"Backup: `mv <file.cortex> <file.cortex.bck>` — preserve original.",
  2:"Read backup: extract metadata (ARQX:artifact level/name/usage/kind) and all entries.",
  3:"Rewrite: construct a new CortexDocument with clean $0 glossary, $0.1 ARQX:metadata, and all entries from backup.",
  4:"Write: use `cortex.core.writer.write_cortex()` to produce the new file.",
  5:"Verify: `cortex verify --strict <file.cortex>` — passes if structurally valid.",
  6:"If verify fails with structural errors (E001/E002/E015): revert from backup.",
  7:"If verify passes with E032/E034 (historical incompleteness): acceptable — the handler fix prevents new ones.",
  tool:"arqux.state.migrate_cortex_file(path) — single call that performs all steps above.",
  key_rule:"Each backup is preserved indefinitely. The .bck file is not deleted after migration."
}


$3: VERIFY — Post-repair validation

STP:w11_verify{
  1:"Run `cortex verify --strict` on the new file.",
  2:"Confirm no structural errors (E001/E002/E015).",
  3:"E032/E034 on historical entries are noted but NOT reverted — they are pre-existing.",
  4:"Test that new entries from the fixed handler are complete: add a test LNG via identity.record and verify it includes all required fields.",
  key_rule:"The measure of success is not 'zero warnings' — it's 'new entries are clean and handler bypasses are eliminated'."
}


$4: WHEN TO USE vs. W09

STP:w11_vs_w09{
  w09:"Use when a CRUD write fails with E032/E034. The file is live and force=True with auto-repair can complete the write.",
  w11:"Use when existing .cortex files have accumulated many blocking errors over time. The file is structurally corrupt and needs a full backup→rewrite.",
  overlap:"If w09 fails repeatedly on the same file (auto-repair can't fix all entries), escalate to w11 for a full migration.",
  key_rule:"w09 is for immediate write failures. w11 is for batch historical cleanup."
}


$5: Lesson

LNG:blp042_migration{type:"procedimental", cause:"BLP-042 descubrio que 21 archivos .cortex tenian entries incompletos por handlers que escribian sin CODEC-CORTEX", lesson:"El protocolo backup→reescritura (w11) permite migrar archivos dañados a formato CORTEX limpio sin perder datos historicos. Los backups .bck se preservan. El beneficio real no es reparar el pasado sino evitar nuevas entradas rotas con handlers que usan CODEC-CORTEX."}
