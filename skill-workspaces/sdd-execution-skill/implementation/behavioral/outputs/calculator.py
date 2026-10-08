"""Finite numeric addition."""

import math


def add(a, b):
    for operand in (a, b):
        if isinstance(operand, bool) or not isinstance(operand, (int, float)):
            raise TypeError("operands must be int or float, excluding bool")
    for operand in (a, b):
        if isinstance(operand, float) and not math.isfinite(operand):
            raise ValueError("operands must be finite")
    try:
        result = a + b
    except OverflowError as error:
        raise ValueError("result must be finite") from error
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("result must be finite")
    return result
