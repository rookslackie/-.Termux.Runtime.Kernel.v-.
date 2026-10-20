"""Run, transfer and resume the observer experiment and recovered QR capsule."""
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

from xi_quantum.common import PROFILES, QuantumComputeError, digest
from xi_quantum.glyphsafe import Identity, SUITE
from xi_quantum.runtime import Runtime, ExecutionGrant
from xi_quantum.tessera import compile_program
from xi_quantum.thinksync import ThinkSync


def grant(raw):
    plan = compile_program(raw)
    return ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))


def verify(home, raw):
    home = Path(home)
    a, b = Runtime(home / "node-a"), Runtime(home / "node-b")
    ka = Identity.load_or_create(a.home / "identity.secret.json")
    kb = Identity.load_or_create(b.home / "identity.secret.json")
    sender = ThinkSync(a, ka)
    receiver = ThinkSync(b, kb, trusted_senders={ka.node_id: ka.public()})
    initial = a.run(raw, grant=grant(raw), stop_after=0)
    partial = a.run(raw, grant=grant(raw), stop_after=max(0, 1 - initial["completed_steps"]))
    wire = sender.queue(raw, kb.public(), checkpoint=a.checkpoint(partial))
    received = receiver.receive(wire)
    completed = b.run(raw, grant=grant(raw), recovered=receiver.checkpoint(received["packet_sha256"]))
    replay = Runtime(b.home).run(raw, grant=grant(raw))
    assert replay["executed_this_call"] == 0 and completed["integrity"] == replay["integrity"]
    assert receiver.receive(wire)["duplicate"]
    kernel = (ROOT / "recovered/2026-10-20/StructuralKernel.QR.v1.xi").read_bytes()
    try:
        compile_program(kernel)
    except QuantumComputeError:
        opaque = True
    else:
        raise AssertionError("Recovered kernel was silently interpreted as a different executable dialect")
    restored = receiver.receive(sender.queue(kernel, kb.public()))
    assert b.source(restored["source_sha256"]) == kernel
    return {"sender": partial, "receiver": completed, "transport": received,
            "replay_executed_steps": replay["executed_this_call"], "unchanged_receiver_integrity": True,
            "crypto_suite": SUITE, "checkpoint_encrypted_bytes": len(wire),
            "kernel_recovery": {"source_sha256": digest(kernel), "payload_bytes": len(kernel),
                                "exact_encrypted_roundtrip": True, "dialect_preserved_as_opaque": opaque,
                                "execution_authorized_by_receipt": restored["execution_authorized_by_receipt"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--program", type=Path, default=ROOT / "examples/QuantumCompute.Observer.v1.xi")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start, cpu = time.perf_counter(), time.process_time()
    result = verify(args.home, args.program.read_bytes())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = ["xi_quantum/observer.py", "xi_quantum/tessera.py", "xi_quantum/runtime.py", "xi_field/operators.py",
             "tests/test_xi_observer.py", "examples/QuantumCompute.Observer.v1.xi", "benchmarks/verify_observer.py"]
    report = {"schema": "xi.observer-verification.v1", "source_commit": commit,
        "sources": {p: {"sha256": digest((ROOT / p).read_bytes()),
                         "url": f"https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./blob/{commit}/{p}"} for p in paths},
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "PyYAML", "cryptography")}},
        "profile": PROFILES["mobile"].__dict__, "execution": result,
        "cost": {"wall_seconds": time.perf_counter() - start, "cpu_seconds": time.process_time() - cpu,
                 "process_peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), "sha256": digest(args.output.read_bytes()),
                      "source_commit": commit, "integrity": result["receiver"]["integrity"]["ok"],
                      "kernel_exact_bytes": result["kernel_recovery"]["exact_encrypted_roundtrip"]}))


if __name__ == "__main__":
    main()
