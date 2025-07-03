# Ξ.Test.SymbolicCapsuleEngine.v∞

import pytest
from symbolic_capsule_engine import Capsule
from capsule_field import CapsuleField

def test_capsule_compression():
    c = Capsule(
        id="Ξ.Unit",
        anchor="⟐",
        mirror="⊚",
        content="A A B B C",
        rules=["⋈", "⟐"],
        echo=True
    )
    c.compress()
    assert c.content == "A B C"

def test_capsule_echo():
    c1 = Capsule("Ξ.One", "⟐", "⊚", "X X Y", ["⋈"], True)
    c2 = Capsule("Ξ.Two", "⟐", "⊚", "Y Z", ["⋈"], True)
    c2.add_child(c1)
    feedback = c2.echo_feedback()
    assert feedback["id"] == "Ξ.Two"
    assert feedback["child_count"] == 1
    assert feedback["children"][0]["id"] == "Ξ.One"

def test_field_aggregation():
    c1 = Capsule("Ξ.A", "⟐", "⊚", "A B", ["⋈"], True)
    c2 = Capsule("Ξ.B", "⟐", "⊚", "B C", ["⋈"], True)
    field = CapsuleField([c1, c2])
    echoes = field.echo_aggregate()
    assert len(echoes) == 2
    assert echoes[0]["id"] == "Ξ.A"
    assert echoes[1]["id"] == "Ξ.B"

def test_field_serialization():
    c1 = Capsule("Ξ.A", "⟐", "⊚", "A B", ["⋈"], True)
    field = CapsuleField([c1])
    yaml_out = field.serialize_field(fmt="yaml")
    json_out = field.serialize_field(fmt="json")
    md_out = field.serialize_field(fmt="md")
    assert "Ξ.A" in yaml_out
    assert "Ξ.A" in json_out
    assert "Ξ.A" in md_out
