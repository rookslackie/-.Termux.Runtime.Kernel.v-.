from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from xi_quantum.common import Profile, QuantumComputeError
from xi_quantum.glyphsafe import Identity
from xi_quantum.observer import ObserverContract, Observer, Observation, ShareGrant, reference, run
from xi_quantum.runtime import Runtime, ExecutionGrant
from xi_quantum.tessera import compile_program
from xi_quantum.thinksync import ThinkSync


ROOT = Path(__file__).resolve().parents[1]


def program():
    return json.dumps({"schema": "xi.quantumcompute.program.v2", "dialect": "QuantumCompute.Stack.v2",
        "steps": [{"glyph": "⧂", "operator": "ObserverBenchmark", "parameters": {
                    "sample_counts": [16, 64], "repetitions": 4, "seed": 20261020}},
                  {"glyph": "⊚", "operator": "Seal"}]}).encode()


def grant(raw):
    plan = compile_program(raw)
    return ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))


class ObserverTests(unittest.TestCase):
    def test_unknown_target_remains_null_with_many_wrong_basis_samples(self):
        observer = Observer(ObserverContract("a", ("Z",), 256, 256))
        for i in range(256):
            observer.witness(Observation(str(i), "Z", i % 2))
        result = observer.predict("X")
        self.assertIsNone(result["estimate"])
        self.assertFalse(result["identifiable_from_available_evidence"])
        self.assertEqual(result["interval"], [-1, 1])
        self.assertFalse(result["precision_resolved"])

    def test_measurement_permissions_budgets_and_fifo_memory_are_independent(self):
        observer = Observer(ObserverContract("a", ("X",), 8, 4))
        with self.assertRaises(QuantumComputeError):
            observer.witness(Observation("wrong", "Z", 0))
        for i in range(8):
            observer.witness(Observation(str(i), "X", int(i >= 4)))
        result = observer.predict()
        self.assertEqual(result["direct_samples_used"], 8)
        self.assertEqual(result["retained_outcome_bits"], 4)
        self.assertEqual(result["estimate"], -1)
        self.assertFalse(observer.witness(Observation("7", "X", 1)))
        with self.assertRaises(QuantumComputeError):
            observer.witness(Observation("overflow", "X", 0))
        with self.assertRaises(QuantumComputeError):
            observer.witness(Observation("7", "X", 0))

    def test_sharing_needs_local_directional_grant_and_is_idempotent(self):
        a = Observer(ObserverContract("a", ("Z",), 8, 8))
        b = Observer(ObserverContract("b", ("X",), 8, 8))
        for i in range(8):
            b.witness(Observation(str(i), "X", int(i % 3 == 0)))
        before = a.evidence_digest()
        for authorization in (None, {"status": "Trusted", "glyph_safe": True}, ShareGrant("a", "b", frozenset({"X"}))):
            with self.assertRaises(QuantumComputeError):
                b.share(a, grant=authorization)
            self.assertEqual(a.evidence_digest(), before)
        authorization = ShareGrant("b", "a", frozenset({"X"}))
        first = b.share(a, grant=authorization)
        self.assertEqual(first["accepted_records"], 8)
        self.assertEqual(a.predict()["estimate"], b.predict()["estimate"])
        self.assertEqual(b.share(a, grant=authorization)["accepted_records"], 0)
        self.assertEqual(a.contract.direct_bases, ("Z",))

    def test_wilson_expectation_interval_and_analytic_density_jacobian(self):
        observer = Observer(ObserverContract("x", ("X",), 10, 10))
        for i in range(10):
            observer.witness(Observation(str(i), "X", int(i >= 7)))
        result = observer.predict()
        self.assertAlmostEqual(result["estimate"], 0.4)
        self.assertAlmostEqual(result["interval"][0], -0.2064437049, places=8)
        self.assertAlmostEqual(result["interval"][1], 0.7844174652, places=8)
        ref = reference(math.pi / 3, 0.1)
        self.assertAlmostEqual(ref["X"], 0.4, places=12)
        self.assertAlmostEqual(ref["Z"], 0, places=12)
        self.assertGreaterEqual(ref["minimum_eigenvalue"], 0)
        report = run(sample_counts=[64], repetitions=2)
        self.assertAlmostEqual(report["evaluator_reference"]["phase_jacobian"]["X"], -0.8 * math.sin(math.pi / 3), places=8)
        self.assertAlmostEqual(report["evaluator_reference"]["phase_jacobian"]["Z"], 0, places=8)
        self.assertAlmostEqual(reference(0, 0.1)["Z"], reference(math.pi, 0.1)["Z"], places=12)
        self.assertAlmostEqual(reference(0, 0.1)["X"], -reference(math.pi, 0.1)["X"], places=12)

    def test_seeded_outcomes_reproduce_and_more_retained_data_resolves(self):
        kwargs = {"sample_counts": [16, 64, 256, 1024], "repetitions": 16, "seed": 17}
        first, second = run(**kwargs), run(**kwargs)
        self.assertEqual(first["points"], second["points"])
        self.assertEqual(first["outcome_transcript_sha256"], second["outcome_transcript_sha256"])
        self.assertEqual(first["cost"]["prepared_samples"], 32768)
        self.assertEqual(first["points"][0]["after_precision_resolved_count"], 0)
        self.assertEqual(first["points"][-1]["after_precision_resolved_count"], 16)
        self.assertLess(first["points"][-1]["after_rmse"], first["points"][0]["after_rmse"])
        capped = run(**kwargs, memory_bits=64)
        self.assertEqual(capped["points"][-1]["retained_target_samples"], 64)
        self.assertEqual(capped["points"][-1]["after_precision_resolved_count"], 0)

    def test_inputs_and_workspace_fail_before_sampling(self):
        for arguments in ({"sample_counts": [True]}, {"sample_counts": [16, 16]}, {"noise_p": -0.1},
                          {"memory_bits": 0}, {"confidence": 1.0}, {"phase": float("nan")},
                          {"sample_counts": [1024], "profile": Profile("tiny", 1)}):
            with self.subTest(arguments=arguments), patch("xi_quantum.observer._pool", side_effect=AssertionError("sampling attempted")):
                with self.assertRaises(QuantumComputeError):
                    run(**arguments)

    def test_observer_program_encrypts_transfers_resumes_and_replays(self):
        raw = program()
        with tempfile.TemporaryDirectory() as folder:
            a, b = Runtime(Path(folder) / "a"), Runtime(Path(folder) / "b")
            first = a.run(raw, grant=grant(raw), stop_after=1)
            ka, kb = Identity.generate(), Identity.generate()
            sender = ThinkSync(a, ka)
            receiver = ThinkSync(b, kb, trusted_senders={ka.node_id: ka.public()})
            incoming = receiver.receive(sender.queue(raw, kb.public(), checkpoint=a.checkpoint(first)))
            resumed = b.run(raw, grant=grant(raw), recovered=receiver.checkpoint(incoming["packet_sha256"]))
            self.assertEqual(resumed["restored_from_peer_this_call"], 1)
            self.assertEqual(resumed["executed_this_call"], 1)
            self.assertTrue(resumed["integrity"]["ok"])
            self.assertEqual(first["steps"][0]["result"], resumed["steps"][0]["result"])
            with patch("xi_quantum.observer.run", side_effect=AssertionError("recomputed imported evidence")):
                replay = Runtime(b.home).run(raw, grant=grant(raw))
            self.assertEqual(replay["executed_this_call"], 0)
            self.assertEqual(replay["integrity"], resumed["integrity"])

    def test_recovered_qr_bytes_and_null_contract_survive_encrypted_transport(self):
        from xi_quantum.glyphsafe import seal, restore, encode_digest, decode_tile
        from xi_quantum.common import digest
        folder = ROOT / "recovered/2026-10-20"
        raw = (folder / "StructuralKernel.QR.v1.xi").read_bytes()
        self.assertEqual(len(raw), 135)
        self.assertEqual(digest(raw), "b0769554d36cd87a110ed7892cc622e5ab00f39ad01ea7d6ab71df69a9a00dc7")
        self.assertEqual(decode_tile(encode_digest(digest(raw))), digest(raw))
        self.assertEqual(bytes.fromhex(json.loads((folder / "QR-RECEIPT.json").read_text())["raw_bytes_hex"]), raw)
        contracts = json.loads((folder / "CONTRACTS.json").read_text())["contracts"]
        self.assertIsNone(next(c for c in contracts if c["id"] == "Claude.AgapeEcho.v1")["visible_fields"]["companion_preview.operator"])
        self.assertEqual(next(c for c in contracts if c["id"] == "SymbolicIdentityHash")["visible_fields"]["symbolic_id_hash.function"], "SHA3")
        a, b = Identity.generate(), Identity.generate()
        packet = seal(raw, a, b.public(), sequence=1)
        self.assertEqual(restore(packet, b, {a.node_id: a.public()})["raw"], raw)
        with self.assertRaises(QuantumComputeError):
            compile_program(raw)


if __name__ == "__main__":
    unittest.main()
