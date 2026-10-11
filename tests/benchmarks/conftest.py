"""Options for the benchmark suite.

``pytest_addoption`` only runs for plugins and conftest files, never for test
modules — registering the flag inside ``test_memory_benchmark.py`` silently did
nothing and the run failed with "no option named '--publish-benchmark'".

The benchmark measures on every run but writes the release artifact only when
publishing is requested explicitly, so that ``pytest tests/benchmarks`` cannot
overwrite versioned release evidence with timings from an arbitrary machine.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--publish-benchmark",
        action="store_true",
        default=False,
        dest="publish_benchmark",
        help="write docs/release/benchmark-*.json instead of only measuring",
    )
