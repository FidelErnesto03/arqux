# Edge Case: Invalid cortex syntax

## Scenario
A .cortex file has syntax errors (malformed entries, missing sections, invalid sigils).

## Expected Behavior
- `cortex.verify()` detects and reports errors
- Invalid entries are flagged but don't crash the parser
- System can still read valid portions

## Actual Behavior
- CODEC-CORTEX parser validates syntax strictly
- Returns structured error list with line numbers
- `cortex.verify` handler returns verification report

## Test Reference
- Test: `tests/test_security.py::test_verify_cortex_missing_header_strict`
- Command: `pytest tests/test_security.py -v`
