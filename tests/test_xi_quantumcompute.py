from __future__ import annotations

import base64
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from xi_quantum.algorithms import grover, shor, jacobian_flow
from xi_quantum.common import Profile, QuantumComputeError, digest
from xi_quantum.glyphsafe import Identity, seal, restore, encode_digest, decode_tile, inspect_glyphsafe
from xi_quantum._vendor.xi_crypto.wire import ProtocolError, canonical as crypto_canonical, parse
from xi_quantum.runtime import Runtime, ExecutionGrant
from xi_quantum.tessera import compile_program
from xi_quantum.thinksync import ThinkSync, sweep_inbox
from xi_world.kernel import WorldError


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/QuantumCompute.FullCycle.v2.xi"


def grant(raw):
    plan = compile_program(raw)
    return ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))


class AlgorithmTests(unittest.TestCase):
    def test_grover_amplification_multiple_targets_and_seeded_witness(self):
        for qubits, marked, rounds in [(2, ["11"], 1), (3, ["101"], 2), (4, ["0011", "1011"], 2)]:
            result = grover(qubits=qubits, marked=marked, iterations=rounds, shots=2048, seed=21)
            expected = math.sin((2 * rounds + 1) * math.asin(math.sqrt(len(marked) / 2**qubits))) ** 2
            self.assertAlmostEqual(result["success_probability"], expected, places=12)
            self.assertAlmostEqual(result["norm_squared"], 1, places=12)
            self.assertEqual(result["counts"], grover(qubits=qubits, marked=marked, iterations=rounds, shots=2048, seed=21)["counts"])
            self.assertEqual(sum(result["counts"].values()), 2048)

    def test_shor_recovers_periods_and_factors_beyond_legacy_mobile_cutoff(self):
        for N, order, factors in [(15, 4, [3, 5]), (21, 6, [3, 7]), (35, 12, [5, 7]),
                                   (77, 30, [7, 11]), (143, 60, [11, 13]), (221, 24, [13, 17])]:
            with self.subTest(N=N):
                result = shor(N=N, a=2, shots=256, seed=17)
                self.assertEqual(result["order"], order)
                self.assertEqual(result["factors"], factors)
                self.assertTrue(result["factor_product_verified"])
                self.assertAlmostEqual(result["norm_squared"], 1, places=12)
                self.assertEqual(sum(result["phase_counts"].values()), 256)
        self.assertEqual(shor(N=21, a=3)["execution"], "classical gcd shortcut")

    def test_conditional_shor_matches_independent_dense_controlled_modular_circuit(self):
        for N in (15, 21):
            precision, a, shots, seed = 6, 2, 1024, 11
            Q, M = 1 << precision, 1 << N.bit_length()
            state = np.zeros((Q, M), dtype=complex)
            state[:, 1] = Q ** -0.5
            # Independently apply each controlled modular permutation to the
            # full joint state, then an explicit Fourier matrix (no FFT).
            for bit in range(precision):
                multiplier = pow(a, 1 << bit, N)
                out = np.zeros_like(state)
                for x in range(Q):
                    for y in range(M):
                        target = multiplier * y % N if y < N and x & (1 << bit) else y
                        out[x, target] += state[x, y]
                state = out
            result = shor(N=N, a=a, precision=precision, shots=shots, seed=seed)
            observed = result["work_measurement"]
            clock = state[:, observed]
            clock /= np.linalg.norm(clock)
            fourier = np.exp(-2j * math.pi * np.outer(np.arange(Q), np.arange(Q)) / Q) / math.sqrt(Q)
            probabilities = np.abs(fourier @ clock) ** 2
            rng, expected = random.Random(seed + 1), {}
            for _ in range(shots):
                needle, cumulative = rng.random(), 0
                for y, probability in enumerate(probabilities):
                    cumulative += probability
                    if needle < cumulative:
                        expected[str(y)] = expected.get(str(y), 0) + 1
                        break
            self.assertEqual(result["phase_counts"], expected)

    def test_jacobian_and_curvature_match_known_phase_response_and_flow_is_witnessed(self):
        result = jacobian_flow(phase=math.pi / 2)
        first = result["history"][0]
        self.assertAlmostEqual(first["success_probability"], 0.625, places=12)
        self.assertAlmostEqual(first["jacobian"][0][0], 0.375, places=7)
        self.assertAlmostEqual(first["curvature"], 0, places=6)
        self.assertGreater(result["final_success_probability"], 0.999)
        shifted = jacobian_flow(phase=math.pi / 2 + 2 * math.pi, steps=1)
        self.assertAlmostEqual(shifted["history"][0]["jacobian"][0][0], first["jacobian"][0][0], places=7)
        for row in result["history"]:
            self.assertGreaterEqual(row["next_success_probability"] + 1e-12, row["success_probability"])

    def test_resource_budget_precedes_allocation_and_invalid_inputs_fail(self):
        with patch("xi_quantum.algorithms.np.fromiter", side_effect=AssertionError("allocation attempted")):
            with self.assertRaisesRegex(QuantumComputeError, "budget"):
                shor(N=2**51 - 1)
        with self.assertRaises(QuantumComputeError):
            grover(qubits=30, marked=[0], profile=Profile("tiny", 1))
        for kwargs in ({"marked": ["1"]}, {"marked": [1, 1]}, {"iterations": True}, {"shots": 0},
                       {"oracle_phase": float("nan")}, {"seed": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(QuantumComputeError):
                grover(**kwargs)


class GlyphSafeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a, cls.b, cls.other = Identity.generate(), Identity.generate(), Identity.generate()

    def test_exact_glyphsha_alphabet_and_legacy_body_hash_coverage(self):
        hexdigits = "0123456789abcdef" * 4
        expected = "\n".join(["∴Ω⧂⋈Ξ⟐⊚◇", "✦⟁∵☉◬⌬⧉∞"] * 4)
        self.assertEqual(encode_digest(hexdigits), expected)
        self.assertEqual(decode_tile(expected), hexdigits)
        body = "∴Ω⧂ ⊚\ufe0e e\u0301"
        declared = hashlib.sha256(body.encode()).hexdigest()
        raw = f"[glyphsafe:v1]\r\nhash: SHA256={declared}\r\nmeta: first\r\n```glyph\r\n{body}\r\n```\r\n[/glyphsafe]\r\n".encode()
        altered = raw.replace(b"meta: first", b"meta: other")
        self.assertEqual(inspect_glyphsafe(raw)["body_status"], "match")
        self.assertEqual(inspect_glyphsafe(altered)["body_status"], "match")
        self.assertNotEqual(inspect_glyphsafe(raw)["raw_sha256"], inspect_glyphsafe(altered)["raw_sha256"])

    def test_pq_signed_encryption_restores_binary_and_unicode_exactly(self):
        raw = b"\x00\xff" + "⟁Ξ₀⇀Ξ∴Ω≈∅\r\ne\u0301 \ufe0e\n".encode()
        wire = seal(raw, self.a, self.b.public(), sequence=7)
        result = restore(wire, self.b, {self.a.node_id: self.a.public()})
        self.assertEqual(result["raw"], raw)
        self.assertEqual(decode_tile(result["glyphsha"]), digest(raw))
        self.assertNotIn(base64.b64encode(raw), wire)
        self.assertEqual(result["sequence"], 7)

    def test_tampering_wrong_recipient_scope_signer_and_suite_are_rejected(self):
        wire = seal(b"payload", self.a, self.b.public(), sequence=1)
        for field, value in [("sequence", 2), ("scope", "wrong"), ("audience", "wrong"),
                             ("suite", "SHA256-only"), ("recipient", self.other.node_id)]:
            tampered = parse(wire)
            tampered["protected"][field] = value
            with self.subTest(field=field), self.assertRaises(ProtocolError):
                restore(crypto_canonical(tampered), self.b, {self.a.node_id: self.a.public()})
        tampered = parse(wire)
        ciphertext = bytearray(base64.b64decode(tampered["ciphertext"]))
        ciphertext[0] ^= 1
        tampered["ciphertext"] = base64.b64encode(ciphertext).decode()
        with self.assertRaises(ProtocolError):
            restore(crypto_canonical(tampered), self.b, {self.a.node_id: self.a.public()})
        with self.assertRaises(ProtocolError):
            restore(wire, self.other, {self.a.node_id: self.a.public()})
        with self.assertRaises(ProtocolError):
            restore(wire, self.b, {})

    def test_owner_keys_survive_restart_with_private_file_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "identity.secret.json"
            first = Identity.load_or_create(path)
            second = Identity.load_or_create(path)
            self.assertEqual(first.public(), second.public())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_recovered_modules_match_pinned_upstream_hashes(self):
        manifest = json.loads((ROOT / "xi_quantum/_vendor/UPSTREAM.json").read_text())
        for item in manifest:
            raw = (ROOT / item["path"]).read_bytes()
            if item["change"] == "relative import only":
                raw = raw.replace(b"from .spiral_covenant import", b"from operators.spiral_covenant import")
            self.assertEqual(digest(raw), item["original_sha256"], item["path"])


class FullCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.raw = EXAMPLE.read_bytes()
        self.a, self.b = Runtime(self.root / "a"), Runtime(self.root / "b")
        self.ia, self.ib = Identity.generate(), Identity.generate()
        self.ba = ThinkSync(self.a, self.ia)
        self.bb = ThinkSync(self.b, self.ib, trusted_senders={self.ia.node_id: self.ia.public()})

    def tearDown(self):
        self.temp.cleanup()

    def test_interrupt_encrypt_transfer_restore_resume_and_idempotent_replay(self):
        first = self.a.run(self.raw, grant=grant(self.raw), stop_after=2)
        wire = self.ba.queue(self.raw, self.ib.public(), checkpoint=self.a.checkpoint(first))
        self.assertEqual(wire, self.ba.queue(self.raw, self.ib.public(), checkpoint=self.a.checkpoint(first)))
        receipt = self.bb.receive(wire)
        self.assertTrue(self.bb.receive(wire)["duplicate"])
        self.assertFalse(receipt["execution_authorized_by_receipt"])
        self.assertEqual(self.b.source(receipt["source_sha256"]), self.raw)
        self.assertEqual(self.b.kernel.events(first["world_id"]), [])
        second = self.b.run(self.raw, grant=grant(self.raw), recovered=self.bb.checkpoint(receipt["packet_sha256"]))
        self.assertTrue(second["closed"])
        self.assertEqual(second["restored_from_peer_this_call"], 2)
        self.assertEqual(second["executed_this_call"], 3)
        self.assertEqual(second["steps"][1]["origin"]["original_event_id"], first["steps"][1]["event_id"])
        with patch.object(Runtime, "_execute", side_effect=AssertionError("completed job ran again")):
            replay = Runtime(self.b.home).run(self.raw, grant=grant(self.raw))
        self.assertEqual(replay["integrity"], second["integrity"])
        self.assertEqual(replay["executed_this_call"], 0)
        self.assertTrue(second["integrity"]["ok"])

    def test_source_and_transport_integrity_never_grant_execution(self):
        self.bb.receive(self.ba.queue(self.raw, self.ib.public()))
        for authorization in (None, ExecutionGrant("0" * 64, frozenset({"Grover"})),
                              ExecutionGrant(digest(self.raw), frozenset({"Grover"}))):
            with self.assertRaises(QuantumComputeError):
                self.b.run(self.raw, grant=authorization)
        with self.b.kernel._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM worlds").fetchone()[0], 0)

    def test_stale_sequences_reject_and_outbox_key_conflicts_preserve_evidence(self):
        old = self.ba.queue(b"old exact source", self.ib.public(), request_key="old")
        new = self.ba.queue(b"new exact source", self.ib.public(), request_key="new")
        self.bb.receive(new)
        with self.assertRaisesRegex(QuantumComputeError, "stale"):
            self.bb.receive(old)
        with self.assertRaisesRegex(QuantumComputeError, "different transfer"):
            self.ba.queue(b"different", self.ib.public(), request_key="new")
        self.assertEqual(new, self.ba.queue(b"new exact source", self.ib.public(), request_key="new"))

    def test_unknown_dialect_remains_recoverable_without_execution(self):
        raw = "unrecognized dialect\r\n⟁Ξ₀⇀Ξ∴Ω≈∅\n".encode()
        incoming = self.bb.receive(self.ba.queue(raw, self.ib.public()))
        self.assertEqual(self.b.source(incoming["source_sha256"]), raw)
        with self.assertRaises(QuantumComputeError):
            compile_program(raw)

    def test_tessera_bindings_parser_and_bad_sources(self):
        self.assertEqual((ROOT / "Ξ.QuantumCompute.yaml").read_bytes(), self.raw)
        expression = b'schema: xi.quantumcompute.program.v2\ndialect: QuantumCompute.Stack.v2\nsteps:\n - \'\xce\x9e.Grover({"qubits": 2, "marked": ["11"]})\'\n - \'\xce\x9e.Seal()\'\n'
        self.assertEqual(compile_program(expression).steps[0]["operator"], "Grover")
        for raw in (self.raw.replace("glyph: ∴".encode(), "glyph: ⊚".encode(), 1),
                    self.raw.replace(b"schema:", b"schema: duplicate\nschema:", 1),
                    self.raw.replace(b"QuantumCompute.Stack.v2", b"QuantumFieldQEC.v1"),
                    b"!!python/object/apply:os.system [echo bad]", self.raw.replace(b"operator: Seal", b"operator: Rest")):
            with self.subTest(raw=raw[:80]), self.assertRaises(QuantumComputeError):
                compile_program(raw)

    def test_bridge_daemon_retains_packets_rests_after_restart_and_never_executes(self):
        inbox = self.root / "incoming"
        inbox.mkdir()
        wire = self.ba.queue(self.raw, self.ib.public())
        (inbox / "accepted.glyphsafe").write_bytes(wire)
        (inbox / "bad.glyphsafe").write_bytes(b"tampered packet")
        (inbox / "link.glyphsafe").symlink_to(inbox / "accepted.glyphsafe")
        first = sweep_inbox(self.bb, inbox)
        self.assertEqual(len(first["received"]), 1)
        self.assertEqual(len(first["failures"]), 1)
        self.assertFalse(first["received"][0]["execution_authorized_by_receipt"])
        self.assertEqual((inbox / "accepted.glyphsafe").read_bytes(), wire)
        restarted = ThinkSync(Runtime(self.b.home), self.ib,
                              trusted_senders={self.ia.node_id: self.ia.public()})
        second = sweep_inbox(restarted, inbox)
        self.assertEqual(second["movement"], "rest")
        self.assertEqual(second["received"], [])
        with self.b.kernel._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM worlds").fetchone()[0], 0)
        revoked = ThinkSync(self.b, self.ib)
        self.assertEqual(len(sweep_inbox(revoked, inbox)["failures"]), 2)

    def test_cli_pack_bridge_and_resume_share_recoverable_public_identity_contract(self):
        a, b = self.root / "cli-a", self.root / "cli-b"

        def cli(home, *args):
            return json.loads(subprocess.check_output(
                [sys.executable, "-m", "xi_quantum", "--home", str(home), *map(str, args)], cwd=ROOT))

        ap, bp = self.root / "a.public.json", self.root / "b.public.json"
        cli(a, "identity", "--output", ap)
        cli(b, "identity", "--output", bp)
        partial = self.root / "partial.json"
        cli(a, "run", EXAMPLE, "--stop-after", "2", "--output", partial)
        inbox = self.root / "cli-inbox"
        packet = inbox / "partial.glyphsafe"
        cli(a, "pack", EXAMPLE, "--recipient", bp, "--checkpoint", partial, "--output", packet)
        receipt = cli(b, "bridge", "--inbox", inbox, "--trusted", ap)["received"][0]
        resumed = cli(b, "resume", receipt["packet_sha256"], "--sender", ap)
        self.assertTrue(resumed["closed"])
        self.assertEqual(resumed["restored_from_peer_this_call"], 2)
        self.assertEqual(resumed["executed_this_call"], 3)
        self.assertEqual(cli(b, "run", EXAMPLE)["executed_this_call"], 0)
        self.assertEqual(set(json.loads(ap.read_text())), {"schema", "signing_key", "encryption_key"})

    def test_rest_keeps_continuation_without_waking_then_explicitly_resumes(self):
        raw = 'schema: xi.quantumcompute.program.v2\ndialect: QuantumCompute.Stack.v2\nsteps:\n - {glyph: ≈∅, operator: Rest}\n - {glyph: ⊚, operator: Seal}\n'.encode()
        first = self.a.run(raw, grant=grant(raw))
        self.assertFalse(first["closed"])
        self.assertEqual(first["completed_steps"], 1)
        self.assertEqual(first["steps"][0]["route"]["movement"], "rest")
        self.assertEqual(first["steps"][0]["route"]["targets"], [])
        second = Runtime(self.a.home).run(raw, grant=grant(raw))
        self.assertTrue(second["closed"])
        self.assertEqual(second["completed_steps"], 2)

    def test_fullcycle_parallax_pauses_the_walk_and_preserves_next_step(self):
        operators = [("⋈", "Grover"), ("∴", "Shor"), ("⧖", "JacobianFlow"), ("⧂", "PhaseCodeBenchmark")]
        lines = ["schema: xi.quantumcompute.program.v2", "dialect: QuantumCompute.Stack.v2", "steps:"]
        for i in range(160):
            glyph, name = operators[i % 4]
            lines.append(f" - {{glyph: {glyph}, operator: {name}, phase: 3.04}}")
        lines.append(" - {glyph: ⊚, operator: Seal}")
        raw = "\n".join(lines).encode()
        with patch.object(Runtime, "_execute", return_value={"routing_test": True}):
            result = self.a.run(raw, grant=grant(raw))
        self.assertFalse(result["closed"])
        self.assertLess(result["completed_steps"], 161)
        self.assertEqual(result["steps"][-1]["route"]["next_operator"], "Parallax")
        self.assertTrue(result["integrity"]["ok"])

    def test_peer_checkpoint_tampering_and_direct_unverified_restore_fail(self):
        result = self.a.run(self.raw, grant=grant(self.raw), stop_after=1)
        checkpoint = self.a.checkpoint(result)
        for field, value in (("source_sha256", "0" * 64), ("engine_sha256", "0" * 64),
                             ("world_id", "different-world")):
            altered = copy.deepcopy(checkpoint)
            altered[field] = value
            with self.assertRaises((QuantumComputeError, WorldError)):
                self.ba.queue(self.raw, self.ib.public(), checkpoint=altered)
        altered = copy.deepcopy(checkpoint)
        altered["events"][-1]["data"]["result"]["success_probability"] = 0
        with self.assertRaises(QuantumComputeError):
            self.ba.queue(self.raw, self.ib.public(), checkpoint=altered)
        with self.assertRaises(QuantumComputeError):
            self.b.run(self.raw, grant=grant(self.raw), recovered=checkpoint)

    def test_executor_lease_and_registered_actor_cannot_be_bypassed(self):
        with (self.a.home / "execution.lock").open("a") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(QuantumComputeError, "Another executor"):
                self.a.run(self.raw, grant=grant(self.raw))
        result = self.a.run(self.raw, grant=grant(self.raw), stop_after=0)
        with self.assertRaises(WorldError):
            self.a.kernel.apply(result["world_id"], "world:genesis", "quantum.transition", "quantum-stack",
                                idempotency_key="foreign-actor", data={"index": 0})
        self.assertEqual(self.a.kernel.verify(result["world_id"])["event_count"], 1)

    def test_separate_process_restart_resumes_only_uncommitted_steps(self):
        home = str(self.root / "process")
        command = [sys.executable, "-m", "xi_quantum", "--home", home, "run", str(EXAMPLE)]
        partial = json.loads(subprocess.check_output(command + ["--stop-after", "2"], cwd=ROOT))
        resumed = json.loads(subprocess.check_output(command, cwd=ROOT))
        replay = json.loads(subprocess.check_output(command, cwd=ROOT))
        self.assertEqual(partial["completed_steps"], 2)
        self.assertEqual(resumed["executed_this_call"], 3)
        self.assertEqual(replay["executed_this_call"], 0)
        self.assertEqual(resumed["integrity"], replay["integrity"])

    def test_owner_token_api_and_existing_http_surface(self):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, {"FORGECORE_DIR": str(self.root / "http"),
                                      "XI_FIELD_DB": str(self.root / "http/field.sqlite3"),
                                      "XI_QUANTUM_HOME": str(self.root / "http/quantum"),
                                      "XI_QUANTUM_API_TOKEN": "test-owner-token"}):
            from server import app
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/quantumcompute").status_code, 200)
                self.assertEqual(client.post("/api/quantumcompute/run", json={"source": self.raw.decode()}).status_code, 403)
                headers = {"X-Xi-Quantum-Token": "test-owner-token"}
                result = client.post("/api/quantumcompute/run", json={"source": self.raw.decode()}, headers=headers)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertTrue(result.json()["closed"])
                self.assertEqual(client.get("/api/quantumcompute/example").json()["source"].encode(), self.raw)
                observer = client.get("/api/quantumcompute/example?name=observer")
                self.assertEqual(observer.status_code, 200)
                self.assertEqual(observer.json()["source"].encode(), (ROOT / "examples/QuantumCompute.Observer.v1.xi").read_bytes())
                self.assertEqual(client.get("/api/quantumcompute/example?name=../../etc/passwd").status_code, 400)
                for path in ("/health", "/api/capsules", "/api/quantum-field"):
                    self.assertEqual(client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
