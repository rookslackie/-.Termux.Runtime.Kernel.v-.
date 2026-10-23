from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from benchmarks.verify_coherent_phase_code import STATES, reference, trace_distance, unpack
from xi_quantum.circuits import phase_code
from xi_quantum.coherent import phase_code_channel
from xi_quantum.common import Profile, QuantumComputeError, digest
from xi_quantum.tessera import compile_program
from xi_quantum.runtime import Runtime, ExecutionGrant
from xi_quantum.service import make_server
from xi_quantum.workbench import Workbench
from xi_quantum.client import LivingCircuitClient
from xi_quantum.__main__ import fullcycle_demo


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/QuantumCompute.CoherentNoise.v3.xi"


class CoherentPhysicsTests(unittest.TestCase):
    def test_dense_oracle_all_states_repeated_rounds_and_noise_models(self):
        for state, vector in STATES.items():
            for angles in ([0, 0, 0], [.2]*3, [-.3, .7, .1], [math.pi]*3):
                for cycles in (1, 2, 8):
                    for twirled in (False, True):
                        with self.subTest(state=state, angles=angles, cycles=cycles, twirled=twirled):
                            result = phase_code_channel(state=state, angles=angles, cycles=cycles, twirled=twirled)
                            expected, history, _ = reference(vector=vector, angles=angles, cycles=cycles, twirled=twirled)
                            self.assertLess(trace_distance(unpack(result["logical_density_matrix"]), expected), 1e-10)
                            for actual, baseline in zip(result["history"], history):
                                for syndrome, branch in baseline["branches"].items():
                                    self.assertAlmostEqual(actual["syndrome_probabilities"][syndrome],
                                                           np.trace(branch).real, places=12)

    def test_any_one_local_rotation_is_corrected_for_arbitrary_complex_input(self):
        vector = np.array([.6, .8j])
        for q in range(3):
            angles = [0, 0, 0]
            angles[q] = 1.73
            result = phase_code_channel(state=[[.6, 0], [0, .8]], angles=angles, cycles=8)
            np.testing.assert_allclose(unpack(result["logical_density_matrix"]),
                                       np.outer(vector, vector.conj()), atol=1e-12, rtol=0)

    def test_twirled_logical_error_matches_binomial_formula(self):
        for angle in (.01, .2, .8, math.pi):
            p = math.sin(angle/2)**2
            result = phase_code_channel(state="zero", angles=[angle]*3, twirled=True)
            self.assertAlmostEqual(unpack(result["logical_density_matrix"])[1, 1].real,
                                   3*p*p-2*p*p*p, places=12)

    def test_coherent_logical_off_diagonal_survives_syndrome_measurement(self):
        angle = .2
        coherent = phase_code_channel(state="zero", angles=[angle]*3)
        twirled = phase_code_channel(state="zero", angles=[angle]*3, twirled=True)
        # For |0>, coherent logical cross terms have magnitude 2 cos^3(a/2) sin^3(a/2).
        expected = 2*(math.cos(angle/2)*math.sin(angle/2))**3
        self.assertAlmostEqual(trace_distance(unpack(coherent["logical_density_matrix"]),
                                             unpack(twirled["logical_density_matrix"])), expected, places=12)

    def test_instrument_is_completely_positive_trace_preserving(self):
        result = phase_code_channel(angles=[.3, -.8, .1])
        operators = [unpack(k["matrix"]) for k in result["kraus_operators"]]
        np.testing.assert_allclose(sum(k.conj().T @ k for k in operators), np.eye(2), atol=1e-12, rtol=0)
        # Apply to half a Bell pair; this probes preservation of external entanglement.
        bell = np.array([1, 0, 0, 1], complex)/np.sqrt(2)
        rho = np.outer(bell, bell.conj())
        joint = sum(np.kron(k, np.eye(2)) @ rho @ np.kron(k, np.eye(2)).conj().T for k in operators)
        self.assertGreaterEqual(np.linalg.eigvalsh(joint).min(), -1e-12)
        self.assertAlmostEqual(np.trace(joint).real, 1, places=12)

    def test_original_sparse_sampler_matches_each_dense_conditional_branch(self):
        angles = [1.2, 1.1, .9]
        _, history, _ = reference(vector=STATES["T"], angles=angles)
        found = set()
        for seed in range(64):
            result = phase_code(state="T", faults=[], angles=angles, seed=seed)
            key = str(result["syndrome"])
            found.add(key)
            branch = history[0]["branches"][key]
            output = np.zeros(8, complex)
            for bits, pair in result["output"]["branches"]:
                output[int(bits, 2)] = complex(*pair)
            reduced = np.einsum('ar,br->ab', output.reshape(2, 4), output.reshape(2, 4).conj())
            self.assertLess(trace_distance(reduced, branch/np.trace(branch)), 1e-10)
            self.assertFalse(result["within_single_fault_scope"])
        self.assertEqual(found, set(history[0]["branches"]))

    def test_negative_control_detects_reversed_rotation_sign(self):
        from xi_quantum.circuits import rz
        expected, _, _ = reference(vector=STATES["zero"], angles=[.7]*3)
        with patch("xi_quantum.coherent.rz", side_effect=lambda a: rz(-a)):
            broken = phase_code_channel(state="zero", angles=[.7]*3)
        self.assertGreater(trace_distance(unpack(broken["logical_density_matrix"]), expected), .01)

    def test_negative_control_rejects_wrong_syndrome_correction(self):
        with patch.dict("xi_quantum.coherent.CORRECTION", {(1, -1): 0}):
            with self.assertRaisesRegex(QuantumComputeError, "ancillas"):
                phase_code_channel(angles=[.2]*3)

    def test_deterministic_commitment_excludes_timing_and_resources(self):
        first = phase_code_channel()
        second = phase_code_channel()
        self.assertEqual(first["numerical_sha256"], second["numerical_sha256"])
        core = {k: v for k, v in first.items() if k not in ("numerical_sha256", "resources", "wall_seconds")}
        self.assertEqual(digest(core), first["numerical_sha256"])
        self.assertNotEqual(first["numerical_sha256"], phase_code_channel(twirled=True)["numerical_sha256"])
        json.dumps(first, allow_nan=False)

    def test_invalid_inputs_and_cycle_budget_are_rejected(self):
        for kwargs in ({"angles": [0, 0]}, {"angles": [0, 0, True]}, {"angles": [0, float("nan"), 0]},
                       {"angles": [float("inf"), 0, 0]}, {"cycles": True}, {"cycles": 0},
                       {"cycles": 1025}, {"twirled": 1}, {"state": [[1, 0], [1, 0]]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(QuantumComputeError):
                phase_code_channel(**kwargs)
        with patch("xi_quantum.coherent._kraus", side_effect=AssertionError("allocated")):
            with self.assertRaisesRegex(QuantumComputeError, "budget"):
                phase_code_channel(cycles=1024, profile=Profile("tiny", 1))
            with self.assertRaisesRegex(QuantumComputeError, "cycles"):
                phase_code_channel(cycles=3, profile=Profile("bounded", 64, 2))


class CoherentIntegrationTests(unittest.TestCase):
    def test_example_and_packaged_copy_compile_in_declared_dialect(self):
        raw = EXAMPLE.read_bytes()
        self.assertEqual(raw, (ROOT/"xi_quantum/programs"/EXAMPLE.name).read_bytes())
        plan = compile_program(raw)
        self.assertEqual(plan.steps[0]["operator"], "PhaseCodeChannel")
        self.assertEqual(plan.steps[0]["glyph"], "⟐⧂ρ")
        program = yaml.safe_load(raw)
        program["schema"], program["dialect"] = "xi.quantumcompute.program.v2", "QuantumCompute.Stack.v2"
        with self.assertRaisesRegex(QuantumComputeError, "binding"):
            compile_program(yaml.safe_dump(program, allow_unicode=True).encode())

    def test_runtime_preserves_exact_source_result_and_replay(self):
        raw = EXAMPLE.read_bytes()
        plan = compile_program(raw)
        grant = ExecutionGrant(plan.program_sha256, frozenset(s["operator"] for s in plan.steps))
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Runtime(temporary)
            first = runtime.run(raw, grant=grant)
            second = Runtime(temporary).run(raw, grant=grant)
            self.assertTrue(first["integrity"]["ok"])
            self.assertEqual(runtime.source(plan.program_sha256), raw)
            self.assertEqual(second["executed_this_call"], 0)
            self.assertEqual(first["steps"][0]["result"]["numerical_sha256"],
                             second["steps"][0]["result"]["numerical_sha256"])

    def test_unused_registry_extension_cannot_dilute_existing_routing_cohort(self):
        from xi_quantum.tessera import ROUTING_BASE_OPERATORS
        from xi_quantum import tessera
        raw = (ROOT/"examples/QuantumCompute.Spectral.v3.xi").read_bytes()
        with patch.dict(tessera.GLYPHS, {"UnusedFutureOperator": "◈future"}):
            plan = compile_program(raw)
            grant = ExecutionGrant(plan.program_sha256, frozenset(s["operator"] for s in plan.steps))
            with tempfile.TemporaryDirectory() as temporary:
                result = Runtime(temporary).run(raw, grant=grant)
        for item in result["steps"]:
            self.assertEqual(item["route"]["coherence_before"]["node_count"], len(ROUTING_BASE_OPERATORS))

    def test_encrypted_fullcycle_transfers_the_new_channel_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = fullcycle_demo(EXAMPLE.read_bytes(), Profile(), temporary)
            self.assertTrue(result["exact_source_roundtrip"])
            self.assertTrue(result["duplicate_packet_is_idempotent"])
            self.assertTrue(result["receiver"]["integrity"]["ok"])
            self.assertEqual(result["receiver"]["steps"][0]["operator"], "PhaseCodeChannel")

    def test_real_http_exposes_example_and_executes_durable_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            bench = Workbench(temporary)
            token = "coherent-test-only-owner-token-long-enough"
            server = make_server(bench, port=0, token=token)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = LivingCircuitClient(f"http://127.0.0.1:{server.server_port}/api/quantumcompute/v3", token=token)
                source = client.request("/examples/coherent-noise")["source"]
                self.assertEqual(source, EXAMPLE.read_text())
                self.assertEqual(client.capabilities()["version"], "3.1.0")
                self.assertEqual(client.request("/openapi.json")["info"]["version"], "3.1.0")
                self.assertIn("PhaseCodeChannel", [op["operator"] for op in client.capabilities()["operators"]])
                job = client.submit(source, "coherent-roundtrip")
                # Block on the existing condition-free polling client convention.
                import time
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    job = client.job(job["id"])
                    if job["state"] in ("completed", "failed"):
                        break
                    time.sleep(.01)
                self.assertEqual(job["state"], "completed")
                self.assertEqual(job["result"]["steps"][0]["result"]["cycles"], 8)
            finally:
                server.shutdown()
                server.server_close()
                bench.close()
