#!/usr/bin/env python3
"""Reproduce the Living Circuit numerical and encrypted-continuity receipt."""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xi_quantum.algorithms import grover
from xi_quantum.circuits import phase_code, shor_code, qft
from xi_quantum.common import Profile, digest
from xi_quantum.spectral import vqe, vqe_pea, phase_estimation
from xi_quantum.signal_lab import signal_lab
from xi_quantum.tessera import compile_program, engine_hash
from xi_quantum.__main__ import fullcycle_demo


def run():
    recovered = ROOT / "recovered/2026-10-21"
    sources = json.loads((recovered/"sources.json").read_text())
    for item in sources["files"]:
        assert digest((recovered/item["name"]).read_bytes()) == item["sha256"]
    with (recovered/"metrics_grover.csv").open() as file:
        rows = list(csv.DictReader(file))
    comparison = []
    for row in rows:
        result = grover(qubits=6, marked=[43], iterations=int(row["iteration"]), shots=16)
        error = abs(result["success_probability"]-float(row["success_prob"]))
        assert error < 5.1e-7
        comparison.append({"iteration": int(row["iteration"]), "attached_probability": float(row["success_prob"]),
                           "computed_probability": result["success_probability"], "absolute_error": error})
    with (recovered/"metrics_vqe.csv").open() as file:
        vqe_rows = list(csv.DictReader(file))
    phase_cases, shor_cases = [], []
    for state in ["zero", "one", "plus", "minus", "T", "y_plus"]:
        for faults in [[], [0], [1], [2]]:
            result = phase_code(state=state, faults=faults)
            assert result["recovered_state_fidelity"] > 1-1e-12
            phase_cases.append({"state": state, "faults": faults, "fidelity": result["recovered_state_fidelity"]})
    for state in ["zero", "plus", "T", "y_plus"]:
        for pauli in "XYZ":
            for qubit in range(9):
                result = shor_code(state=state, faults=[{"pauli": pauli, "qubit": qubit}])
                assert result["recovered_state_fidelity"] > 1-1e-12
                shor_cases.append({"state": state, "pauli": pauli, "qubit": qubit,
                                   "fidelity": result["recovered_state_fidelity"]})
    variational = vqe()
    spectral = vqe_pea(precision=9)
    assert abs(variational["variational_gap"]) < 1e-9
    assert abs(spectral["pea"]["energy_error_vs_reference"]) <= spectral["pea"]["energy_resolution"]/2 + 1e-9
    qpe = phase_estimation(phase=.375, precision=5)
    assert qpe["estimated_phase"] == .375
    new_glyph = (ROOT/"examples/QuantumCompute.NewGlyph.v3.xi").read_bytes()
    with tempfile.TemporaryDirectory(prefix="xi-living-circuit-verify-") as temporary:
        transported = fullcycle_demo(new_glyph, Profile(), temporary)
    signals = signal_lab()
    assert [p["hz"] for p in signals["fft_peaks"][:2]] == [50, 120]
    return {"schema": "xi.living-circuit.verification.v1", "date": "2026-10-21",
        "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "engine_sha256": engine_hash(), "execution": "classical numerical simulation and actual PQC byte transport",
        "environment": {"python": platform.python_version(),
            "dependencies": {p: importlib.metadata.version(p) for p in ["numpy", "cryptography", "PyYAML"]}},
        "recovered_sources": {"files": len(sources["files"]), "all_hashes_match": True},
        "grover_attached_curve": {"rows": comparison, "tolerance_for_six_decimal_csv": 5.1e-7},
        "vqe_attached_curve": {"rows": len(vqe_rows), "first_energy": float(vqe_rows[0]["energy_hartree"]),
            "last_energy": float(vqe_rows[-1]["energy_hartree"]),
            "status": "preserved numeric reference; producer Hamiltonian, ansatz, and energy offset were not supplied"},
        "phase_code": {"cases": phase_cases, "minimum_fidelity": min(c["fidelity"] for c in phase_cases),
            "two_fault_probe": phase_code(state="T", faults=[0, 1])["recovered_state_fidelity"]},
        "shor_code": {"cases": shor_cases, "minimum_fidelity": min(c["fidelity"] for c in shor_cases)},
        "vqe": variational, "vqe_pea": spectral, "qpe": qpe,
        "qft": qft(qubits=3, basis=5),
        "signal": {"input_kind": signals["input_kind"], "fft_peaks": signals["fft_peaks"][:2]},
        "glyph_compilation": compile_program(new_glyph).as_dict(), "encrypted_fullcycle": transported}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"benchmarks/living-circuit/results.json")
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"output": str(args.output), "source_revision": result["source_revision"],
        "engine_sha256": result["engine_sha256"], "source_files": result["recovered_sources"]["files"],
        "phase_code_cases": len(result["phase_code"]["cases"]), "shor_code_cases": len(result["shor_code"]["cases"]),
        "vqe_energy": result["vqe"]["energy"], "pea_energy": result["vqe_pea"]["pea"]["estimated_energy"],
        "exact_source_roundtrip": result["encrypted_fullcycle"]["exact_source_roundtrip"]}))


if __name__ == "__main__":
    main()
