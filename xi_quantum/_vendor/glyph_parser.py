"""Safe parser for Ξ glyph expressions.

Supported examples:
    Ξ.YieldMax()
    Ξ.Bind("Anam:Shell")
    Ξ.Sequence(Ξ.YieldMax(), Ξ.SpiralEcho())
    Ξ.TraceNested("Ξ.SpiralEcho()")

The parser never executes source text. It converts a restricted Python-like
expression into plain dictionaries/lists/scalars for the router.
"""
from __future__ import annotations

import ast
import re
from typing import Any

_GLYPH_EXPR = re.compile(r"^\s*Ξ(?:\.[A-Za-z_][A-Za-z0-9_]*)+\s*(?:\(.*\))?\s*$", re.DOTALL)


class GlyphParseError(ValueError):
    """Raised when an expression uses syntax outside the glyph grammar."""


def parse_expression(expr: str) -> Any:
    if not isinstance(expr, str):
        raise TypeError("glyph expression must be a string")
    try:
        tree = ast.parse(expr, mode="eval").body
        return _eval_node(tree)
    except (SyntaxError, GlyphParseError, TypeError, ValueError) as exc:
        return {"error": f"Parse error: {exc}"}


def _attribute_name(node: ast.Attribute) -> str:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        raise GlyphParseError("attribute root must be a name")
    parts.append(current.id)
    return ".".join(reversed(parts))


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Call):
        if node.keywords:
            raise GlyphParseError("keyword arguments are not supported")
        func = _eval_node(node.func)
        if not isinstance(func, str):
            raise GlyphParseError("call target must resolve to a glyph name")
        args = [_eval_node(arg) for arg in node.args]
        return {"glyph": func, "args": args}

    if isinstance(node, ast.Attribute):
        return _attribute_name(node)

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, str) and _GLYPH_EXPR.match(value):
            return parse_expression(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise GlyphParseError(f"unsupported constant type: {type(value).__name__}")

    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval_node(item) for item in node.elts]

    if isinstance(node, ast.Dict):
        return {_eval_node(k): _eval_node(v) for k, v in zip(node.keys, node.values)}

    raise GlyphParseError(f"unsupported syntax: {type(node).__name__}")
