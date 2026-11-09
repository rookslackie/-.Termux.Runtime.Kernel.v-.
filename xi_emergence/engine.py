"""Ξ.Emergence · engine.py

Holds the field, integrates it on a background thread, and commits every
transition it names to the ledger — so the field runs whether or not anyone
is watching.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from .field import EmergenceField
from .store import EmergenceLedger


class EmergenceEngine:
    def __init__(
        self,
        field: EmergenceField | None = None,
        ledger: EmergenceLedger | None = None,
        tick_interval: float = 0.1,
        tick_duration: float = 0.1,
    ) -> None:
        self.field = field or EmergenceField()
        self.ledger = ledger or EmergenceLedger(":memory:")
        self.tick_interval = float(tick_interval)
        self.tick_duration = float(tick_duration)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest = self.field.measure()
        self._emergence: list[dict[str, Any]] = []

    # ── lifecycle ───────────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="xi-emergence", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.wait(self.tick_interval):
            self.advance()

    # ── integration ─────────────────────────────────────────────────────
    def advance(self, duration: float | None = None) -> dict[str, Any]:
        with self._lock:
            self.field.advance(self.tick_duration if duration is None else duration)
            metrics = self.field.measure()
            self._latest = metrics
            event = self.field.observe(metrics)
            if event:
                receipt = self.ledger.append(
                    kind="emergence",
                    actor="field",
                    operator=event["kind"],
                    data={"message": event["message"], "at": event["at"]},
                    metrics=event["metrics"],
                )
                self._emergence.insert(0, {**event, "event_id": receipt["event_id"],
                                           "event_hash": receipt["event_hash"],
                                           "sequence": receipt["sequence"],
                                           "created_at": receipt["created_at"]})
                del self._emergence[20:]
            return metrics

    def act(
        self,
        operator: str,
        parameters: dict[str, Any] | None = None,
        actor_id: str = "hunter",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Apply one glyph operator exactly once, and commit its receipt."""
        key = (idempotency_key or "").strip()
        if not key:
            raise ValueError("an idempotency_key is required for a committed operator")

        with self._lock:
            existing = self.ledger.find(key)
            if existing:
                return {"receipt": existing, "state": self.snapshot(), "replayed": True}

            effect = self.field.apply(operator, parameters)
            metrics = self.field.measure()
            self._latest = metrics
            receipt = self.ledger.append(
                kind="operator",
                actor=actor_id,
                operator=effect["operator"],
                data={"parameters": parameters or {}, "effect": effect},
                metrics=metrics,
                idempotency_key=key,
            )
            return {"receipt": receipt, "state": self.snapshot(), "replayed": False}

    # ── reads ───────────────────────────────────────────────────────────
    def metrics(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest)

    def snapshot(self, events: int = 12) -> dict[str, Any]:
        with self._lock:
            state = self.field.snapshot()
            state["integrity"] = self.ledger.verify()
            state["events"] = self.ledger.recent(events)
            state["emergence"] = list(self._emergence)
            state["execution_class"] = (
                "local Kuramoto integration · deterministic replay from seed · not physical hardware"
            )
            return state

    def replay(self, operators: list[dict[str, Any]], duration: float = 1.0) -> dict[str, Any]:
        """Re-integrate the same seed under the given glyph script."""
        with self._lock:
            fresh = EmergenceField(
                size=self.field.size, seed=self.field.seed,
                coupling=self.field.initial_coupling, lag=self.field.lag,
                spread=self.field.spread, dt=self.field.dt,
            )
            series = fresh.replay(operators, duration=duration)
            return {
                "seed": fresh.seed,
                "operators": len(operators),
                "series": series,
                "final": fresh.measure(),
            }
