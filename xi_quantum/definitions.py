"""Versioned, exact-glyph macro definitions lowered into typed primitives.

Definitions are declarative data. Parameters use whole-value $name references;
there is no Python evaluation, textual substitution, or silent glyph rewriting.
"""
from __future__ import annotations

import copy
import re

from .common import QuantumComputeError, canonical, digest, finite, integer
from ._vendor.glyph_parser import parse_expression


NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
TYPES = {"integer": lambda v: type(v) is int, "number": lambda v: type(v) in (int, float),
         "string": lambda v: type(v) is str, "boolean": lambda v: type(v) is bool,
         "array": lambda v: type(v) is list, "object": lambda v: type(v) is dict}


def _check_value(name, value, specification):
    kind = specification.get("type")
    if kind not in TYPES or not TYPES[kind](value):
        raise QuantumComputeError(f"Glyph parameter {name} must have type {kind}")
    canonical(value)
    if kind in ("number", "integer"):
        finite(value, name)
        if "minimum" in specification and value < specification["minimum"]:
            raise QuantumComputeError(f"Glyph parameter {name} is below its minimum")
        if "maximum" in specification and value > specification["maximum"]:
            raise QuantumComputeError(f"Glyph parameter {name} is above its maximum")
    if "enum" in specification and value not in specification["enum"]:
        raise QuantumComputeError(f"Glyph parameter {name} is outside its declared enum")


def validate_definitions(definitions, builtins):
    if type(definitions) is not list or len(definitions) > 64:
        raise QuantumComputeError("TESSERA accepts at most 64 local glyph definitions")
    result, glyphs = {}, set(builtins.values())
    for definition in definitions:
        if (type(definition) is not dict or set(definition) !=
                {"name", "version", "glyph", "meaning", "parameters", "steps"}):
            raise QuantumComputeError("A glyph definition requires name, version, glyph, meaning, parameters, and steps")
        name, glyph = definition["name"], definition["glyph"]
        if type(name) is not str or not NAME.fullmatch(name) or name in result or name in builtins:
            raise QuantumComputeError("Glyph definition names must be distinct identifiers outside the primitive catalogue")
        integer(definition["version"], "definition version", 1, 2147483647)
        if (type(glyph) is not str or not 1 <= len(glyph) <= 32
                or any(ord(c) < 33 for c in glyph) or glyph in glyphs):
            raise QuantumComputeError("A new exact glyph must be nonempty, distinct, and contain no spaces or controls")
        if type(definition["meaning"]) is not str or not definition["meaning"].strip():
            raise QuantumComputeError("A new glyph needs its explicit intended meaning")
        specs = definition["parameters"]
        if type(specs) is not dict or len(specs) > 32:
            raise QuantumComputeError("A glyph definition accepts at most 32 named parameters")
        for parameter, spec in specs.items():
            if type(parameter) is not str or not NAME.fullmatch(parameter):
                raise QuantumComputeError("Invalid glyph parameter name")
            if (type(spec) is not dict or set(spec) - {"type", "default", "minimum", "maximum", "enum"}
                    or spec.get("type") not in TYPES):
                raise QuantumComputeError("Invalid glyph parameter specification")
            for bound in ("minimum", "maximum"):
                if bound in spec:
                    finite(spec[bound], bound)
            if "enum" in spec and (type(spec["enum"]) is not list or not spec["enum"]):
                raise QuantumComputeError("A parameter enum must be a nonempty list")
            if "default" in spec:
                _check_value(parameter, spec["default"], spec)
        if type(definition["steps"]) is not list or not 1 <= len(definition["steps"]) <= 128:
            raise QuantumComputeError("A glyph body requires 1..128 declared steps")
        result[name] = copy.deepcopy(definition)
        glyphs.add(glyph)
    # Check every body, including unused definitions, for missing bindings and cycles.
    depths = {}
    def visit(name, path):
        if name in path:
            raise QuantumComputeError("Glyph definitions are cyclic or exceed nesting depth 16")
        if name in depths:
            return depths[name]
        depth = 1
        for step in result[name]["steps"]:
            if type(step) is not dict or step.get("operator") not in set(builtins) | set(result):
                raise QuantumComputeError("Glyph bodies require known explicit operator objects")
            expected = builtins.get(step["operator"], result.get(step["operator"], {}).get("glyph"))
            if (set(step) - {"operator", "glyph", "parameters", "phase"}
                    or step.get("glyph") != expected or type(step.get("parameters", {})) is not dict):
                raise QuantumComputeError("Glyph body binding or fields do not match their catalogue")
            if step["operator"] in result:
                depth = max(depth, 1 + visit(step["operator"], path + [name]))
        if depth > 16:
            raise QuantumComputeError("Glyph definitions exceed nesting depth 16")
        depths[name] = depth
        return depth
    for name in result:
        visit(name, [])
    return result


def _resolve(value, parameters):
    if isinstance(value, str) and value.startswith("$"):
        if value[1:] not in parameters:
            raise QuantumComputeError(f"Unknown glyph parameter reference {value}")
        return copy.deepcopy(parameters[value[1:]])
    if type(value) is dict:
        return {key: _resolve(item, parameters) for key, item in value.items()}
    if type(value) is list:
        return [_resolve(item, parameters) for item in value]
    return value


def expand_steps(steps, definitions, builtins):
    catalogue = {**builtins, **{name: definition["glyph"] for name, definition in definitions.items()}}
    expanded = []

    def lower(step, source_index, lineage):
        if isinstance(step, str):
            expression = parse_expression(step)
            if not isinstance(expression, dict) or "error" in expression:
                raise QuantumComputeError("Unsupported glyph expression")
            name = expression.get("glyph", "").removeprefix("Ξ.")
            arguments = expression.get("args", [])
            if len(arguments) > 1 or (arguments and type(arguments[0]) is not dict):
                raise QuantumComputeError("Use one explicit parameter object per glyph call")
            step = {"operator": name, "glyph": catalogue.get(name),
                    "parameters": arguments[0] if arguments else {}}
        if type(step) is not dict or set(step) - {"operator", "glyph", "parameters", "phase"}:
            raise QuantumComputeError("Unexpected step fields")
        name, glyph, parameters = step.get("operator"), step.get("glyph"), step.get("parameters", {})
        if name not in catalogue or glyph != catalogue[name] or type(parameters) is not dict:
            raise QuantumComputeError("Glyph/operator binding does not match the declared dialect")
        if name not in definitions:
            compiled = copy.deepcopy(step)
            if lineage:
                compiled["compiled_from"] = {"source_index": source_index, "definitions": lineage}
            expanded.append(compiled)
            if len(expanded) > 1024:
                raise QuantumComputeError("Expanded glyph program exceeds 1024 primitive steps")
            return
        definition = definitions[name]
        if set(parameters) - set(definition["parameters"]):
            raise QuantumComputeError(f"Unknown parameter for glyph {name}")
        bound = {}
        for parameter, spec in definition["parameters"].items():
            if parameter not in parameters and "default" not in spec:
                raise QuantumComputeError(f"Missing glyph parameter {parameter}")
            value = parameters[parameter] if parameter in parameters else spec["default"]
            _check_value(parameter, value, spec)
            bound[parameter] = value
        binding = {"name": name, "glyph": glyph, "version": definition["version"],
                   "definition_sha256": digest(definition), "parameters": bound}
        for child in definition["steps"]:
            resolved = _resolve(child, bound)
            resolved.setdefault("phase", step.get("phase", 0))
            lower(resolved, source_index, lineage + [binding])

    for source_index, step in enumerate(steps):
        lower(step, source_index, [])
    return expanded
