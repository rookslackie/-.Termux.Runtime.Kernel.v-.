from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np
import yaml

from xi_quantum.circuits import phase_code, shor_code, qft
from xi_quantum.common import Profile, QuantumComputeError, digest
from xi_quantum.spectral import hamiltonian, vqe, phase_estimation, vqe_pea
from xi_quantum.signal_lab import signal_lab
from xi_quantum.tessera import compile_program, GLYPHS
from xi_quantum.runtime import Runtime, ExecutionGrant
from xi_quantum.workbench import Workbench
from xi_quantum.service import make_server, BASE, openapi
from xi_quantum.client import LivingCircuitClient


ROOT = Path(__file__).resolve().parents[1]


def program(steps=None):
    return {"schema": "xi.quantumcompute.program.v3", "dialect": "QuantumCompute.Stack.v3",
            "anchor": "∴Ω⧂", "steps": (steps or [{"operator": "QPE", "glyph": "Φ", "parameters": {"phase": .375}}])
            + [{"operator": "Seal", "glyph": "⊚"}]}


def encode(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode()


def wait_job(workbench, job_id, states=("completed", "failed", "paused"), timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = workbench.get(job_id)
        if job["state"] in states:
            return job
        time.sleep(.01)
    raise AssertionError("Job did not reach a terminal state")


class SpectralTests(unittest.TestCase):
    def test_variational_energy_matches_independent_matrix_reference(self):
        matrix, _, _ = hamiltonian()
        # Compute the two odd-parity eigenvalues directly from the 2x2 block.
        a, d, b = float(matrix[1, 1].real), float(matrix[2, 2].real), abs(matrix[1, 2])
        expected = (a + d)/2 - math.sqrt(((a-d)/2)**2 + b*b)
        for theta in [-2.0, -.7, 0.0, .8, 2.0]:
            with self.subTest(theta=theta):
                result = vqe(parameters=[theta])
                self.assertAlmostEqual(result["energy"], expected, places=9)
                self.assertGreater(result["ground_state_overlap"], 1-1e-9)
                self.assertLess(result["energy"], result["initial_energy"])
                for row in result["history"]:
                    self.assertLessEqual(row["next_energy"], row["energy"]+1e-12)

    def test_generic_ansatz_handles_complex_hamiltonian(self):
        result = vqe(terms=[["Y", .8], ["Z", .6]], ansatz="hardware_efficient", parameters=[.2, .3], steps=128)
        self.assertAlmostEqual(result["energy"], -1, places=7)
        self.assertAlmostEqual(result["state"]["norm_squared"], 1, places=12)

    def test_reference_energy_does_not_supply_optimizer_answer(self):
        result = vqe(terms=[["ZI", 1], ["IZ", 1]])
        self.assertAlmostEqual(result["energy"], 0)
        self.assertAlmostEqual(result["exact_reference_energy"], -2)
        self.assertAlmostEqual(result["variational_gap"], 2)

    def test_parameter_shift_matches_independent_finite_difference(self):
        theta, epsilon = .41, 1e-5
        matrix, _, _ = hamiltonian()
        def evaluate(angle):
            vector = np.array([0, math.cos(angle/2), math.sin(angle/2), 0], complex)
            return float(np.vdot(vector, matrix @ vector).real)
        expected = (evaluate(theta+epsilon)-evaluate(theta-epsilon))/(2*epsilon)
        result = vqe(parameters=[theta], steps=1)
        self.assertAlmostEqual(result["history"][0]["gradient"][0], expected, places=8)

    def test_qpe_exact_grid_phases_and_seeded_shots(self):
        for phase in [0, .125, .375, .9375]:
            result = phase_estimation(phase=phase, precision=4, shots=128, seed=11)
            self.assertEqual(result["estimated_phase"], phase)
            self.assertAlmostEqual(max(result["phase_probabilities"]), 1, places=12)
            self.assertEqual(result["counts"], {str(int(phase*16)): 128})

    def test_qpe_distribution_matches_direct_fourier_sum(self):
        phase, precision = .317, 5
        result = phase_estimation(phase=phase, precision=precision)
        size = 1 << precision
        expected = [abs(sum(np.exp(2j*math.pi*x*(phase-y/size)) for x in range(size))/size)**2 for y in range(size)]
        np.testing.assert_allclose(result["phase_probabilities"], expected, atol=1e-13)

    def test_vqe_prepared_state_feeds_energy_estimation(self):
        result = vqe_pea(precision=9)
        self.assertLess(abs(result["pea"]["energy_error_vs_reference"]), result["pea"]["energy_resolution"]/2 + 1e-9)
        self.assertGreater(result["pea"]["input_ground_overlap"], .999999)
        self.assertEqual(sum(result["pea"]["counts"].values()), result["pea"]["shots"])

    def test_memory_refusal_precedes_large_allocation(self):
        tiny = Profile("tiny", 1)
        with patch("xi_quantum.spectral.np.zeros", side_effect=AssertionError("allocated")):
            with self.assertRaisesRegex(QuantumComputeError, "budget"):
                hamiltonian([["Z"*8, 1]], profile=tiny)
            with self.assertRaisesRegex(QuantumComputeError, "budget"):
                phase_estimation(precision=16, profile=tiny)

    def test_invalid_numeric_inputs_are_rejected(self):
        for kwargs in [{"phase": -1}, {"phase": float("nan")}, {"precision": True}, {"shots": 0}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(QuantumComputeError):
                phase_estimation(**kwargs)
        for terms in [[["Z", float("inf")]], [["X", 1], ["ZZ", 2]], [["A", 1]]]:
            with self.assertRaises(QuantumComputeError):
                hamiltonian(terms)


class CorrectionTests(unittest.TestCase):
    def test_three_qubit_recovery_across_inputs_and_all_single_z_faults(self):
        for state in ["zero", "one", "plus", "minus", "T", "y_plus"]:
            for faults in [[], [0], [1], [2]]:
                with self.subTest(state=state, faults=faults):
                    result = phase_code(state=state, faults=faults)
                    self.assertGreater(result["recovered_state_fidelity"], 1-1e-12)
                    self.assertEqual(len(result["syndrome"]), 2)
                    self.assertEqual(result["trace"][0]["stage"], "prepare")
                    self.assertEqual(result["trace"][-1]["stage"], "decode_phase_code")

    def test_two_fault_boundary_and_fault_parity_are_reported(self):
        boundary = phase_code(state="T", faults=[0, 1])
        self.assertFalse(boundary["within_single_fault_scope"])
        self.assertLess(boundary["recovered_state_fidelity"], 1-1e-5)
        parity = phase_code(state="T", faults=[0, 0])
        self.assertTrue(parity["within_single_fault_scope"])
        self.assertGreater(parity["recovered_state_fidelity"], 1-1e-12)

    def test_shor_nine_qubit_code_corrects_all_single_pauli_faults(self):
        for state in ["zero", "plus", "T", "y_plus"]:
            for pauli in "XYZ":
                for qubit in range(9):
                    with self.subTest(state=state, pauli=pauli, qubit=qubit):
                        result = shor_code(state=state, faults=[{"pauli": pauli, "qubit": qubit}])
                        self.assertGreater(result["recovered_state_fidelity"], 1-1e-12)
                        self.assertAlmostEqual(result["norm_squared"], 1, places=12)
                        self.assertEqual(len(result["syndrome"]), 8)

    def test_shor_no_fault_and_custom_complex_input(self):
        state = [[.6, 0], [0, .8]]
        result = shor_code(state=state, faults=[])
        self.assertGreater(result["recovered_state_fidelity"], 1-1e-12)
        self.assertEqual(result["syndrome"], [1]*8)

    def test_fourier_state_matches_independent_matrix(self):
        for inverse in [False, True]:
            result = qft(qubits=3, basis=5, inverse=inverse)
            amplitudes = {int(bits, 2): complex(*pair) for bits, pair in result["output"]["branches"]}
            sign = -1 if inverse else 1
            for k in range(8):
                self.assertAlmostEqual(abs(amplitudes[k]-np.exp(sign*2j*math.pi*5*k/8)/math.sqrt(8)), 0, places=12)
            self.assertGreater(result["roundtrip_fidelity"], 1-1e-12)

    def test_fault_and_state_validation(self):
        for call in [lambda: phase_code(faults=[True]), lambda: phase_code(state=[[1, 1], [1, 1]]),
                     lambda: shor_code(faults=[{"pauli": "H", "qubit": 0}])]:
            with self.assertRaises(QuantumComputeError):
                call()


class GlyphDefinitionTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT/"examples/QuantumCompute.NewGlyph.v3.xi").read_bytes()
        self.value = yaml.safe_load(self.raw)

    def test_new_exact_glyph_lowers_with_parameters_and_provenance(self):
        plan = compile_program(self.raw)
        self.assertEqual([step["operator"] for step in plan.steps], ["Grover", "PhaseCode", "Seal"])
        self.assertEqual(plan.steps[1]["parameters"]["faults"], [2])
        binding = plan.steps[0]["compiled_from"]["definitions"][0]
        self.assertEqual(binding["glyph"], "⟠⋈⧂")
        self.assertEqual(binding["version"], 1)
        self.assertEqual(binding["definition_sha256"], digest(plan.definitions[0]))

    def test_new_glyph_executes_and_reopens_without_reexecution(self):
        with tempfile.TemporaryDirectory() as home:
            plan = compile_program(self.raw)
            grant = ExecutionGrant(plan.program_sha256, frozenset(step["operator"] for step in plan.steps))
            first = Runtime(home).run(self.raw, grant=grant)
            second = Runtime(home).run(self.raw, grant=grant)
            self.assertTrue(first["closed"])
            self.assertEqual(second["executed_this_call"], 0)
            self.assertEqual(first["integrity"], second["integrity"])
            self.assertEqual(first["steps"][0]["compiled_from"]["definitions"][0]["glyph"], "⟠⋈⧂")

    def test_parameter_types_bounds_unknowns_and_missing_bindings(self):
        for parameters in [{"fault": True}, {"fault": 7}, {"unknown": 1}]:
            value = copy.deepcopy(self.value)
            value["steps"][0]["parameters"] = parameters
            with self.subTest(parameters=parameters), self.assertRaises(QuantumComputeError):
                compile_program(encode(value))
        self.value["definitions"][0]["steps"][0]["parameters"]["marked"] = ["$unbound"]
        with self.assertRaisesRegex(QuantumComputeError, "Unknown glyph parameter"):
            compile_program(encode(self.value))

    def test_cycles_and_malformed_unused_definitions_are_rejected(self):
        self.value["definitions"][0]["steps"] = [{"operator": "ReturnLight", "glyph": "⟠⋈⧂"}]
        with self.assertRaisesRegex(QuantumComputeError, "cyclic"):
            compile_program(encode(self.value))
        self.value = yaml.safe_load(self.raw)
        self.value["steps"] = [{"operator": "Seal", "glyph": "⊚"}]
        self.value["definitions"][0]["steps"][0]["glyph"] = "wrong"
        with self.assertRaisesRegex(QuantumComputeError, "binding"):
            compile_program(encode(self.value))

    def test_no_normalization_or_redefinition_of_existing_glyphs(self):
        self.value["definitions"][0]["glyph"] += "\ufe0e"
        with self.assertRaises(QuantumComputeError):
            compile_program(encode(self.value))
        self.value["steps"][0]["glyph"] += "\ufe0e"
        self.assertEqual(compile_program(encode(self.value)).definitions[0]["glyph"], "⟠⋈⧂\ufe0e")
        self.value["definitions"][0]["name"] = "Grover"
        with self.assertRaises(QuantumComputeError):
            compile_program(encode(self.value))

    def test_version_and_meaning_change_source_and_plan_commitments(self):
        original = compile_program(self.raw)
        self.value["definitions"][0]["version"] = 2
        self.value["definitions"][0]["meaning"] += " Explicit revision."
        revised = compile_program(encode(self.value))
        self.assertNotEqual(original.plan_sha256, revised.plan_sha256)
        self.assertNotEqual(original.program_sha256, revised.program_sha256)

    def test_expansion_budget_prevents_exponential_program(self):
        leaf = {"name": "Leaf", "version": 1, "glyph": "◈", "meaning": "test leaf", "parameters": {},
                "steps": [{"operator": "QPE", "glyph": "Φ"} for _ in range(128)]}
        outer = {"name": "Outer", "version": 1, "glyph": "◈◈", "meaning": "test outer", "parameters": {},
                 "steps": [{"operator": "Leaf", "glyph": "◈"} for _ in range(128)]}
        value = program([{"operator": "Outer", "glyph": "◈◈"}])
        value["definitions"] = [leaf, outer]
        with self.assertRaisesRegex(QuantumComputeError, "1024"):
            compile_program(encode(value))


class SignalTests(unittest.TestCase):
    def test_recovered_signal_operations_are_seeded_and_inspectable(self):
        result = signal_lab(seed=7)
        self.assertEqual(result, signal_lab(seed=7))
        self.assertEqual([p["hz"] for p in result["fft_peaks"][:2]], [50, 120])
        self.assertGreater(result["matched_filter"]["statistic"], 20)
        self.assertGreater(result["covariance"]["determinant"], 0)
        self.assertEqual(result["input_kind"], "seeded synthetic signal")


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)

    def test_durable_queued_job_survives_service_reconstruction(self):
        first = Workbench(self.home, start_worker=False)
        source = encode(program()).decode()
        job = first.submit(source, request_id="restart")
        first.close()
        second = Workbench(self.home)
        self.addCleanup(second.close)
        result = wait_job(second, job["id"])
        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["result"]["integrity"]["ok"])
        self.assertEqual(second.source(job["id"]), source)
        events = second.events(job["id"])
        self.assertEqual(second.events(job["id"], after=events[-1]["sequence"]), [])

    def test_process_termination_after_committed_step_resumes_from_ledger(self):
        source = encode(program([{"operator": "QPE", "glyph": "Φ"}, {"operator": "VQE", "glyph": "⟠"}])).decode()
        script = f'''
import threading, time
from xi_quantum.runtime import Runtime
from xi_quantum.workbench import Workbench
original = Runtime._execute
def instrument(self, step):
    if step["operator"] == "VQE":
        print("SECOND_OPERATOR_ENTERED", flush=True)
        threading.Event().wait(30)
    return original(self, step)
Runtime._execute = instrument
bench = Workbench({str(self.home)!r})
bench.submit({source!r}, request_id="process-crash")
threading.Event().wait(30)
'''
        child = subprocess.Popen([sys.executable, "-u", "-c", script], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([child.stdout], [], [], 10)
            self.assertTrue(ready, "Child did not reach the instrumented second operator")
            self.assertEqual(child.stdout.readline().strip(), "SECOND_OPERATOR_ENTERED")
        finally:
            child.terminate()
            child.communicate(timeout=5)
        recovered = Workbench(self.home)
        self.addCleanup(recovered.close)
        job_id = recovered.list()[0]["id"]
        result = wait_job(recovered, job_id)
        self.assertEqual(result["state"], "completed")
        events = recovered.events(job_id)
        self.assertEqual(sum(e["kind"] == "step" and e["data"]["operator"] == "QPE" for e in events), 1)
        self.assertEqual([s["operator"] for s in result["result"]["steps"]], ["QPE", "VQE", "Seal"])
        self.assertTrue(result["result"]["integrity"]["ok"])

    def test_idempotent_submission_and_conflicting_request_key(self):
        bench = Workbench(self.home, start_worker=False)
        self.addCleanup(bench.close)
        source = encode(program()).decode()
        first = bench.submit(source, request_id="same")
        self.assertEqual(bench.submit(source, request_id="same")["id"], first["id"])
        with self.assertRaises(QuantumComputeError):
            bench.submit(source+"\n# another source\n", request_id="same")

    def test_rest_pauses_then_resume_completes_and_cancellation_preserves_source(self):
        bench = Workbench(self.home)
        self.addCleanup(bench.close)
        source = encode(program([{"operator": "Rest", "glyph": "≈∅"}, {"operator": "QPE", "glyph": "Φ"}])).decode()
        job = bench.submit(source)
        self.assertEqual(wait_job(bench, job["id"])["state"], "paused")
        bench.resume(job["id"])
        self.assertEqual(wait_job(bench, job["id"])["state"], "completed")

    def test_queued_cancellation_and_manual_return(self):
        bench = Workbench(self.home, start_worker=False)
        self.addCleanup(bench.close)
        source = encode(program()).decode()
        job = bench.submit(source)
        self.assertEqual(bench.cancel(job["id"])["state"], "cancelled")
        self.assertEqual(bench.source(job["id"]), source)
        bench.resume(job["id"])
        bench.start()
        self.assertEqual(wait_job(bench, job["id"])["state"], "completed")

    def test_failed_operator_is_recorded_and_worker_continues(self):
        bench = Workbench(self.home)
        self.addCleanup(bench.close)
        bad = program([{"operator": "QPE", "glyph": "Φ", "parameters": {"phase": 2}}])
        job = bench.submit(encode(bad).decode())
        failure = wait_job(bench, job["id"])
        self.assertEqual(failure["state"], "failed")
        self.assertIn("phase", failure["error"])
        good = bench.submit(encode(program()).decode())
        self.assertEqual(wait_job(bench, good["id"])["state"], "completed")

    def test_encrypted_export_restores_exact_source_and_checkpoint(self):
        sender = Workbench(self.home/"sender")
        receiver = Workbench(self.home/"receiver", start_worker=False)
        self.addCleanup(sender.close)
        self.addCleanup(receiver.close)
        source = (ROOT/"examples/QuantumCompute.NewGlyph.v3.xi").read_text()
        job = sender.submit(source)
        self.assertEqual(wait_job(sender, job["id"])["state"], "completed")
        wire = sender.export(job["id"], receiver.identity().public())
        accepted = receiver.receive(wire, sender.identity().public())
        self.assertEqual(receiver.runtime.source(accepted["source_sha256"]), source.encode())
        self.assertTrue(accepted["checkpoint_retained"])
        self.assertFalse(accepted["execution_authorized_by_receipt"])

    def test_engine_drift_holds_queued_jobs_and_duplicate_home_is_refused(self):
        bench = Workbench(self.home, start_worker=False)
        bench.submit(encode(program()).decode())
        with self.assertRaises(QuantumComputeError):
            Workbench(self.home)
        bench.close()
        with patch("xi_quantum.workbench.engine_hash", return_value="changed"):
            held = Workbench(self.home, start_worker=False)
            self.addCleanup(held.close)
            self.assertEqual(held.list()[0]["state"], "needs_recompile")

    def test_resource_profile_change_preserves_job_and_requires_a_new_request(self):
        first = Workbench(self.home, start_worker=False)
        job = first.submit(encode(program()).decode())
        first.close()
        second = Workbench(self.home, profile=Profile("larger", 128), start_worker=False)
        self.addCleanup(second.close)
        self.assertEqual(second.get(job["id"])["state"], "needs_recompile")
        self.assertEqual(second.source(job["id"]), encode(program()).decode())
        with self.assertRaisesRegex(QuantumComputeError, "profile"):
            second.resume(job["id"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.bench = Workbench(temporary.name)
        self.addCleanup(self.bench.close)
        self.token = "test-only-owner-token-of-sufficient-length"
        self.server = make_server(self.bench, port=0, token=self.token, allowed_origin="http://localhost:5173")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.client = LivingCircuitClient(f"http://127.0.0.1:{self.server.server_port}{BASE}", token=self.token)

    def test_real_socket_compile_submit_events_and_source(self):
        source = (ROOT/"examples/QuantumCompute.NewGlyph.v3.xi").read_text()
        self.assertEqual(self.client.request("/examples/new-glyph")["source"], source)
        self.assertEqual(len(self.client.compile(source)["steps"]), 3)
        job = self.client.submit(source, "http-roundtrip")
        result = wait_job(self.bench, job["id"])
        self.assertEqual(self.client.job(job["id"])["state"], "completed")
        self.assertTrue(result["result"]["integrity"]["ok"])
        self.assertGreater(len(self.client.events(job["id"])["events"]), 2)
        self.assertEqual(self.client.request(f"/jobs/{job['id']}/source")["source"], source)

    def test_auth_public_catalogue_bad_json_and_explicit_cors(self):
        anonymous = LivingCircuitClient(self.client.base_url)
        self.assertIn("VQE", [op["operator"] for op in anonymous.capabilities()["operators"]])
        with self.assertRaisesRegex(ValueError, "401"):
            anonymous.request("/jobs")
        request = Request(self.client.base_url+"/compile", data=b"broken", headers={
            "Authorization": "Bearer "+self.token, "Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 400)
        request = Request(self.client.base_url+"/jobs", method="OPTIONS", headers={"Origin": "http://localhost:5173"})
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertIn(BASE+"/jobs", openapi()["paths"])


if __name__ == "__main__":
    unittest.main()
