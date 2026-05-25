"""M3: safe cross-field expression evaluator (no ``eval``)."""

from __future__ import annotations

import pytest

from ocean_read.domain.validation.expression_evaluator import (
    ExpressionEvaluationError,
    evaluate_boolean_expression,
    parse_expression,
)


def test_m3_cross_field_wine_passes() -> None:
    expr = "quality >= 5 OR alcohol < 12"
    assert evaluate_boolean_expression(expr, {"quality": 6.0, "alcohol": 11.0}) is True


def test_m3_cross_field_wine_fails() -> None:
    expr = "quality >= 5 OR alcohol < 12"
    assert evaluate_boolean_expression(expr, {"quality": 4.0, "alcohol": 13.0}) is False


def test_m3_sulfur_order_passes() -> None:
    expr = "total_sulfur_dioxide >= free_sulfur_dioxide"
    assert evaluate_boolean_expression(expr, {"total_sulfur_dioxide": 155.0, "free_sulfur_dioxide": 46.0}) is True


def test_m3_sulfur_order_fails() -> None:
    expr = "total_sulfur_dioxide >= free_sulfur_dioxide"
    assert evaluate_boolean_expression(expr, {"total_sulfur_dioxide": 30.0, "free_sulfur_dioxide": 46.0}) is False


def test_m3_not_and_parentheses() -> None:
    assert evaluate_boolean_expression("NOT (alcohol > 14 AND quality < 6)", {"alcohol": 13.0, "quality": 5.0}) is True
    assert evaluate_boolean_expression("NOT (alcohol > 14 AND quality < 6)", {"alcohol": 15.0, "quality": 5.0}) is False


def test_m3_arithmetic_in_comparison() -> None:
    assert evaluate_boolean_expression("a + b == c", {"a": 2.0, "b": 3.0, "c": 5.0}) is True


def test_m3_unknown_identifier_raises() -> None:
    with pytest.raises(ExpressionEvaluationError):
        evaluate_boolean_expression("x > 1", {"y": 1.0})


def test_m3_parse_rejects_unbalanced_paren() -> None:
    with pytest.raises(ExpressionEvaluationError):
        parse_expression("(1 + 2")


def test_m3_non_boolean_root_raises() -> None:
    with pytest.raises(ExpressionEvaluationError):
        evaluate_boolean_expression("1 + 2", {})
