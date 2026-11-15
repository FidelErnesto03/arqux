"""Safety and correctness tests for the policy condition DSL (BLP-003)."""
from __future__ import annotations

import pytest

from arqux.core.learning.algorithms.conditions import make_evaluator, parse_condition


def test_parse_simple_equality():
    c = parse_condition('kind == "behavioral"')
    assert c.evaluate({"kind": "behavioral"}) is True
    assert c.evaluate({"kind": "other"}) is False


def test_parse_in_list():
    c = parse_condition('sigil in ["SES", "LNG"]')
    assert c.evaluate({"sigil": "SES"}) is True
    assert c.evaluate({"sigil": "KNW"}) is False


def test_parse_and_or_not():
    c = parse_condition('a == 1 and not (b == 2)')
    assert c.evaluate({"a": 1, "b": 3}) is True
    assert c.evaluate({"a": 1, "b": 2}) is False


def test_fail_closed_on_unknown_tokens():
    with pytest.raises(ValueError):
        parse_condition("__import__('os').system('id')")


def test_fail_closed_on_lambda():
    with pytest.raises(ValueError):
        parse_condition("lambda: 1")


def test_evaluator_fail_closed_at_runtime():
    ev = make_evaluator('x == 1')
    assert ev({"x": 1}) is True
    assert ev(None) is False


def test_no_eval_exec_compile_in_module():
    import inspect

    import arqux.core.learning.algorithms.conditions as mod

    src = inspect.getsource(mod)
    # Guard against dynamic-evaluation primitives in the implementation.
    # Only builtin CALL sites matter: eval/exec/compile. "re.compile" is the
    # stdlib regex compiler (safe, required) so we strip it before checking.
    sanitized = src.replace("re.compile(", "re.RE_COMPILE(")
    forbidden_calls = ["ev" + "al(", "ex" + "ec(", "com" + "pile("]
    for token in forbidden_calls:
        assert token not in sanitized, f"forbidden call token found: {token}"
    # No dynamic AST module import/execution.
    assert ("import " + "ast") not in src
    assert ("__import__(") not in src
