"""Deterministic structural composition for provenance-bearing residues.

This module does not interpret narrative meaning. It carries source boundaries
through a workbench projection and derives only relations explicitly recorded
in the input: adjacency, unfinished form, repair traces, and contrast.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping


INCOMPLETE_STATES = {"empty", "unopened", "unfinished", "incomplete"}


def compose_structural_field(residues: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Build an auditable working set without assigning semantic meaning."""
    sources: list[dict[str, Any]] = []
    elements: list[dict[str, str]] = []
    adjacency: list[dict[str, Any]] = []
    contrasts: list[dict[str, Any]] = []
    incomplete: list[dict[str, str]] = []
    repair_traces: list[dict[str, str]] = []

    for residue in residues:
        residue_id = str(residue["residue_id"])
        form = residue.get("form", {})
        residue_elements = form.get("elements", [])
        element_ids = {str(item["id"]) for item in residue_elements}
        sources.append({
            "residue_id": residue_id,
            "provenance": residue["provenance"],
            "source_ref": residue.get("source_ref"),
            "recovered": list(residue.get("recovered", [])),
            "composed": list(residue.get("composed", [])),
        })

        for item in residue_elements:
            item_id, state = str(item["id"]), str(item["state"])
            node = {"residue_id": residue_id, "element_id": item_id, "state": state}
            elements.append(node)
            if state in INCOMPLETE_STATES:
                incomplete.append({"residue_id": residue_id, "element_id": item_id, "state": state})
            if state == "repaired":
                repair_traces.append({"residue_id": residue_id, "element_id": item_id})

        for left, right in form.get("adjacent", []):
            if left not in element_ids or right not in element_ids:
                raise ValueError(f"adjacency in {residue_id!r} must reference recorded form elements")
            adjacency.append({"residue_id": residue_id, "left": left, "right": right})
        for left, right in form.get("contrasts", []):
            if left not in element_ids or right not in element_ids:
                raise ValueError(f"contrast in {residue_id!r} must reference recorded form elements")
            contrasts.append({"residue_id": residue_id, "left": left, "right": right})

    return {
        "operator": "structural_projection.v1",
        "sources": sources,
        "elements": elements,
        "adjacency": adjacency,
        "incomplete": incomplete,
        "repair_traces": repair_traces,
        "contrasts": contrasts,
        "interpretation": None,
        "meaning_status": "unassigned",
    }
