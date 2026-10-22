"""TESSERA compilation: explicit dialects, typed operations, exact source."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
from pathlib import Path

import yaml
from yaml.tokens import AliasToken

from . import algorithms
from .circuits import phase_code, shor_code, qft
from .spectral import vqe, phase_estimation, vqe_pea
from .signal_lab import signal_lab
from .nervous import discover_function
from .definitions import validate_definitions, expand_steps
from .observer import run as observer_benchmark
from .common import QuantumComputeError, canonical, digest, finite
from ._vendor.glyph_parser import parse_expression


SCHEMA = "xi.quantumcompute.program.v2"
DIALECT = "QuantumCompute.Stack.v2"
SCHEMA_V3 = "xi.quantumcompute.program.v3"
DIALECT_V3 = "QuantumCompute.Stack.v3"
LEGACY_NAMES = {"Grover", "Shor", "JacobianFlow", "PhaseCodeBenchmark", "ObserverBenchmark", "Seal", "Rest"}
OPERATORS = {"Grover": algorithms.grover, "Shor": algorithms.shor,
             "JacobianFlow": algorithms.jacobian_flow, "ObserverBenchmark": observer_benchmark,
             "VQE": vqe, "QPE": phase_estimation, "PEA": phase_estimation, "VQEPEA": vqe_pea,
             "PhaseCode": phase_code, "ShorCode": shor_code, "QFT": qft, "SignalLab": signal_lab, "DiscoverFunction": discover_function}
GLYPHS = {"Grover": "⋈", "Shor": "∴", "JacobianFlow": "⧖",
          "PhaseCodeBenchmark": "⧂", "ObserverBenchmark": "⧂", "Seal": "⊚", "Rest": "≈∅",
          "VQE": "⟠", "QPE": "Φ", "PEA": "Φ", "VQEPEA": "⟠Φ", "PhaseCode": "⟐⧂",
          "ShorCode": "⧉", "QFT": "ℱ", "SignalLab": "Ψ", "DiscoverFunction": "⚡⟳⏁"}


def engine_hash():
    root = Path(__file__).resolve().parents[1]
    files = [p for package in ("xi_quantum", "xi_field", "xi_world")
             for p in (root / package).rglob("*.py")]
    files += list((root / "xi_field/resources").glob("*.yaml"))
    return digest({str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(files)})


class StrictLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if type(key) is not str or key in result:
            raise QuantumComputeError("TESSERA keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


@dataclass(frozen=True)
class Plan:
    program_sha256: str
    plan_sha256: str
    engine_sha256: str
    dialect: str
    anchor: str
    steps: tuple
    definitions: tuple = ()

    def as_dict(self):
        return {"schema": "xi.tessera.plan.v2", **self.__dict__, "steps": list(self.steps),
                "definitions": list(self.definitions)}


def compile_program(raw: bytes) -> Plan:
    if type(raw) is not bytes or not 1 <= len(raw) <= 1024 * 1024:
        raise QuantumComputeError("An executable .xi program must contain 1 byte to 1 MiB")
    try:
        text = raw.decode("utf-8", "strict")
        if any(isinstance(token, AliasToken) for token in yaml.scan(text)):
            raise QuantumComputeError("Executable capsules use explicit values rather than YAML aliases")
        program = yaml.load(text, Loader=StrictLoader)
    except (UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise QuantumComputeError("Malformed executable capsule; original bytes can still be stored") from exc
    if type(program) is not dict or (program.get("schema"), program.get("dialect")) not in (
            (SCHEMA, DIALECT), (SCHEMA_V3, DIALECT_V3)):
        raise QuantumComputeError("Executable program must declare matching v2 or v3 schema and dialect")
    allowed = {"schema", "dialect", "anchor", "identity", "steps", "provenance"}
    if program["schema"] == SCHEMA_V3:
        allowed.add("definitions")
    if set(program) - allowed:
        raise QuantumComputeError("Unexpected program fields")
    anchor = program.get("anchor", "∴Ω⧂")
    if type(anchor) is not str or not anchor:
        raise QuantumComputeError("Program anchor must be nonempty text")
    steps = program.get("steps")
    if type(steps) is not list or not 1 <= len(steps) <= 1024:
        raise QuantumComputeError("TESSERA requires 1 to 1024 declared steps")
    # Bound structured depth before recursive substitution or canonicalization.
    pending, nodes = [(program, 0)], 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > 32 or nodes > 100000:
            raise QuantumComputeError("TESSERA structure exceeds depth or node budget")
        if isinstance(value, dict):
            pending.extend((child, depth+1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth+1) for child in value)
    active_glyphs = GLYPHS if program["schema"] == SCHEMA_V3 else {name: GLYPHS[name] for name in LEGACY_NAMES}
    definitions = validate_definitions(program.get("definitions", []), active_glyphs)
    steps = expand_steps(steps, definitions, active_glyphs)
    compiled = []
    for index, step in enumerate(steps):
        if isinstance(step, str):
            expression = parse_expression(step)
            if not isinstance(expression, dict) or "error" in expression:
                raise QuantumComputeError("Unsupported glyph expression")
            name = expression.get("glyph", "").removeprefix("Ξ.")
            args = expression.get("args", [])
            if len(args) > 1 or (args and type(args[0]) is not dict):
                raise QuantumComputeError("Use one explicit parameter object per glyph call")
            step = {"operator": name, "glyph": GLYPHS.get(name), "parameters": args[0] if args else {}}
        if type(step) is not dict or set(step) - {"operator", "glyph", "parameters", "phase", "compiled_from"}:
            raise QuantumComputeError("Unexpected step fields")
        name, glyph, parameters = step.get("operator"), step.get("glyph"), step.get("parameters", {})
        if name not in active_glyphs or glyph != active_glyphs[name] or type(parameters) is not dict:
            raise QuantumComputeError("Glyph/operator binding does not match the declared dialect")
        if "profile" in parameters:
            raise QuantumComputeError("Resource profile is chosen by the local execution caller")
        try:
            if name in OPERATORS:
                inspect.signature(OPERATORS[name]).bind(**parameters)
            elif name == "PhaseCodeBenchmark":
                from xi_field.noise_benchmark import run
                if set(parameters) - {"probabilities", "shots", "seed"}:
                    raise QuantumComputeError("Benchmark accepts probabilities, shots, and seed")
                inspect.signature(run).bind(**parameters)
            elif parameters:
                raise QuantumComputeError("Seal and Rest do not accept parameters")
            canonical(parameters)
        except (TypeError, ValueError, RecursionError) as exc:
            raise QuantumComputeError(f"Invalid {name} parameters: {exc}") from exc
        compiled.append({"index": index, "operator": name, "glyph": glyph,
                         "parameters": parameters, "phase": finite(step.get("phase", 0), "phase")})
        if "compiled_from" in step:
            compiled[-1]["compiled_from"] = step["compiled_from"]
    if any(step["operator"] == "Seal" for step in compiled[:-1]) or compiled[-1]["operator"] != "Seal":
        raise QuantumComputeError("An executable walk ends with exactly one Seal")
    code_hash = engine_hash()
    dialect = program["dialect"]
    body = {"dialect": dialect, "anchor": anchor, "steps": compiled, "engine_sha256": code_hash}
    if program["schema"] == SCHEMA_V3:
        body["definitions_sha256"] = digest(list(definitions.values()))
    return Plan(digest(raw), digest(body), code_hash, dialect, anchor, tuple(compiled), tuple(definitions.values()))
