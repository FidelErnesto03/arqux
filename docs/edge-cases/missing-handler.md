# Edge Case: Missing handler

## Scenario
CLI tries to call a handler that is not registered in the REGISTRY.

## Expected Behavior
- CLI displays "Unknown handler" error
- Lists available handlers
- No crash

## Actual Behavior
- `cli.py:_call_handler()` checks REGISTRY before dispatch
- Returns error with handler name and available list
- `cmd_call` prints error and exits cleanly

## Test Reference
- Test: `tests/test_cli.py::test_call_unknown_handler`
- Command: `pytest tests/test_cli.py -v`
