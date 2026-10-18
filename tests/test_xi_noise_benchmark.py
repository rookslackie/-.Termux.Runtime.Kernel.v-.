from __future__ import annotations

import copy
import math
from pathlib import Path
import tempfile
import unittest

from xi_field import bootstrap_field
from xi_field.noise_benchmark import enumerate_faults, logical_error_prediction, run, trial_seed, wilson_interval
from xi_field.operators import FieldOperatorError, apply_operator, initial_state
from xi_world.kernel import WorldError


class IndependentPhaseNoiseTests(unittest.TestCase):
    def test_seeded_noise_known_zero_single_double_and_triple_masks(self):
        for p, faults in [(0, []), (0.25, [1]), (0.5, [0, 1]), (1, [0, 1, 2])]:
            with self.subTest(p=p):
                original = initial_state(3)
                for q in range(3):
                    original, _ = apply_operator(original, "hadamard", {"qubit": q})
                unchanged = copy.deepcopy(original)
                noisy, receipt = apply_operator(original, "sample_z_noise", {"p": p, "seed": 12345})
                self.assertEqual(receipt["fault_qubits"], faults)
                self.assertEqual(receipt["fault_count"], len(faults))
                self.assertEqual(original, unchanged)
                expected = original
                for q in faults:
                    expected, _ = apply_operator(expected, "z", {"qubit": q})
                self.assertEqual(noisy["branches"], expected["branches"])
                replay, replay_receipt = apply_operator(original, "sample_z_noise", {"p": p, "seed": 12345})
                self.assertEqual((noisy, receipt), (replay, replay_receipt))

    def test_reference_qubit_is_excluded_and_targets_keep_declared_order(self):
        state = initial_state(4)
        _, receipt = apply_operator(state, "sample_z_noise", {"p": 1, "seed": 3, "qubits": [2, 0]})
        self.assertEqual(receipt["fault_qubits"], [2, 0])
        state, _ = apply_operator(state, "encode_phase_code")
        with self.assertRaises(FieldOperatorError):
            apply_operator(state, "sample_z_noise", {"p": 1, "seed": 3, "qubits": [3]})

    def test_invalid_noise_is_atomic_and_pending_syndrome_cannot_go_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            field = bootstrap_field(Path(temp) / "noise.sqlite3")
            invalid = [
                {"p": p, "seed": 1} for p in (-0.01, 1.01, float("nan"), float("inf"), True, "0.1")
            ] + [
                {"p": 0.1, "seed": seed} for seed in (None, True, 1.5)
            ] + [
                {"p": 0.1, "seed": 1, "qubits": targets} for targets in ([], [0, 0], [3], [True], "012")
            ]
            before = field.kernel.verify(field.world_id)
            for index, params in enumerate(invalid):
                with self.subTest(params=params), self.assertRaises(WorldError):
                    field.execute("sample_z_noise", parameters=params, idempotency_key=f"invalid-{index}")
            self.assertEqual(field.kernel.verify(field.world_id), before)
            field.execute("encode_phase_code", idempotency_key="encode")
            field.execute("phase_syndrome", parameters={"seed": 1}, idempotency_key="measure")
            with self.assertRaisesRegex(WorldError, "before syndrome"):
                field.execute("sample_z_noise", parameters={"p": 1, "seed": 1}, idempotency_key="stale")
            field.execute("correct_z_error", idempotency_key="correct")
            with self.assertRaises(WorldError):
                field.execute("sample_z_noise", parameters={"p": 1, "seed": 1}, idempotency_key="late")
            field.execute("decode_phase_code", idempotency_key="decode")
            field.execute("encode_phase_code", idempotency_key="reencode")
            field.execute("sample_z_noise", parameters={"p": 1, "seed": 1}, idempotency_key="next-round")

    def test_all_eight_masks_measure_syndrome_decode_and_fidelity(self):
        expected = {
            "000": ([1, 1], None, "I"), "001": ([1, -1], 2, "I"),
            "010": ([-1, -1], 1, "I"), "011": ([-1, 1], 0, "X"),
            "100": ([-1, 1], 0, "I"), "101": ([-1, -1], 1, "X"),
            "110": ([1, -1], 2, "X"), "111": ([1, 1], None, "X"),
        }
        patterns = enumerate_faults()
        for row in patterns:
            syndrome, corrected, pauli = expected[row["mask"]]
            self.assertEqual((row["syndrome"], row["corrected_qubit"], row["logical_pauli"]),
                             (syndrome, corrected, pauli))
            self.assertEqual(row["entanglement_fidelity"], 1.0 if pauli == "I" else 0.0)
            self.assertEqual(row["t_state_fidelity"], 1.0 if pauli == "I" else 0.5)
        for p in (0, 0.01, 0.1, 0.25, 0.5, 0.75, 1):
            weighted_failure = sum(
                (1 - row["entanglement_fidelity"]) * p ** len(row["fault_qubits"])
                * (1 - p) ** (3 - len(row["fault_qubits"])) for row in patterns
            )
            self.assertAlmostEqual(weighted_failure, logical_error_prediction(p), places=13)

    def test_seed_derivation_and_small_benchmark_have_fixed_results(self):
        self.assertEqual(trial_seed(20261018, 0.1, 0, "encoded-noise"),
                         78067946495494165521062554153422313066)
        first = run(probabilities=(0.1, 0.5, 0.9), shots=128, ledger_trials=0)
        second = run(probabilities=(0.9, 0.1, 0.5), shots=128, ledger_trials=0)
        fixed = {0.1: (5, 9), 0.5: (66, 62), 0.9: (126, 112)}
        other = {row["p"]: row for row in second["points"]}
        for point in first["points"]:
            self.assertEqual((point["encoded"]["logical_failures"], point["unencoded"]["logical_failures"]),
                             fixed[point["p"]])
            for key in ("encoded", "unencoded", "mask_counts", "fault_weight_counts"):
                self.assertEqual(point[key], other[point["p"]][key])
            self.assertEqual(point["encoded"]["t_state_fidelity"],
                             1 - 0.5 * point["encoded"]["logical_error_rate"])

    def test_independent_mask_histogram_and_error_rates_match_model(self):
        # Fixed seeds make this statistical regression deterministic. A six-sigma
        # tolerance detects dependence/bias without demanding 95% CI coverage of
        # every random result (which is not a valid pass/fail rule).
        result = run(probabilities=(0.1, 0.25, 0.75), shots=4096, seed=404, ledger_trials=0)
        for point in result["points"]:
            p, shots = point["p"], point["shots_per_arm"]
            for mask, count in point["mask_counts"].items():
                expected = p ** mask.count("1") * (1 - p) ** mask.count("0")
                tolerance = 6 * math.sqrt(expected * (1 - expected) / shots) + 1 / shots
                self.assertLessEqual(abs(count / shots - expected), tolerance)
            for arm, expected in (("encoded", logical_error_prediction(p)), ("unencoded", p)):
                tolerance = 6 * math.sqrt(expected * (1 - expected) / shots) + 1 / shots
                self.assertLessEqual(abs(point[arm]["logical_error_rate"] - expected), tolerance)
            self.assertEqual(sum(point["mask_counts"].values()), shots)
            self.assertEqual(sum(point["fault_weight_counts"].values()), shots)
        self.assertEqual(result["points"][0]["observed_regime"], "improves")
        self.assertEqual(result["points"][-1]["observed_regime"], "worsens")

    def test_zero_and_unit_probability_are_exact_and_persistent_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "benchmark.sqlite3"
            first = run(probabilities=(0, 0.5, 1), shots=4, seed=1, database=db, ledger_trials=4)
            second = run(probabilities=(0, 0.5, 1), shots=4, seed=1, database=db, ledger_trials=4)
            self.assertEqual(first["run_id"], second["run_id"])
            self.assertEqual(first["persistence"]["traces"], second["persistence"]["traces"])
            self.assertEqual(len(first["persistence"]["traces"]), 24)
            for point in (first["points"][0], first["points"][-1]):
                for arm in ("encoded", "unencoded"):
                    self.assertEqual(point[arm]["logical_error_rate"], point["p"])
            for point in first["points"]:
                for arm in ("encoded", "unencoded"):
                    committed_failures = sum(
                        trace["entanglement_fidelity"] < 0.5 for trace in first["persistence"]["traces"]
                        if trace["p"] == point["p"] and trace["arm"] == arm
                    )
                    self.assertEqual(committed_failures, point[arm]["logical_failures"])
            for trace in first["persistence"]["traces"]:
                field = bootstrap_field(db, world_id=trace["world_id"])
                events = field.kernel.events(trace["world_id"])
                self.assertEqual(len(events), 10 if trace["arm"] == "encoded" else 6)
                self.assertTrue(trace["integrity"]["ok"])
                self.assertEqual(trace["integrity"]["head_hash"], field.kernel.verify(field.world_id)["head_hash"])
                for before, after in zip(events, events[1:]):
                    self.assertEqual(after.causes, (before.event_id,))
            # Replay after a partial (committed noise, no recovery) run as well.
            interrupted = first["persistence"]["traces"][0]
            noise = interrupted["noise_receipt"]
            field = bootstrap_field(Path(temp) / "partial.sqlite3", world_id=interrupted["world_id"], qubits=4)
            for index, (op, params) in enumerate([
                ("reference", {}), ("hadamard", {"qubit": 0}),
                ("cnot", {"control": 0, "target": 3}), ("encode_phase_code", {}),
                ("sample_z_noise", {"p": noise["p"], "seed": noise["seed"], "qubits": noise["qubits"]}),
            ]):
                field.execute(op, parameters=params, idempotency_key=f"prepare-{index}")
            resumed = run(probabilities=(0, 0.5, 1), shots=4, seed=1,
                          database=Path(temp) / "partial.sqlite3", ledger_trials=4)
            self.assertEqual(resumed["persistence"]["traces"][0]["event_count"], 10)

    def test_wilson_intervals_and_configuration_validation(self):
        self.assertEqual(wilson_interval(0, 100)[0], 0)
        self.assertAlmostEqual(wilson_interval(0, 100)[1], 0.03699349820698568)
        self.assertEqual(wilson_interval(100, 100)[1], 1)
        self.assertAlmostEqual(wilson_interval(50, 100)[0], 0.4038315303659956)
        for kwargs in ({"shots": 0}, {"shots": True}, {"seed": True}, {"probabilities": []},
                       {"probabilities": [float("nan")]}, {"probabilities": [-0.1]},
                       {"probabilities": [0.1, 0.1]}, {"shots": 2, "ledger_trials": 3}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run(**kwargs)


if __name__ == "__main__":
    unittest.main()
