# Edge Case: Empty brain.cortex

## Scenario
A workspace is initialized but brain.cortex has no entries (empty file or missing sections).

## Expected Behavior
- `sync_brain()` creates default entries (IDN, FCS, OBJ, WRK, DOM:arqux)
- No crash or exception
- Brain becomes usable after sync

## Actual Behavior
- `_build_brain_doc()` generates a complete brain.cortex template with all required sections
- `_sync_meta_brain()` populates meta-brain with DOM:arqux entry
- If brain.cortex exists but is empty, sync overwrites with the template

## Test Reference
- Test: `tests/test_sync_brain.py::test_sync_brain_updates_wrk`
- Command: `pytest tests/test_sync_brain.py -v`
