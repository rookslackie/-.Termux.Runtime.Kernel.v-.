from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from xi_field import FieldOperatorError, bootstrap_field
from xi_field.runtime import FIELD_ACTOR_ID
from xi_field.demo import run as run_demo
from xi_field.phase_code_demo import run as run_phase_code_demo
from xi_field.operators import apply_operator, initial_state
from xi_field.topology import chip_topology
from xi_world.kernel import WorldError


class GlyphFieldRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "field.sqlite3"
        self.field = bootstrap_field(self.db, qubits=3)

    def tearDown(self):
        self.temp.cleanup()

    def op(self, name, key, **parameters):
        return self.field.execute(name, idempotency_key=key, parameters=parameters)

    def test_chip_topology_is_loaded_and_provenanced(self):
        topology, fingerprint = chip_topology()
        self.assertEqual(topology["architecture"]["name"], "Woven Glyph-Chip")
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(self.field.state()["topology_sha256"], fingerprint)

    def test_sparse_glyph_cycle_witness_and_restart_are_persistent(self):
        reference = self.op("reference", "reference")
        h = self.op("hadamard", "h-0", qubit=0)
        e1 = self.op("cnot", "cnot-01", control=0, target=1)
        e2 = self.op("cnot", "cnot-02", control=0, target=2)
        phase = self.op("phase", "phase-pi", angle=3.141592653589793)
        witness = self.op("witness", "witness-x", basis="x", seed=417)
        close = self.op("close", "close-0")

        self.assertEqual({b[0] for b in e2.echo["glyph-chip"]["branches"]}, {"000", "111"})
        self.assertAlmostEqual(phase.echo["glyph-chip"]["branches"][1][1][0], -2**-0.5)
        outcome = witness.echo["glyph-chip"]["last_operator_receipt"]["outcome"]
        self.assertEqual(outcome.count("1") % 2, 1)
        self.assertTrue(close.echo["glyph-chip"]["closed"])
        self.assertEqual(close.causes, (witness.event_id,))

        resumed = bootstrap_field(self.db, qubits=3)
        self.assertTrue(resumed.state()["closed"])
        resume = resumed.execute("resume", idempotency_key="resume-1")
        self.assertFalse(resume.echo["glyph-chip"]["closed"])
        next_h = resumed.execute("hadamard", parameters={"qubit": 1}, idempotency_key="next-cycle-h")
        self.assertEqual(next_h.causes, (resume.event_id,))
        self.assertEqual(len(resumed.kernel.events(resumed.world_id)), 10)
        self.assertTrue(resumed.kernel.verify(resumed.world_id)["ok"])
        self.assertEqual(reference.sequence, 2)
        self.assertEqual(h.sequence, 3)
        self.assertEqual(e1.sequence, 4)

    def test_idempotency_replay_returns_same_capsule_and_rejects_conflict(self):
        first = self.op("hadamard", "same-key", qubit=0)
        replay = self.op("hadamard", "same-key", qubit=0)
        self.assertEqual(first.event_id, replay.event_id)
        with self.assertRaises(WorldError):
            self.op("hadamard", "same-key", qubit=1)

    def test_invalid_operations_do_not_mutate_the_ledger(self):
        before = len(self.field.kernel.events(self.field.world_id))
        with self.assertRaises(WorldError):
            self.op("cnot", "bad-cnot", control=1, target=1)
        with self.assertRaises(WorldError):
            self.field.execute("witness", idempotency_key="bad-witness", parameters={"basis": "z"})
        self.assertEqual(len(self.field.kernel.events(self.field.world_id)), before)

    def test_close_requires_explicit_resume(self):
        self.op("close", "close")
        before = len(self.field.kernel.events(self.field.world_id))
        with self.assertRaises(WorldError):
            self.op("hadamard", "blocked", qubit=0)
        self.assertEqual(len(self.field.kernel.events(self.field.world_id)), before)

    def test_h_plus_t_prepares_an_ideal_magic_state_without_claiming_qec(self):
        db = Path(self.temp.name) / "magic.sqlite3"
        field = bootstrap_field(db, world_id="magic-state", qubits=1)
        field.execute("hadamard", idempotency_key="h", parameters={"qubit": 0})
        event = field.execute("t", idempotency_key="t", parameters={"qubit": 0})
        state = event.echo["glyph-chip"]
        self.assertEqual([branch[0] for branch in state["branches"]], ["0", "1"])
        amp0 = complex(*state["branches"][0][1])
        amp1 = complex(*state["branches"][1][1])
        self.assertAlmostEqual(abs(amp0), 2**-0.5)
        self.assertAlmostEqual(abs(amp1), 2**-0.5)
        self.assertAlmostEqual((amp1 / amp0).real, 2**-0.5)
        self.assertAlmostEqual((amp1 / amp0).imag, 2**-0.5)
        self.assertIn("non-Clifford", state["last_operator_receipt"]["meaning"])

    def test_phase_flip_code_corrects_each_single_z_fault(self):
        expected_syndromes = {
            0: [-1, 1],
            1: [-1, -1],
            2: [1, -1],
        }
        for faulty_qubit in range(3):
            with self.subTest(faulty_qubit=faulty_qubit):
                state = initial_state(3)
                for operator, parameters in [
                    ("hadamard", {"qubit": 0}),
                    ("t", {"qubit": 0}),
                    ("encode_phase_code", {}),
                    ("inject_z_error", {"qubit": faulty_qubit}),
                    ("phase_syndrome", {"seed": 20261017}),
                ]:
                    state, receipt = apply_operator(state, operator, parameters)
                self.assertEqual(receipt["syndrome"], expected_syndromes[faulty_qubit])
                state, correction = apply_operator(state, "correct_z_error")
                self.assertEqual(correction["corrected_qubit"], faulty_qubit)
                state, _ = apply_operator(state, "decode_phase_code")

                ideal = initial_state(3)
                ideal, _ = apply_operator(ideal, "hadamard", {"qubit": 0})
                ideal, _ = apply_operator(ideal, "t", {"qubit": 0})
                self.assertEqual(state["branches"], ideal["branches"])
                self.assertTrue(state["phase_code_decoded"])

    def test_phase_code_persists_recovery_across_restart_and_replay(self):
        db = Path(self.temp.name) / "phase-code.sqlite3"
        first = run_phase_code_demo(db, world_id="persistent-phase-code")
        second = run_phase_code_demo(db, world_id="persistent-phase-code")
        self.assertEqual(first["event_count"], 10)
        self.assertEqual(first["syndrome"], [-1, -1])
        self.assertEqual(first["corrected_qubit"], 1)
        self.assertEqual(first["recovered_state_fidelity"], 1.0)
        self.assertTrue(first["state_after_restart"])
        self.assertTrue(first["integrity"]["ok"])
        self.assertEqual(second["event_count"], first["event_count"])
        self.assertEqual(second["integrity"]["head_hash"], first["integrity"]["head_hash"])

    def test_phase_code_composes_multiple_injections_by_parity(self):
        state = initial_state(3)
        for operator, parameters in [
            ("hadamard", {"qubit": 0}),
            ("t", {"qubit": 0}),
            ("encode_phase_code", {}),
            ("inject_z_error", {"qubit": 0}),
        ]:
            state, _ = apply_operator(state, operator, parameters)
        state, _ = apply_operator(state, "inject_z_error", {"qubit": 2})
        self.assertEqual(state["injected_z_faults"], [0, 2])
        # Applying the same Z twice cancels; the remaining single fault still corrects.
        state, _ = apply_operator(state, "inject_z_error", {"qubit": 0})
        state, syndrome = apply_operator(state, "phase_syndrome", {"seed": 123})
        self.assertEqual(syndrome["syndrome"], [1, -1])
        with self.assertRaisesRegex(FieldOperatorError, "before syndrome"):
            apply_operator(state, "inject_z_error", {"qubit": 1})
        state, correction = apply_operator(state, "correct_z_error")
        self.assertEqual(correction["corrected_qubit"], 2)
        state, _ = apply_operator(state, "decode_phase_code")
        ideal = initial_state(3)
        ideal, _ = apply_operator(ideal, "hadamard", {"qubit": 0})
        ideal, _ = apply_operator(ideal, "t", {"qubit": 0})
        self.assertEqual(state["branches"], ideal["branches"])

    def test_demo_replays_completed_cycle_without_duplicate_capsules(self):
        db = Path(self.temp.name) / "demo.sqlite3"
        first = run_demo(db, world_id="demo-world")
        second = run_demo(db, world_id="demo-world")
        self.assertEqual(first["event_count"], 8)
        self.assertEqual(second["event_count"], 8)
        self.assertEqual(first["integrity"]["head_hash"], second["integrity"]["head_hash"])


if __name__ == "__main__":
    unittest.main()
