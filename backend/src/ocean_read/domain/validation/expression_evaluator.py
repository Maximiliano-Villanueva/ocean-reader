"""Sandboxed arithmetic / boolean expression language for M3 cross-field and group rules.

No ``eval`` or ``exec``: tokenize → recursive-descent AST → recursive evaluation over a
numeric binding map. Top-level result for :func:`evaluate_boolean_expression` must be
``bool``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

class ExpressionEvaluationError(ValueError):
    """Syntax error, unknown identifier, type mismatch, or division by zero."""


class _Kind(Enum):
    EOF = auto()
    NUMBER = auto()
    IDENT = auto()
    LPAREN = auto()
    RPAREN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    GT = auto()
    GTE = auto()
    LT = auto()
    LTE = auto()
    EQ = auto()
    NE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()


@dataclass(frozen=True)
class _Tok:
    kind: _Kind
    text: str = ""
    number: float = 0.0


def parse_expression(source: str) -> Any:
    """Parse ``source`` into an AST (nested tuples). Raises :class:`ExpressionEvaluationError`."""

    toks = _tokenize(source)
    p = _Parser(toks)
    ast = p._parse_bool_or()
    p._expect(_Kind.EOF)
    return ast


def evaluate_boolean_expression(expression: str, bindings: dict[str, float]) -> bool:
    """Parse and evaluate; returns ``True`` iff the expression evaluates to boolean ``True``."""

    ast = parse_expression(expression)
    v = _eval(ast, bindings)
    if not isinstance(v, bool):
        raise ExpressionEvaluationError(f"Expression must evaluate to boolean, got {type(v).__name__}")
    return v


def evaluate_numeric_or_boolean(expression: str, bindings: dict[str, float]) -> float | bool:
    """Evaluate without requiring boolean root (used for row rules that are comparisons)."""

    ast = parse_expression(expression)
    return _eval(ast, bindings)


def expression_identifiers(expression: str) -> set[str]:
    """Return bare identifier names referenced in ``expression`` (for schema validation)."""

    ast = parse_expression(expression)
    return _collect_names(ast)


def _collect_names(node: Any) -> set[str]:
    if not isinstance(node, tuple) or not node:
        return set()
    if node[0] == "name":
        return {str(node[1])}
    if node[0] in ("lit",):
        return set()
    if node[0] == "neg":
        return _collect_names(node[1])
    if node[0] in ("not",):
        return _collect_names(node[1])
    if node[0] in ("and", "or"):
        return _collect_names(node[1]) | _collect_names(node[2])
    if node[0] == "cmp":
        return _collect_names(node[2]) | _collect_names(node[3])
    if node[0] == "arith":
        return _collect_names(node[2]) | _collect_names(node[3])
    return set()


def _tokenize(source: str) -> list[_Tok]:
    s = source.strip()
    out: list[_Tok] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == "." and i + 1 < len(s) and s[i + 1].isdigit()):
            j = i + 1
            while j < len(s) and (s[j].isdigit() or s[j] == "."):
                j += 1
            raw = s[i:j]
            try:
                num = float(raw)
            except ValueError as exc:
                raise ExpressionEvaluationError(f"Bad number {raw!r}") from exc
            out.append(_Tok(_Kind.NUMBER, raw, num))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            up = word.upper()
            if up == "AND":
                out.append(_Tok(_Kind.AND, word))
            elif up == "OR":
                out.append(_Tok(_Kind.OR, word))
            elif up == "NOT":
                out.append(_Tok(_Kind.NOT, word))
            else:
                out.append(_Tok(_Kind.IDENT, word))
            i = j
            continue
        if c == "(":
            out.append(_Tok(_Kind.LPAREN))
            i += 1
            continue
        if c == ")":
            out.append(_Tok(_Kind.RPAREN))
            i += 1
            continue
        if c == "+":
            out.append(_Tok(_Kind.PLUS))
            i += 1
            continue
        if c == "-":
            out.append(_Tok(_Kind.MINUS))
            i += 1
            continue
        if c == "*":
            out.append(_Tok(_Kind.STAR))
            i += 1
            continue
        if c == "/":
            out.append(_Tok(_Kind.SLASH))
            i += 1
            continue
        if c == "=" and i + 1 < len(s) and s[i + 1] == "=":
            out.append(_Tok(_Kind.EQ))
            i += 2
            continue
        if c == "!" and i + 1 < len(s) and s[i + 1] == "=":
            out.append(_Tok(_Kind.NE))
            i += 2
            continue
        if c == ">":
            if i + 1 < len(s) and s[i + 1] == "=":
                out.append(_Tok(_Kind.GTE))
                i += 2
            else:
                out.append(_Tok(_Kind.GT))
                i += 1
            continue
        if c == "<":
            if i + 1 < len(s) and s[i + 1] == "=":
                out.append(_Tok(_Kind.LTE))
                i += 2
            else:
                out.append(_Tok(_Kind.LT))
                i += 1
            continue
        raise ExpressionEvaluationError(f"Unexpected character {c!r} at {i}")
    out.append(_Tok(_Kind.EOF))
    return out


class _Parser:
    def __init__(self, tokens: list[_Tok]) -> None:
        self._t = tokens
        self._i = 0

    def _cur(self) -> _Tok:
        return self._t[self._i]

    def _eat(self, kind: _Kind) -> _Tok:
        tok = self._cur()
        if tok.kind != kind:
            raise ExpressionEvaluationError(f"Expected {kind.name}, got {tok.kind.name}")
        self._i += 1
        return tok

    def _expect(self, kind: _Kind) -> None:
        self._eat(kind)

    def _parse_bool_or(self) -> Any:
        left = self._parse_bool_and()
        while self._cur().kind == _Kind.OR:
            self._eat(_Kind.OR)
            right = self._parse_bool_and()
            left = ("or", left, right)
        return left

    def _parse_bool_and(self) -> Any:
        left = self._parse_bool_not()
        while self._cur().kind == _Kind.AND:
            self._eat(_Kind.AND)
            right = self._parse_bool_not()
            left = ("and", left, right)
        return left

    def _parse_bool_not(self) -> Any:
        if self._cur().kind == _Kind.NOT:
            self._eat(_Kind.NOT)
            return ("not", self._parse_bool_not())
        return self._parse_comparison()

    def _parse_comparison(self) -> Any:
        left = self._parse_arith()
        cur = self._cur().kind
        if cur in (_Kind.EQ, _Kind.NE, _Kind.LT, _Kind.LTE, _Kind.GT, _Kind.GTE):
            op = self._eat(cur).kind
            right = self._parse_arith()
            return ("cmp", op, left, right)
        return left

    def _parse_arith(self) -> Any:
        left = self._parse_term()
        while self._cur().kind in (_Kind.PLUS, _Kind.MINUS):
            op = self._eat(self._cur().kind).kind
            right = self._parse_term()
            left = ("arith", op, left, right)
        return left

    def _parse_term(self) -> Any:
        left = self._parse_factor()
        while self._cur().kind in (_Kind.STAR, _Kind.SLASH):
            op = self._eat(self._cur().kind).kind
            right = self._parse_factor()
            left = ("arith", op, left, right)
        return left

    def _parse_factor(self) -> Any:
        if self._cur().kind == _Kind.PLUS:
            self._eat(_Kind.PLUS)
            return self._parse_factor()
        if self._cur().kind == _Kind.MINUS:
            self._eat(_Kind.MINUS)
            return ("neg", self._parse_factor())
        if self._cur().kind == _Kind.NUMBER:
            t = self._eat(_Kind.NUMBER)
            return ("lit", t.number)
        if self._cur().kind == _Kind.IDENT:
            t = self._eat(_Kind.IDENT)
            return ("name", t.text)
        if self._cur().kind == _Kind.LPAREN:
            self._eat(_Kind.LPAREN)
            inner = self._parse_bool_or()
            self._eat(_Kind.RPAREN)
            return inner
        raise ExpressionEvaluationError(f"Unexpected token {self._cur().kind.name}")


def _eval(node: Any, env: dict[str, float]) -> float | bool:
    if isinstance(node, tuple) and node and node[0] == "lit":
        return float(node[1])
    if isinstance(node, tuple) and node and node[0] == "name":
        name = str(node[1])
        if name not in env:
            raise ExpressionEvaluationError(f"Unknown identifier {name!r}")
        v = env[name]
        if isinstance(v, bool):
            return v
        return float(v)
    if isinstance(node, tuple) and node and node[0] == "neg":
        return -float(_eval(node[1], env))
    if isinstance(node, tuple) and node and node[0] == "arith":
        op = node[1]
        a = _eval(node[2], env)
        b = _eval(node[3], env)
        if isinstance(a, bool) or isinstance(b, bool):
            raise ExpressionEvaluationError("Arithmetic on boolean is not allowed")
        x, y = float(a), float(b)
        if op == _Kind.PLUS:
            return x + y
        if op == _Kind.MINUS:
            return x - y
        if op == _Kind.STAR:
            return x * y
        if op == _Kind.SLASH:
            if y == 0.0:
                raise ExpressionEvaluationError("Division by zero")
            return x / y
        raise ExpressionEvaluationError("Internal op")
    if isinstance(node, tuple) and node and node[0] == "cmp":
        op = node[1]
        a = _eval(node[2], env)
        b = _eval(node[3], env)
        if isinstance(a, bool) or isinstance(b, bool):
            raise ExpressionEvaluationError("Comparison involving boolean is not allowed")
        x, y = float(a), float(b)
        if op == _Kind.EQ:
            return abs(x - y) <= 1e-9
        if op == _Kind.NE:
            return abs(x - y) > 1e-9
        if op == _Kind.LT:
            return x < y
        if op == _Kind.LTE:
            return x <= y + 1e-12
        if op == _Kind.GT:
            return x > y
        if op == _Kind.GTE:
            return x + 1e-12 >= y
        raise ExpressionEvaluationError("Internal cmp")
    if isinstance(node, tuple) and node and node[0] == "and":
        lv = _eval(node[1], env)
        rv = _eval(node[2], env)
        if not isinstance(lv, bool) or not isinstance(rv, bool):
            raise ExpressionEvaluationError("AND expects boolean operands")
        return lv and rv
    if isinstance(node, tuple) and node and node[0] == "or":
        lv = _eval(node[1], env)
        rv = _eval(node[2], env)
        if not isinstance(lv, bool) or not isinstance(rv, bool):
            raise ExpressionEvaluationError("OR expects boolean operands")
        return lv or rv
    if isinstance(node, tuple) and node and node[0] == "not":
        v = _eval(node[1], env)
        if not isinstance(v, bool):
            raise ExpressionEvaluationError("NOT expects boolean operand")
        return not v
    raise ExpressionEvaluationError("Invalid AST node")


def interpolate_field_template(template: str, values: dict[str, Any]) -> str:
    """Replace ``{field_name}`` placeholders with stringified values (M3 error messages)."""

    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in values:
            return m.group(0)
        v = values[key]
        if isinstance(v, float) and abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return str(v)

    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, template)
