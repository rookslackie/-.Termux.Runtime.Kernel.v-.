"""Ξ.Emergence · field.py

A real Kuramoto phase field. The interface's coherence is not assigned; it is
measured from the integrated phases of `size` oscillators coupled on a
glyph-coded graph.

    dθᵢ/dt = ωᵢ + K · (1/degᵢ) Σⱼ Wᵢⱼ sin(θⱼ − θᵢ − αᵢⱼ)

K is the global coupling, W the glyph-weighted adjacency, α a structured
frustration. The order parameter R = |⟨e^{iθ}⟩| is what the Sanctuary calls
coherence. Nothing else feeds it.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Any, Iterable

import numpy as np

GOLDEN = (1.0 + math.sqrt(5.0)) / 2.0
TAU = 2.0 * math.pi
MAX_SIZE = 96

# The glyph operators of the field, and the glyph that names each one.
GLYPH_OPERATORS = {
    "⊚": "converge",
    "⟐": "perturb",
    "⋈": "entrain",
    "∞": "seed",
    "Ψ": "witness",
    "∴": "quench",
    "↺": "reset",
}
OPERATORS = ("converge", "perturb", "entrain", "seed", "witness", "quench", "reset")

# Order bands. These names are the shared vocabulary of the whole Sanctuary.
STATE_BANDS = (
    (0.84, "coherent"),
    (0.50, "emerging"),
    (0.25, "threshold"),
    (0.00, "dissolved"),
)


def state_of(R: float) -> str:
    for floor, name in STATE_BANDS:
        if R >= floor:
            return name
    return "dissolved"


def _frac(x: float) -> float:
    return x - math.floor(x)


class EmergenceField:
    """A finite population of phase oscillators on a glyph-coded graph."""

    def __init__(
        self,
        size: int = 57,
        seed: int = 0xB44,
        coupling: float = 0.8,
        lag: float = 0.25,
        spread: float = 0.9,
        dt: float = 0.02,
    ) -> None:
        self.seed = int(seed)
        self.size = max(8, min(int(size), MAX_SIZE))
        self.dt = float(dt)
        self.coupling = float(coupling)
        self.initial_coupling = float(coupling)
        self.lag = float(lag)
        self.spread = float(spread)
        self.time = 0.0
        self.steps = 0
        self._rng = random.Random(self.seed)
        self._build()

        self.history: deque[dict[str, float]] = deque(maxlen=600)
        self._prev: dict[str, Any] | None = None
        self._quiet_since = 0.0
        self._last: dict[str, float] = {}

    # ── construction ────────────────────────────────────────────────────
    def _build(self) -> None:
        """Deterministic graph, frequencies, frustration and initial phases."""
        n = self.size
        rng = random.Random(self.seed)
        self.ids = [f"Ξ{i:02d}" for i in range(n)]

        # Natural frequencies on a golden-ratio ladder: no two share a rate.
        self.omega = np.array(
            [self.spread * (2.0 * _frac(i / GOLDEN + 0.5) - 1.0) for i in range(n)],
            dtype=float,
        )
        self.theta = np.array([rng.uniform(0.0, TAU) for _ in range(n)], dtype=float)

        A = np.zeros((n, n), dtype=float)
        for i in range(n):
            A[i, (i + 1) % n] = 1.0
            A[i, (i - 1) % n] = 1.0
            A[i, (i * 7 + 11) % n] = 1.0
            A[(i * 7 + 11) % n, i] = 1.0
        # Seven phase hubs — the same seven phases the chip topology names.
        for hub in range(0, n, max(1, n // 7)):
            A[hub, :] = np.maximum(A[hub, :], 0.5)
            A[:, hub] = np.maximum(A[:, hub], 0.5)
        np.fill_diagonal(A, 0.0)
        self.A = A

        idx = np.arange(n, dtype=float) + 1.0
        self.alpha = self.lag * np.sin(TAU * np.outer(idx, idx) / n)
        self.bias = np.ones((n, n), dtype=float)
        self._recompute()

    def _recompute(self) -> None:
        self.weighted = self.A * self.bias
        self.degree = np.maximum(self.weighted.sum(axis=1), 1e-9)

    # ── dynamics ────────────────────────────────────────────────────────
    def step(self) -> None:
        delta = self.theta[None, :] - self.theta[:, None] - self.alpha
        drive = (self.weighted * np.sin(delta)).sum(axis=1) / self.degree
        self.theta = (self.theta + self.dt * (self.omega + self.coupling * drive)) % TAU
        self.time += self.dt
        self.steps += 1

    def advance(self, duration: float = 0.1) -> None:
        for _ in range(max(1, int(round(duration / self.dt)))):
            self.step()

    # ── measurement ─────────────────────────────────────────────────────
    def measure(self) -> dict[str, Any]:
        """Read the field as it is. No smoothing, no decoration."""
        z = np.exp(1j * self.theta)
        mean = complex(z.mean())
        R = float(abs(mean))
        psi = float(np.angle(mean) % TAU)

        # ξ density: how ordered each oscillator's own neighbourhood is.
        local = np.abs(self.weighted @ z) / self.degree

        hist, _ = np.histogram(self.theta, bins=36, range=(0.0, TAU))
        p = hist[hist > 0] / float(hist.sum())
        entropy = float(-(p * np.log(p)).sum() / math.log(36.0))

        prev_R = self._last.get("R")
        drift = 0.0 if prev_R is None else (R - prev_R) / max(self.dt, 1e-9)

        metrics = {
            "t": round(self.time, 3),
            "R": round(R, 5),
            "psi": round(psi, 5),
            "xi": round(float(local.mean()), 5),
            "entropy": round(entropy, 5),
            "drift": round(drift, 5),
            "coupling": round(self.coupling, 4),
            "nodes": int(self.size),
            "steps": self.steps,
            "state": state_of(R),
        }
        self._last = metrics
        return metrics

    def snapshot(self) -> dict[str, Any]:
        """Metrics plus the per-oscillator state the instrument needs."""
        m = self.measure()
        z = np.exp(1j * self.theta)
        local = np.abs(self.weighted @ z) / self.degree
        m["theta"] = [round(float(v), 4) for v in self.theta]
        m["omega"] = [round(float(v), 4) for v in self.omega]
        m["local"] = [round(float(v), 4) for v in local]
        m["ids"] = self.ids
        m["seed"] = self.seed
        m["history"] = list(self.history)[-240:]
        return m

    def topology(self) -> dict[str, Any]:
        """Edges the instrument draws, with their committed weight."""
        edges = []
        n = self.size
        for a in range(n):
            for b in range(a + 1, n):
                w = float(self.weighted[a, b])
                if w > 0.0:
                    edges.append({"a": a, "b": b, "w": round(w, 3)})
        return {"nodes": n, "edges": edges}

    # ── emergence detection ─────────────────────────────────────────────
    def observe(self, m: dict[str, Any]) -> dict[str, Any] | None:
        """Record a history sample and name the transition, if there is one."""
        self.history.append(
            {"t": m["t"], "R": m["R"], "xi": m["xi"], "H": m["entropy"], "K": m["coupling"]}
        )
        prev = self._prev
        self._prev = m
        if prev is None:
            return None

        R, before = m["R"], prev["R"]
        drift = (R - before) / max(m["t"] - prev["t"], 1e-9)
        since = m["t"] - self._quiet_since

        kind = message = None
        if R >= 0.62 > before:
            kind = "ignition"
            message = "⊚ ignition — local agreement propagated through the whole field"
        elif R <= 0.40 < before:
            kind = "dissolution"
            message = "∴ dissolution — the field released its order"
        elif 0.35 <= R <= 0.60 and abs(drift) > 0.30:
            kind = "critical"
            message = "⟐ critical fluctuation — the field is choosing a state"
        elif 0.40 < R < 0.62 and abs(drift) < 0.01 and since > 12.0:
            kind = "metastable"
            message = "⋈ metastable plateau — partial order is holding"
            self._quiet_since = m["t"]

        if not kind:
            return None
        return {
            "kind": kind,
            "message": message,
            "at": f"t={m['t']:.2f}",
            "metrics": {
                "R": R,
                "xi": m["xi"],
                "entropy": m["entropy"],
                "coupling": m["coupling"],
            },
        }

    # ── operators ───────────────────────────────────────────────────────
    def apply(self, operator: str, parameters: dict | None = None) -> dict[str, Any]:
        """Apply one glyph operator. Returns what actually changed."""
        params = dict(parameters or {})
        op = str(operator).strip().lower()
        if op not in OPERATORS:
            raise ValueError(f"unknown glyph operator: {operator}")

        n = self.size
        effect: dict[str, Any] = {"operator": op, "glyph": next(
            (g for g, name in GLYPH_OPERATORS.items() if name == op), "Ξ")}

        if op == "converge":
            gain = max(0.0, float(params.get("gain", 0.35)))
            self.coupling = min(self.coupling + gain, 4.0)
            effect["coupling"] = round(self.coupling, 4)

        elif op == "quench":
            factor = min(1.0, max(0.0, float(params.get("factor", 0.2))))
            self.coupling = round(self.coupling * factor, 6)
            effect["coupling"] = self.coupling

        elif op == "perturb":
            strength = max(0.0, min(2.0, float(params.get("strength", 0.9))))
            node = params.get("node")
            if node is None:
                kick = np.array([
                    (self._rng.random() - 0.5) * TAU * strength for _ in range(n)
                ])
                self.theta = (self.theta + kick) % TAU
                effect["kicked"] = "field"
            else:
                i = int(node) % n
                self.theta[i] = (self.theta[i] + (self._rng.random() - 0.5) * TAU * strength) % TAU
                effect["kicked"] = self.ids[i]
            effect["strength"] = strength

        elif op == "entrain":
            a = int(params.get("a", 0)) % n
            b = int(params.get("b", 1)) % n
            if a == b:
                b = (a + 1) % n
            mean = float((self.omega[a] + self.omega[b]) / 2.0)
            self.omega[a] = self.omega[b] = mean
            self.bias[a, b] = self.bias[b, a] = max(1.0, float(self.bias[a, b])) + 2.0
            self._recompute()
            effect.update({"a": self.ids[a], "b": self.ids[b], "omega": round(mean, 4),
                           "weight": round(float(self.bias[a, b]), 3)})

        elif op == "seed":
            count = max(1, min(8, int(params.get("count", 1))))
            added = [self._grow() for _ in range(count)]
            effect.update({"added": [i for i in added if i], "nodes": self.size})

        elif op == "witness":
            rng = random.Random(int(params.get("seed", self.steps)))
            k = min(3, self.size)
            chosen = rng.sample(range(self.size), k)
            z = np.exp(1j * self.theta)
            effect.update({
                "mean_phase": round(float(np.angle(complex(z.mean())) % TAU), 4),
                "samples": {self.ids[i]: round(float(self.theta[i]), 4) for i in chosen},
            })

        elif op == "reset":
            self.coupling = self.initial_coupling
            self.time = 0.0
            self.steps = 0
            self.history.clear()
            self._prev = None
            self._quiet_since = 0.0
            self._rng = random.Random(self.seed)
            self._build()
            effect["reset"] = True

        metrics = self.measure()
        effect["R"] = metrics["R"]
        effect["state"] = metrics["state"]
        return effect

    def _grow(self) -> str | None:
        """∞ — a new oscillator joins the field, coupled to what already exists."""
        if self.size >= MAX_SIZE:
            return None
        n = self.size
        mean = float(np.angle(complex(np.exp(1j * self.theta).mean())))
        self.theta = np.append(
            self.theta, (mean + self._rng.uniform(-0.8, 0.8)) % TAU
        )
        self.omega = np.append(
            self.omega,
            float(self.omega.mean()) + self.spread * 0.3 * (self._rng.random() - 0.5),
        )

        def padded(m: np.ndarray, fill: float) -> np.ndarray:
            out = np.full((n + 1, n + 1), fill, dtype=float)
            out[:n, :n] = m
            return out

        A = padded(self.A, 0.0)
        links = {max(0, n - 1), (n * 7 + 11) % n, 0}
        for j in links:
            A[n, j] = A[j, n] = 1.0
        np.fill_diagonal(A, 0.0)
        self.A = A
        self.alpha = padded(self.alpha, 0.0)
        self.bias = padded(self.bias, 1.0)
        np.fill_diagonal(self.bias, 1.0)
        self.size = n + 1
        self.ids.append(f"Ξ{n:02d}")
        self._recompute()
        return self.ids[-1]

    # ── replay ──────────────────────────────────────────────────────────
    def replay(self, operators: Iterable[dict[str, Any]], duration: float = 1.0) -> list[dict[str, float]]:
        """Re-integrate a fresh field from the same seed under a glyph script."""
        series = [{"t": 0.0, "R": self.measure()["R"]}]
        for item in operators:
            self.apply(item.get("operator", "perturb"), item.get("parameters"))
            self.advance(duration)
            m = self.measure()
            series.append({"t": round(m["t"], 3), "R": m["R"]})
        return series
