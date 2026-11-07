"""Local CLI for Ξ.QuantumCompute FullCycle v2."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import time

from . import __version__
from .common import PROFILES, Profile, QuantumComputeError
from .glyphsafe import Identity, public_id, SUITE, seal, restore
from .runtime import Runtime, ExecutionGrant
from .tessera import compile_program
from .thinksync import ThinkSync, sweep_inbox


def _grant(raw):
    plan = compile_program(raw)
    return ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))


def fullcycle_demo(raw, profile, root):
    """Owned local nodes: execute, interrupt, seal, transfer, restore, resume."""
    root = Path(root)
    alice, bob = Runtime(root / "node-a", profile=profile), Runtime(root / "node-b", profile=profile)
    key_a = Identity.load_or_create(alice.home / "identity.secret.json")
    key_b = Identity.load_or_create(bob.home / "identity.secret.json")
    sender = ThinkSync(alice, key_a)
    receiver = ThinkSync(bob, key_b, trusted_senders={key_a.node_id: key_a.public()})
    initial = alice.run(raw, grant=_grant(raw), stop_after=0)
    first = alice.run(raw, grant=_grant(raw), stop_after=max(0, 2 - initial["completed_steps"]))
    wire = sender.queue(raw, key_b.public(), checkpoint=alice.checkpoint(first))
    accepted = receiver.receive(wire)
    duplicate = receiver.receive(wire)
    second = bob.run(raw, grant=_grant(raw), recovered=receiver.checkpoint(accepted["packet_sha256"]))
    replay = Runtime(bob.home, profile=profile).run(raw, grant=_grant(raw))
    assert bob.source(accepted["source_sha256"]) == raw
    assert replay["integrity"] == second["integrity"] and replay["executed_this_call"] == 0
    return {"schema": "xi.quantumcompute.fullcycle-test.v2", "profile": profile.name,
            "crypto_suite": SUITE, "source_sha256": accepted["source_sha256"],
            "exact_source_roundtrip": True, "duplicate_packet_is_idempotent": duplicate["duplicate"],
            "resume_without_reexecution": True, "sender": first, "receiver": second,
            "transport": accepted, "encrypted_packet_bytes": len(wire)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=".xi/quantumcompute")
    parser.add_argument("--profile", choices=PROFILES, default="mobile")
    parser.add_argument("--memory-mib", type=int)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    sub.add_parser("catalog")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=7476)
    serve_parser.add_argument("--allowed-origin")
    identity = sub.add_parser("identity")
    identity.add_argument("--output")
    plan = sub.add_parser("compile")
    plan.add_argument("file", type=Path)
    run = sub.add_parser("run")
    run.add_argument("file", type=Path)
    run.add_argument("--stop-after", type=int)
    run.add_argument("--output", type=Path)
    demo = sub.add_parser("fullcycle")
    demo.add_argument("file", type=Path)
    demo.add_argument("--output", type=Path)
    send = sub.add_parser("pack")
    send.add_argument("file", type=Path)
    send.add_argument("--recipient", type=Path, required=True)
    send.add_argument("--output", type=Path, required=True)
    send.add_argument("--checkpoint", type=Path, help="a prior run receipt from this local home")
    receive = sub.add_parser("receive")
    receive.add_argument("packet", type=Path)
    receive.add_argument("--sender", type=Path, required=True)
    resume = sub.add_parser("resume")
    resume.add_argument("packet_sha256")
    resume.add_argument("--sender", type=Path, required=True)
    bridge_parser = sub.add_parser("bridge")
    bridge_parser.add_argument("--inbox", type=Path, required=True)
    bridge_parser.add_argument("--trusted", type=Path, required=True)
    bridge_parser.add_argument("--watch", action="store_true")
    bridge_parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    base = PROFILES[args.profile]
    profile = Profile(base.name, base.memory_mib if args.memory_mib is None else args.memory_mib, base.max_iterations)
    output = getattr(args, "output", None)
    try:
        if args.command == "serve":
            from .service import serve
            serve(args.home, profile=profile, host=args.host, port=args.port, allowed_origin=args.allowed_origin)
            return
        if args.command == "catalog":
            from .workbench import capabilities
            result = capabilities()
        elif args.command == "doctor":
            a, b = Identity.generate(), Identity.generate()
            sample = b"Xi.QuantumCompute/doctor/v2"
            assert restore(seal(sample, a, b.public(), sequence=1), b, {a.node_id: a.public()})["raw"] == sample
            result = {"version": __version__, "python": platform.python_version(), "profile": profile.__dict__,
                      "dependencies": {p: importlib.metadata.version(p) for p in ("numpy", "PyYAML", "cryptography")},
                      "crypto_suite": SUITE, "crypto_roundtrip_verified": True,
                      "transport": "explicit encrypted packet handoff and inbox daemon",
                      "return_operator": "⟁∴Ω"}
        elif args.command == "compile":
            result = compile_program(args.file.read_bytes()).as_dict()
        elif args.command == "identity":
            result = Identity.load_or_create(Path(args.home) / "identity.secret.json").public()
        elif args.command == "run":
            raw = args.file.read_bytes()
            result = Runtime(args.home, profile=profile).run(raw, grant=_grant(raw), stop_after=args.stop_after)
        elif args.command == "fullcycle":
            result = fullcycle_demo(args.file.read_bytes(), profile, args.home)
        else:
            runtime = Runtime(args.home, profile=profile)
            key = Identity.load_or_create(runtime.home / "identity.secret.json")
            if args.command == "bridge":
                peers = json.loads(args.trusted.read_text())
                peers = peers if isinstance(peers, list) else [peers]
                bridge = ThinkSync(runtime, key, trusted_senders={public_id(peer): peer for peer in peers})
                if not 0.1 <= args.interval <= 3600:
                    raise QuantumComputeError("Bridge interval must be 0.1 to 3600 seconds")
                while True:
                    result = sweep_inbox(bridge, args.inbox)
                    if not args.watch:
                        break
                    if result["received"] or result["failures"]:
                        print(json.dumps(result, ensure_ascii=False), flush=True)
                    time.sleep(args.interval)
                print(json.dumps(result, ensure_ascii=False))
                return
            if args.command == "pack":
                peer = json.loads(args.recipient.read_text())
                checkpoint = runtime.checkpoint(json.loads(args.checkpoint.read_text())) if args.checkpoint else None
                wire = ThinkSync(runtime, key).queue(args.file.read_bytes(), peer, checkpoint=checkpoint)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_bytes(wire)
                print(json.dumps({"packet": str(args.output), "bytes": len(wire)}))
                return
            peer = json.loads(args.sender.read_text())
            bridge = ThinkSync(runtime, key, trusted_senders={public_id(peer): peer})
            if args.command == "receive":
                result = bridge.receive(args.packet.read_bytes())
            else:
                verified = bridge.checkpoint(args.packet_sha256)
                raw = runtime.source(verified.checkpoint["source_sha256"])
                result = runtime.run(raw, grant=_grant(raw), recovered=verified)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(rendered)
        print(json.dumps({"output": str(output), "schema": result.get("schema")}))
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
