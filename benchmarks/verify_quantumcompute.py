"""Reproduce numerical observations and encrypted FullCycle recovery receipts."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.backends.openssl.backend import backend
from xi_quantum.__main__ import fullcycle_demo
from xi_quantum.algorithms import grover, shor, jacobian_flow
from xi_quantum.common import PROFILES, digest
from xi_quantum.glyphsafe import Identity, seal, restore, SUITE
from xi_quantum.tessera import engine_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--profile", choices=PROFILES, default="mobile")
    args = parser.parse_args()
    start, cpu_start = time.perf_counter(), time.process_time()
    profile = PROFILES[args.profile]
    grover_results = [grover(qubits=q, marked=m, iterations=r, shots=4096, seed=args.seed, profile=profile)
                      for q, m, r in [(2, ["11"], 1), (3, ["101"], 2), (4, ["0011", "1011"], 2)]]
    shor_results = [shor(N=N, a=2, shots=256, seed=args.seed, profile=profile)
                    for N in (15, 21, 35, 77, 143, 221)]
    assert all(result["factor_product_verified"] for result in shor_results)
    flow = jacobian_flow(profile=profile)
    raw = (ROOT / "Ξ.QuantumCompute.yaml").read_bytes()
    a, b = Identity.generate(), Identity.generate()
    crypto_start = time.perf_counter()
    sizes = []
    for sequence in range(1, 11):
        packet = seal(raw, a, b.public(), sequence=sequence)
        assert restore(packet, b, {a.node_id: a.public()})["raw"] == raw
        sizes.append(len(packet))
    crypto_seconds = time.perf_counter() - crypto_start
    fullcycle = fullcycle_demo(raw, profile, args.home)
    replay = fullcycle_demo(raw, profile, args.home)
    assert replay["sender"]["executed_this_call"] == replay["receiver"]["executed_this_call"] == 0
    assert fullcycle["receiver"]["integrity"] == replay["receiver"]["integrity"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = ["xi_quantum/algorithms.py", "xi_quantum/glyphsafe.py", "xi_quantum/thinksync.py",
             "xi_quantum/tessera.py", "xi_quantum/runtime.py", "xi_quantum/ledger.py",
             "xi_world/kernel.py", "xi_field/operators.py", "tests/test_xi_quantumcompute.py",
             ".github/workflows/python-package-conda.yml", "benchmarks/verify_quantumcompute.py"]
    repository = "https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-."
    report = {"schema": "xi.quantumcompute.verification.v2", "seed": args.seed,
        "source_commit": commit, "engine_sha256": engine_hash(),
        "sources": {path: {"sha256": digest((ROOT / path).read_bytes()),
                             "url": f"{repository}/blob/{commit}/{path}"} for path in paths},
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "openssl": backend.openssl_version_text(),
                        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "PyYAML", "cryptography")}},
        "profile": profile.__dict__, "grover": grover_results, "shor": shor_results,
        "jacobian_flow": flow, "glyphsafe": {"suite": SUITE, "exact_byte_roundtrips": 10,
             "payload_bytes": len(raw), "encrypted_packet_bytes": sizes,
             "wall_seconds": crypto_seconds}, "fullcycle": fullcycle,
        "second_fullcycle": {"sender_executed": replay["sender"]["executed_this_call"],
                             "receiver_executed": replay["receiver"]["executed_this_call"],
                             "unchanged_receiver_integrity": True},
        "scope": {"algorithms": "ideal classical state-vector simulation",
                  "transport": "two owned local nodes; explicit encrypted handoff",
                  "costs": "host software wall/CPU costs and process-wide RSS high-water mark"},
        "costs": {"wall_seconds": time.perf_counter() - start, "cpu_seconds": time.process_time() - cpu_start,
                  "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output.read_bytes()),
                      "source_commit": commit, "factors": {r["N"]: r["factors"] for r in shor_results},
                      "fullcycle_integrity": fullcycle["receiver"]["integrity"]["ok"]}))


if __name__ == "__main__":
    main()
