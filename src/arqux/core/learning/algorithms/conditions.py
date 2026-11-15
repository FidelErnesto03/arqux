"""Safe condition DSL for learning policies (BLP-003).

The policy evaluator must NEVER execute dynamic code. This module implements a
small, closed DSL: parse -> evaluate over a plain dict context.

Supported forms (conservative subset, fail-closed):
  - Equality/inequality: ``key == "value"``, ``key != 3``
  - Membership: ``key in ["a","b"]``, ``key not in ["x"]``
  - Boolean ops: ``and``, ``or`` (left-to-right, no precedence surprises)
  - Unary: ``not expr``
  - Literals: strings, ints, floats, bools (true/false), null/none, lists

Anything else raises ``ValueError`` (fail-closed).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Invariant: no dynamic evaluation (eval/exec/compile) and no AST module.



@dataclass(frozen=True)
class Clause:
    op: str
    left: Any = None
    right: Any = None

    def evaluate(self, ctx: dict[str, Any]) -> bool:
        if self.op == "eq":
            return _resolve(self.left, ctx) == _resolve(self.right, ctx)
        if self.op == "ne":
            return _resolve(self.left, ctx) != _resolve(self.right, ctx)
        if self.op == "in":
            container = _resolve(self.right, ctx)
            try:
                return _resolve(self.left, ctx) in container
            except Exception:  # noqa: BLE001
                return False
        if self.op == "not_in":
            container = _resolve(self.right, ctx)
            try:
                return _resolve(self.left, ctx) not in container
            except Exception:  # noqa: BLE001
                return False
        if self.op == "and":
            return bool(self.left.evaluate(ctx) and self.right.evaluate(ctx))
        if self.op == "or":
            return bool(self.left.evaluate(ctx) or self.right.evaluate(ctx))
        if self.op == "not":
            return not bool(self.left.evaluate(ctx))
        raise ValueError(f"unsupported op: {self.op}")


@dataclass(frozen=True)
class Condition:
    source: str
    clause: Clause

    def evaluate(self, ctx: dict[str, Any] | None = None) -> bool:
        return self.clause.evaluate(ctx or {})


_TOKEN_RE = re.compile(
    r"\s*(==|!=|\bnot\s+in\b|\bin\b|\band\b|\bor\b|\bnot\b|\(|\)|\[|\]|,|"
    r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|[A-Za-z_][A-Za-z0-9_.]*|"
    r"-?\d+(?:\.\d+)?|.)"
)


def _tokenize(expr: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(expr):
        m = _TOKEN_RE.match(expr, i)
        if not m:
            raise ValueError(f"cannot tokenize: {expr[i:]!r}")
        tok = m.group(1)
        if tok.strip():
            tokens.append(tok.strip())
        i = m.end()
    return tokens


def _parse_literal(tok: str) -> Any:
    if tok.startswith(("\"", "'")) and tok.endswith(("\"", "'")):
        return tok[1:-1]
    low = tok.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    if re.fullmatch(r"-?\d+\.\d+", tok):
        return float(tok)
    return ("var", tok)


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def eat(self, expected: str | None = None) -> str:
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of expression")
        if expected is not None and tok.lower() != expected.lower():
            raise ValueError(f"expected {expected!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse(self) -> Clause:
        node = self.parse_or()
        if self.peek() is not None:
            raise ValueError(f"unexpected token: {self.peek()!r}")
        return node

    def parse_or(self) -> Clause:
        node = self.parse_and()
        while self.peek() and self.peek().lower() == "or":
            self.eat()
            node = Clause("or", node, self.parse_and())
        return node

    def parse_and(self) -> Clause:
        node = self.parse_not()
        while self.peek() and self.peek().lower() == "and":
            self.eat()
            node = Clause("and", node, self.parse_not())
        return node

    def parse_not(self) -> Clause:
        if self.peek() and self.peek().lower() == "not" and (
            self.i + 1 >= len(self.tokens) or self.tokens[self.i + 1].lower() != "in"
        ):
            self.eat("not")
            return Clause("not", self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self) -> Clause:
        if self.peek() == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        left = self.parse_atom()
        tok = self.peek()
        if tok == "==":
            self.eat("==")
            return Clause("eq", left, self.parse_atom())
        if tok == "!=":
            self.eat("!=")
            return Clause("ne", left, self.parse_atom())
        if tok and tok.lower() == "in":
            self.eat()
            return Clause("in", left, self.parse_atom())
        if tok and tok.lower() == "not":
            self.eat("not")
            self.eat("in")
            return Clause("not_in", left, self.parse_atom())
        # bare truthiness of a variable/literal
        return Clause("eq", left, True)

    def parse_atom(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of expression")
        if tok == "[":
            self.eat("[")
            items = []
            if self.peek() != "]":
                while True:
                    items.append(self.parse_atom())
                    if self.peek() == ",":
                        self.eat(",")
                        continue
                    break
            self.eat("]")
            return items
        if tok == "(":
            self.eat("(")
            node = self.parse_or()
            self.eat(")")
            return node
        self.eat()
        return _parse_literal(tok)


def _resolve(value: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(value, tuple) and value and value[0] == "var":
        name = value[1]
        # dotted lookup: a.b.c
        cur: Any = ctx
        for part in name.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else getattr(cur, part, None)
        return cur
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def parse_condition(expr: str) -> Condition:
    """Parse a condition expression. Raises ValueError on malformed input."""
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("condition must be a non-empty string")
    tokens = _tokenize(expr)
    clause = _Parser(tokens).parse()
    return Condition(source=expr, clause=clause)


def make_evaluator(expr: str) -> Callable[[dict[str, Any] | None], bool]:
    """Return a callable that evaluates *expr* against a context dict.

    Fail-closed: parse errors raise ValueError at construction time;
    evaluation errors return False.
    """
    cond = parse_condition(expr)

    def _run(ctx: dict[str, Any] | None = None) -> bool:
        try:
            return cond.evaluate(ctx or {})
        except Exception:  # noqa: BLE001
            return False

    return _run


__all__ = ["Clause", "Condition", "make_evaluator", "parse_condition"]
