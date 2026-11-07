"""Explicit execution resources and deterministic data commitments."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math


class QuantumComputeError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedCheckpoint:
    """Local bridge result; never constructed from executable capsule fields."""
    checkpoint: dict
    sender: str
    envelope_sha256: str


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def integer(value, name, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise QuantumComputeError(f"{name} must be an integer >= {minimum}" +
                                  (f" and <= {maximum}" if maximum is not None else ""))
    return value


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise QuantumComputeError(f"{name} must be finite")
    return float(value)


@dataclass(frozen=True)
class Profile:
    name: str = "mobile"
    memory_mib: int = 64
    max_iterations: int = 4096

    def __post_init__(self):
        integer(self.memory_mib, "memory_mib", 1)
        integer(self.max_iterations, "max_iterations", 1)

    def reserve(self, qubits: int, bytes_per_basis: int = 96) -> dict:
        integer(qubits, "qubits", 1)
        # Compare bit lengths before constructing a potentially enormous 2**n.
        available = self.memory_mib * 1024 * 1024
        if qubits > (available // bytes_per_basis).bit_length() - 1:
            raise QuantumComputeError(
                f"{qubits} simulated qubits exceed {self.name}'s {self.memory_mib} MiB budget "
                f"({bytes_per_basis} estimated workspace bytes per basis state); choose a larger profile")
        return {"profile": self.name, "memory_budget_mib": self.memory_mib,
                "simulated_qubits": qubits, "basis_states": 1 << qubits,
                "estimated_workspace_bytes": bytes_per_basis * (1 << qubits)}


PROFILES = {"mobile": Profile(), "desktop": Profile("desktop", 512, 16384),
            "workstation": Profile("workstation", 2048, 65536)}
