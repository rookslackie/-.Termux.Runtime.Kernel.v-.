"""The emergence field is real dynamics: order must emerge, replay must match,
and the ledger must refuse to hide a broken chain."""

from __future__ import annotations

import numpy as np
import pytest

from xi_emergence.engine import EmergenceEngine
from xi_emergence.field import EmergenceField, OPERATORS
from xi_emergence.store import EmergenceLedger


def _settle(field: EmergenceField, seconds: float = 20.0) -> float:
    field.advance(seconds)
    return field.measure()["R"]


def test_order_emerges_with_coupling():
    loose = EmergenceField(size=24, seed=7, coupling=0.0)
    tight = EmergenceField(size=24, seed=7, coupling=2.6)
    r_loose = _settle(loose)
    r_tight = _settle(tight)
    assert r_tight > r_loose + 0.3, (r_loose, r_tight)
    assert r_loose < 0.5


def test_quench_dissolves_a_coherent_field():
    field = EmergenceField(size=24, seed=11, coupling=2.6)
    coherent = _settle(field)
    field.apply("quench", {"factor": 0.0})
    dissolved = _settle(field)
    assert coherent > 0.7
    assert dissolved < coherent - 0.3


def test_replay_is_deterministic():
    a = EmergenceField(size=20, seed=99)
    b = EmergenceField(size=20, seed=99)
    script = [
        {"operator": "converge", "parameters": {"gain": 0.8}},
        {"operator": "perturb", "parameters": {"strength": 0.7}},
        {"operator": "entrain", "parameters": {"a": 3, "b": 9}},
    ]
    for step in script:
        a.apply(step["operator"], step["parameters"])
        b.apply(step["operator"], step["parameters"])
        a.advance(0.5)
        b.advance(0.5)
    assert np.allclose(a.theta, b.theta)
    assert a.measure()["R"] == b.measure()["R"]


def test_operators_change_the_field():
    field = EmergenceField(size=16, seed=5, coupling=0.5)
    assert field.apply("converge")["coupling"] > 0.5
    field.apply("quench", {"factor": 0.5})
    assert field.coupling < 0.5

    before = field.size
    field.apply("seed", {"count": 2})
    assert field.size == before + 2
    assert len(field.ids) == field.size

    field.apply("entrain", {"a": 0, "b": 1})
    assert field.omega[0] == pytest.approx(field.omega[1])

    witness = field.apply("witness", {"seed": 3})
    assert set(witness["samples"])

    field.apply("perturb", {"node": 0})
    field.apply("reset")
    assert field.coupling == field.initial_coupling
    assert field.steps == 0


def test_every_operator_is_known():
    field = EmergenceField(size=12, seed=1)
    for operator in OPERATORS:
        field.apply(operator, {"count": 1})
    with pytest.raises(ValueError):
        field.apply("sing")


def test_ledger_chain_verifies_and_detects_tampering(tmp_path):
    ledger = EmergenceLedger(tmp_path / "ledger.sqlite3")
    for i in range(5):
        ledger.append("operator", "hunter", "converge", {"i": i}, {"R": 0.1 * i})
    assert ledger.verify()["ok"]
    assert ledger.verify()["entries"] == 5
    assert ledger.find("missing") is None

    ledger._db.execute(
        "UPDATE emergence_events SET data_json = ? WHERE sequence = 2", ('{"i":999}',)
    )
    ledger._db.commit()
    verdict = ledger.verify()
    assert not verdict["ok"]
    assert verdict["broken_at"] == 2


def test_engine_commits_once_per_idempotency_key(tmp_path):
    engine = EmergenceEngine(
        field=EmergenceField(size=14, seed=3),
        ledger=EmergenceLedger(tmp_path / "engine.sqlite3"),
    )
    first = engine.act("converge", {}, actor_id="hunter", idempotency_key="k-1")
    second = engine.act("converge", {}, actor_id="hunter", idempotency_key="k-1")
    assert first["replayed"] is False
    assert second["replayed"] is True
    assert first["receipt"]["event_id"] == second["receipt"]["event_id"]
    assert engine.ledger.verify()["entries"] == 1

    with pytest.raises(ValueError):
        engine.act("converge", {}, idempotency_key="  ")


def test_snapshot_is_json_safe_and_replays(tmp_path):
    engine = EmergenceEngine(
        field=EmergenceField(size=15, seed=42),
        ledger=EmergenceLedger(":memory:"),
    )
    engine.advance(1.0)
    snapshot = engine.snapshot()
    assert len(snapshot["theta"]) == 15
    assert 0.0 <= snapshot["R"] <= 1.0
    assert snapshot["state"] in {"coherent", "emerging", "threshold", "dissolved"}

    replay = engine.replay([{"operator": "converge", "parameters": {"gain": 1.0}}], duration=1.0)
    assert replay["series"][0]["t"] == 0.0
    assert len(replay["series"]) == 2
    assert replay["operators"] == 1
