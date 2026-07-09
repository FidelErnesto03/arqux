# Edge Case: Missing identity file

## Scenario
A handler tries to read an identity file (e.g., `identities/test-governor.cortex`) that doesn't exist.

## Expected Behavior
- Handler returns `OUT-ERROR code=NOT_FOUND` with descriptive message
- No unhandled exception
- System continues operating

## Actual Behavior
- `cortex.entry.get()` returns NOT_FOUND error
- `record_lesson_handler` returns NOT_FOUND when identity file missing
- Error is logged but doesn't crash the process

## Test Reference
- Test: `tests/test_learn_trigger.py::test_learn_auto_trigger_on_record`
- Command: `pytest tests/test_learn_trigger.py -v`
