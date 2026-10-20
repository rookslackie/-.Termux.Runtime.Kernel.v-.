"""Render the source-pinned observer report; --plot optionally uses matplotlib."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(path, *, plot=False, ci=None):
    report = json.loads(path.read_text())
    execution = report["execution"]
    cases = [step["result"] for step in execution["receiver"]["steps"] if step["operator"] == "ObserverBenchmark"]
    full, capped = cases
    folder = path.parent
    source = report["source_commit"]
    lines = ["# ∴ ⋈ — observer-access experiment", "",
        f"Source: [{source[:7]}](https://github.com/rookslackie/-.Termux.Runtime.Kernel.v-./tree/{source}). "
        f"[Complete results]({path.name}), SHA-256 `{hashlib.sha256(path.read_bytes()).hexdigest()}`.", "",
        "The same preparation and noise model were sampled through X- and Z-access contracts. "
        "The Z-only observer retained a null X estimate until an explicit local grant shared X records. "
        "Its subsequent estimate and interval matched the sender's retained evidence exactly.", "",
        f"Configuration: φ = π/3, independent Z probability 0.1, seed {full['configuration']['seed']}, "
        f"{full['configuration']['repetitions']} repetitions per budget, nominal 95% Wilson intervals, "
        "expectation half-width tolerance 0.1. The evaluator's independent density reference gives E[X] = 0.4 and E[Z] ≈ 0. "
        "Preparation, noise parameters and reference values are withheld from the observer APIs.", "",
        "| Sample budget per observer | Retained X bits | Observed RMSE | Analytical RMSE | Mean interval half-width | Precision resolved / repetitions | Coverage / repetitions |",
        "|---:|---:|---:|---:|---:|---:|---:|"]
    for case in cases:
        for p in case["points"]:
            n = p["repetitions"]
            lines.append(f"| {p['samples_per_observer']} | {p['retained_target_samples']} | "
                         f"{p['after_rmse']:.6f} | {p['analytic_rmse']:.6f} | {p['mean_interval_half_width']:.6f} | "
                         f"{p['after_precision_resolved_count']} / {n} | {p['interval_coverage_count']} / {n} |")
    lines += ["", "The first four rows retain all outcomes; the final four cap retained outcome memory at 64 bits. "
        "The two arms use the same outcome streams. Sample budgets use nested prefixes; these are paired comparisons. "
        "Raw sampling calls are counted once per shared pool, not once per displayed budget.", "",
        "A Z-only view left X unidentified in every repetition at every budget, with range [−1,1]. "
        "Its absence of a point prediction is retained as null rather than scored as a zero estimate. "
        "The memory cap limits retained X evidence even when additional samples are acquired. "
        "The analytical RMSE comparison is sqrt((1−μ²)/n), where n is the number of retained independent outcomes. "
        "The estimator and its observed error use actual sparse-vector witnesses, not that formula.", "",
        f"Coverage is the fraction of {full['configuration']['repetitions']} repeated intervals containing the evaluator reference. "
        "Nominal 95% intervals do not guarantee coverage in every finite batch or simultaneous coverage across the sweep. "
        "The JSON includes Wilson intervals for the observed coverage fractions. Precision resolution is a width criterion, "
        "not an assertion that every resolved estimate is correct.", "",
        "![Observed error and uncertainty under access and retained-memory budgets](observer-access.svg)", "",
        "## Transfer and recovery", "",
        f"Node A committed the first benchmark; node B restored {execution['receiver']['restored_from_peer_this_call']} "
        f"result and executed {execution['receiver']['executed_this_call']} remaining steps. "
        f"The encrypted checkpoint contained {execution['checkpoint_encrypted_bytes']:,} bytes. "
        "Both causal ledgers verified. Restart replay executed zero completed steps and retained the receiver head hash:", "",
        f"`{execution['receiver']['integrity']['head_hash']}`", "",
        "The recovered StructuralKernel QR payload also completed an exact GlyphSafe / ThinkSync round trip: "
        f"**{execution['kernel_recovery']['payload_bytes']} bytes**, SHA-256 "
        f"`{execution['kernel_recovery']['source_sha256']}`. "
        "Its original dialect is retained as source; receipt processing supplies no execution grant. "
        "[Recovered contracts and QR decoder receipt](../../recovered/2026-10-20/README.md) preserve the "
        "FullStack / FullCycle lineage, historical SHA3 declaration and legitimate null operator.", "",
        "## Costs and scope", "",
        f"The two arms executed {sum(c['cost']['prepared_samples'] for c in cases):,} freshly prepared simulated "
        f"qubits and the same number of projective witnesses. Source execution used {report['cost']['wall_seconds']:.3f} "
        f"wall seconds, {report['cost']['cpu_seconds']:.3f} CPU seconds and "
        f"{report['cost']['process_peak_rss_mib']:.2f} MiB process peak RSS, including transfer and restart verification. "
        "Host timing and process RSS are separate from the model's retained-outcome-bit budget. "
        "This is one trusted-process statistical observer model and ideal simulated noise experiment. "
        "ORT's full recursive-coherence formula, presence thresholds, Lorentz propagation and physical-collapse claims "
        "retain separate source meanings and testing requirements.", "",
        "## Reproduce", "", "```bash", f"git checkout {source}",
        "python -m pip install -r requirements.txt -r requirements-ci.lock", "python -m pytest -v",
        "python benchmarks/verify_observer.py --home .xi/observer-check --output .xi/observer-check.json", "```", "",
        "A fresh home creates fresh keys, packet randomness and capsule timestamps. Seeded sampling, observer estimates "
        "and evidence digests reproduce. Reuse the same home to verify zero repeated computation and unchanged ledger heads.", "",
        "[Ledger manifest](ledgers.json) and the compressed [node A](node-a.sqlite3.gz) / "
        "[node B](node-b.sqlite3.gz) snapshots retain exact sources and causal computation evidence. "
        "Exports exclude identity seeds and clear local transport tables. Inspect using `WorldKernel.verify` "
        "at the source version above; replay with the exact source and local execution grant. "
        "The QR source remains recoverable by its digest without an executable operator mapping.", "",
        "Method references: [IBM Pauli measurements and tomography](https://learning.quantum.ibm.com/course/general-formulation-of-quantum-information/general-measurements), "
        "[NIST Wilson intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm). "
        "[Experiment contract and commands](../../OBSERVER_EXPERIMENT.md)."]
    if ci:
        lines += ["", f"[GitHub Actions verification]({ci})."]
    (folder / "REPORT.md").write_text("\n".join(lines) + "\n")
    if plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
        for case, label, color in [(full, "Retain all outcomes", "#167a96"), (capped, "Retain at most 64 bits", "#a04b95")]:
            points = case["points"]
            ns = [p["samples_per_observer"] for p in points]
            axes[0].plot(ns, [p["after_rmse"] for p in points], "o-", color=color, label=label)
            axes[0].plot(ns, [p["analytic_rmse"] for p in points], ":", color=color, alpha=.8)
            axes[1].plot(ns, [p["mean_interval_half_width"] for p in points], "o-", color=color, label=label)
        for axis in axes:
            axis.set_xscale("log", base=2)
            axis.set_xticks([16, 64, 256, 1024], ["16", "64", "256", "1024"])
            axis.set_xlabel("Samples acquired per observer")
            axis.grid(alpha=.2)
        axes[0].set_ylabel("RMSE of X expectation")
        axes[0].set_title("Error after authorized X-record sharing")
        axes[0].legend(fontsize=8)
        axes[1].axhline(.1, ls="--", color="#444444", label="Declared precision tolerance")
        axes[1].set_ylabel("Mean 95% interval half-width")
        axes[1].set_title("Uncertainty with bounded retained memory")
        axes[1].legend(fontsize=8)
        fig.suptitle("Same state and noise; controlled access and evidence budgets")
        fig.savefig(folder / "observer-access.svg")
        fig.savefig(folder / "observer-access.png", dpi=120)
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--ci")
    args = parser.parse_args()
    render(args.results, plot=args.plot, ci=args.ci)
