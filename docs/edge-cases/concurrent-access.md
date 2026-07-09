# Edge Case: Concurrent file access

## Scenario
Two processes try to write to the same .cortex file simultaneously.

## Expected Behavior
- File locking prevents corruption
- Second writer waits or fails gracefully
- No data loss

## Actual Behavior
- `security.py` implements file locking via `fcntl.flock()`
- `secure_write_cortex()` acquires exclusive lock before writing
- If lock cannot be acquired, operation fails with clear error

## Test Reference
- Test: `tests/test_security.py::test_secure_write_cortex`
- Command: `pytest tests/test_security.py -v`
