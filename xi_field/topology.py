"""Load and validate the recovered Woven Glyph-Chip topology."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import Any

import yaml


def chip_topology() -> tuple[dict[str, Any], str]:
    raw = files("xi_field.resources").joinpath("glyphic_quantum_processor.yaml").read_bytes()
    document = yaml.safe_load(raw)
    chip = document.get("glyphic_quantum_processor", {}) if isinstance(document, dict) else {}
    names = {node.get("name") for node in chip.get("nodes", []) if isinstance(node, dict)}
    required_nodes = {"Ψ", "⋈", "⟐", "Self₁₇", "Xi", "∴", "Hunter"}
    if not required_nodes.issubset(names):
        raise ValueError(f"recovered chip topology is missing nodes: {sorted(required_nodes - names)}")
    edges = chip.get("edges", [])
    if not edges or any(edge.get("from") not in names or edge.get("to") not in names for edge in edges):
        raise ValueError("recovered chip topology contains an invalid edge")
    return chip, hashlib.sha256(raw).hexdigest()
