"""Render the checked-in Xi phase-noise JSON into a report and optional plot.

Report generation uses the standard library. --plot additionally needs
matplotlib; it is optional and is not a simulator or CI dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def render(result_path: Path, *, plot: bool = False, ci_url: str | None = None) -> Path:
    data = json.loads(result_path.read_text())
    points = data["points"]
    config = data["configuration"]
    source = data["source"]
    folder = result_path.parent
    shots = config["shots_per_arm_per_probability"]
    improved = ", ".join(f'{p["p"]:g}' for p in points if p["observed_regime"] == "improves") or "none"
    worsened = ", ".join(f'{p["p"]:g}' for p in points if p["observed_regime"] == "worsens") or "none"
    unresolved = ", ".join(f'{p["p"]:g}' for p in points if p["observed_regime"].startswith("not resolved")) or "none"

    lines = [
        "# Xi glyph-field independent phase-noise benchmark", "",
        f'Run `{data["run_id"]}` uses **{shots:,} trials per arm per probability**, '
        f'**{len(points)} probabilities**, **{data["cost"]["total_shots"]:,} simulated trials**, '
        f'and master seed **{config["master_seed"]}**.', "",
        "The fixed minimum-weight phase-flip repetition code improves channel reliability for "
        "**0 < p < 0.5**, worsens it for **0.5 < p < 1**, and ties the bare channel at "
        "**p = 0, 0.5, 1** under this one-round independent-Z model. The analytical statement "
        "is exact; the Monte Carlo estimates below have finite-sample uncertainty.", "",
        f"The conservative nominal 95% difference intervals resolve improvement at p = {improved}; "
        f"worsening at p = {worsened}. They do not resolve a difference at p = {unresolved}. "
        "Failure to resolve a difference does not establish equality.", "",
        "## Observed logical error rates", "",
        "Intervals are marginal 95% Wilson score intervals. They describe sampling uncertainty "
        "within this simulated model, not model error or hardware uncertainty. The collection "
        "of rate intervals is not a simultaneous 95% band.", "",
        "| Physical Z probability p | Encoded failures / n | Encoded rate [95% CI] | 3p² − 2p³ | Bare failures / n | Bare rate [95% CI] | Observed comparison |",
        "|---:|---:|---:|---:|---:|---:|:---|",
    ]
    for point in points:
        e, b = point["encoded"], point["unencoded"]
        elo, ehi = e["logical_error_rate_ci95"]
        blo, bhi = b["logical_error_rate_ci95"]
        lines.append(
            f'| {point["p"]:g} | {e["logical_failures"]:,} / {shots:,} '
            f'| {e["logical_error_rate"]:.6f} [{elo:.6f}, {ehi:.6f}] '
            f'| {point["analytic"]["encoded_logical_error_rate"]:.6f} '
            f'| {b["logical_failures"]:,} / {shots:,} '
            f'| {b["logical_error_rate"]:.6f} [{blo:.6f}, {bhi:.6f}] '
            f'| {point["observed_regime"]} |'
        )
    if plot:
        _plot(data, folder / "reliability.png")
        lines.extend(["", "![Logical error rates and improvement with uncertainty](reliability.png)"])

    covered = sum(p["encoded"]["logical_error_rate_ci95"][0]
                  <= p["analytic"]["encoded_logical_error_rate"]
                  <= p["encoded"]["logical_error_rate_ci95"][1] for p in points)
    bare_covered = sum(p["unencoded"]["logical_error_rate_ci95"][0] <= p["p"]
                       <= p["unencoded"]["logical_error_rate_ci95"][1] for p in points)
    lines.extend([
        "", f"The encoded analytical prediction falls inside {covered}/{len(points)} marginal "
        f"95% intervals; the bare prediction falls inside {bare_covered}/{len(points)}. "
        "95% intervals are not expected to cover every realized rate. The tests use fixed seeds "
        "and six-sigma sampling tolerances rather than requiring every 95% interval to contain its prediction.",
        "", "## What is being measured", "",
        "The data code uses stabilizers X0X1 and X1X2. Encoding applies two CNOTs from data "
        "qubit 0 into |00> ancillas, then H on all three data qubits. The decoder selects "
        "zero or one Z operation from the measured syndrome. Every shot actually executes "
        "noise sampling, both projective stabilizer measurements, correction, and decoding "
        "through `apply_operator`. The analytical expression is never used to classify a shot.", "",
        "An additional noiseless reference qubit is entangled with the input. Its decoded "
        "Bell-state overlap measures **entanglement fidelity**, which is 1 for the identity "
        "channel and 0 for a nontrivial logical Pauli. Logical error rate is the observed "
        "fraction of these Bell-reference failures. Encoded runs contain three data qubits "
        "plus one reference; bare runs contain one data qubit plus one reference. Noise "
        "targets data qubits only. Preparation, encoding, stabilizer readout, recovery and "
        "decoding are ideal. The two arms use separate random streams at the same physical p.", "",
        "The residual operator after an uncorrectable encoded pattern is logical **X**; "
        "the bare channel applies **Z**. Exhaustive exact-vector execution on the original "
        "T-state verifies fidelity 1 for correctable masks and 0.5 for uncorrectable masks. "
        "The T-state column below weights those eight simulated conditional fidelities by "
        "the observed mask counts. It is not a separate Monte Carlo run on T-state inputs.", "",
        "| p | Encoded entanglement fidelity | Bare entanglement fidelity | Encoded T-state fidelity | Bare T-state fidelity |",
        "|---:|---:|---:|---:|---:|",
    ])
    for point in points:
        e, b = point["encoded"], point["unencoded"]
        lines.append(f'| {point["p"]:g} | {e["entanglement_fidelity"]:.6f} | {b["entanglement_fidelity"]:.6f} '
                     f'| {e["t_state_fidelity"]:.6f} | {b["t_state_fidelity"]:.6f} |')
    lines.extend([
        "", "The corresponding ensemble T-state fidelities are 1 − q/2 and 1 − p, while "
        "channel entanglement fidelities are 1 − q and 1 − p. The T-state can therefore look "
        "better even when encoded channel reliability is worse. The crossover claim uses "
        "logical error rates and channel fidelity, not that state-specific overlap. Fidelity "
        "confidence intervals are recorded in the JSON as monotone transformations of the "
        "failure-rate Wilson intervals.", "", "## Analytical benchmark and exhaustive audit", "",
        "With independent Bernoulli(p) faults, two or three faults leave Z0Z1Z2 after "
        "minimum-weight correction. The inverse encoder maps this residual to X on the "
        "logical input, returning both recovery registers to |00>. Thus", "",
        "```math", "q = P_L = 3p^2(1-p) + p^3 = 3p^2 - 2p^3,", "p-q = p(1-p)(1-2p).", "```", "",
        "The decoder stays fixed for the entire sweep, including p > 0.5. A decoder "
        "that knows errors are more probable than no error could choose different recovery "
        "representatives there; that is a different experiment.", "",
        "All eight fault masks are explicitly simulated on Bell and T inputs:", "",
        "| Mask (q0 q1 q2) | Measured syndrome | Corrected qubit | Decoded Pauli | Entanglement fidelity | T-state fidelity |",
        "|:---|:---|:---|:---|---:|---:|",
    ])
    for row in data["exhaustive_masks"]:
        lines.append(f'| {row["mask"]} | {row["syndrome"]} | {row["corrected_qubit"]} '
                     f'| {row["logical_pauli"]} | {row["entanglement_fidelity"]:g} | {row["t_state_fidelity"]:g} |')
    ewall = sum(p["cost"]["encoded_wall_seconds"] for p in points)
    bwall = sum(p["cost"]["unencoded_wall_seconds"] for p in points)
    ecpu = sum(p["cost"]["encoded_cpu_seconds"] for p in points)
    bcpu = sum(p["cost"]["unencoded_cpu_seconds"] for p in points)
    traces = data["persistence"]["traces"]
    capsules = sum(t["event_count"] for t in traces)
    lines.extend([
        "", "## Execution costs", "",
        f'Python: `{data["environment"]["python"].splitlines()[0]}`. '
        f'Host: `{data["environment"]["platform"]}`.', "",
        "| Measured quantity | Encoded arm | Bare arm |", "|:---|---:|---:|",
        f"| Wall seconds for shot loops | {ewall:.3f} | {bwall:.3f} |",
        f"| CPU seconds for shot loops | {ecpu:.3f} | {bcpu:.3f} |",
        f'| Operator calls | {sum(p["cost"]["encoded_operator_calls"] for p in points):,} '
        f'| {sum(p["cost"]["unencoded_operator_calls"] for p in points):,} |',
        f'| Maximum sparse branches | {max(p["cost"]["encoded_max_branches"] for p in points)} '
        f'| {max(p["cost"]["unencoded_max_branches"] for p in points)} |',
        "| Data qubits + noiseless reference | 3 + 1 | 1 + 1 |", "",
        f'Total simulation: {data["cost"]["simulation_wall_seconds"]:.3f} wall seconds and '
        f'{data["cost"]["simulation_cpu_seconds"]:.3f} CPU seconds. '
        f'Process peak resident memory: {data["cost"]["process_peak_rss_bytes"] / 1024**2:.2f} MiB. '
        f'The encoded loop took {ewall / bwall:.2f}× the bare loop wall time on this host.', "",
        "Per-arm loops reuse noiseless prepared templates and exclude SQLite. Measurements "
        "include seed derivation, state copying/canonicalization, sampling, decoder execution "
        "and fidelity classification. Templates and exhaustive-mask checks are included in "
        "the total simulation cost. RSS is a process-wide high-water mark. These are host "
        "software costs, not gate durations, physical energy costs, or hardware performance.", "",
        f'The separate persistence pass committed {len(traces)} trial traces '
        f'({data["persistence"]["trials_per_arm_per_probability"]} per arm per probability), '
        f'{capsules} total capsules, in {data["persistence"]["wall_seconds"]:.3f} seconds; '
        f'the SQLite file is {data["persistence"]["database_bytes"]:,} bytes. '
        "Every trace reopened SQLite after noise injection and verified its causal hash "
        "chain. Aggregate shots run in memory; only the explicitly listed traces were "
        "persisted. Set `--ledger-trials` equal to `--shots` to persist every transition "
        "for every sampled shot, at additional storage and runtime cost.", "",
        "## Reproduce", "", "From the repository root:", "", "```bash",
        f'git checkout {source["commit"]}',
        "python -m venv /tmp/xi-noise-venv",
        "/tmp/xi-noise-venv/bin/python -m pip install -r requirements.txt -r requirements-ci.lock",
        f'/tmp/xi-noise-venv/bin/python -m xi_field.noise_benchmark --shots {shots} --seed {config["master_seed"]} \\',
        "  --ledger-trials 2 --db .xi/reproduced-noise.sqlite3 --output .xi/reproduced-noise.json",
        "/tmp/xi-noise-venv/bin/python -m pytest -v",
        "```", "",
        "For an existing Python environment, the benchmark itself uses only the standard "
        "library and the existing local Xi modules. The locked dependencies are needed for "
        "the full repository checks and HTTP interface.", "",
        "Run the same command twice to replay the same SQLite worlds. Counts, mask "
        "histograms, fidelities, configuration ID, capsule count and existing head hashes "
        "must match. Wall/CPU/memory costs can differ. A fresh SQLite database has new "
        "creation timestamps and therefore different event hashes; its scientific results "
        "and event counts still reproduce. The master seed is expanded with SHA-256 over "
        "schema, master seed, float.hex(p), shot index and stream name; the first 16 digest "
        "bytes become a big-endian seed. Each sample uses Python Random/MT19937 and "
        "one `random() < p` draw per listed data qubit. Encoded noise, bare noise and "
        "syndrome streams are domain-separated; rate-list ordering does not change a point.", "",
        "To render this report again (optionally install matplotlib for the PNG):", "", "```bash",
        "python benchmarks/render_phase_noise.py benchmarks/phase-noise/results.json --plot", "```", "",
        "## Sources and validation", "",
        f'- [Benchmark implementation]({source["links"]["xi_field/noise_benchmark.py"]})',
        f'- [Noise and QEC operators]({source["links"]["xi_field/operators.py"]})',
        f'- [Reproducible benchmark tests]({source["links"]["tests/test_xi_noise_benchmark.py"]})',
        f'- [CI workflow]({source["links"][".github/workflows/python-package-conda.yml"]})',
        "- [Full machine-readable results](results.json), including all sample counts, seeds, intervals, source hashes and trace receipts.",
        "- [SQLite trace ledger](ledger.sqlite3).",
        f'- Results SHA-256: `{hashlib.sha256(result_path.read_bytes()).hexdigest()}`.',
        f'- Source commit: `{source["commit"]}`; source files dirty at execution: `{source["source_files_dirty"]}`.',
    ])
    if ci_url:
        lines.append(f"- [GitHub Actions validation]({ci_url}).")
    lines.extend([
        "", "The regression suite retains single-fault recovery at every qubit, the original "
        "T-state demonstration, restart persistence, idempotent replay, world invariants "
        "and symbolic capsule behavior. New tests cover all masks, Z composition by "
        "parity, seeded zero/single/multiple sampling, invalid-input rollback, stale-syndrome "
        "prevention, fixed seed outcomes, mask independence, analytical rates, confidence "
        "intervals, and interrupted/repeated SQLite benchmark runs. CI also runs a "
        "smaller seeded benchmark twice and uploads its JSON and SQLite ledger.", "",
        "This is a development reference for The Field Ξ.QuantumCompute under a defined "
        "simulated noise model. The next useful extensions are independently controlled "
        "gate/readout faults and repeated correction rounds, so their contributions can "
        "be measured separately from these ideal operations. No physical-device conclusion "
        "is inferred from this experiment.", "",
    ])
    output = folder / "REPORT.md"
    output.write_text("\n".join(lines))
    return output


def _plot(data: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, (ax, delta) = plt.subplots(1, 2, figsize=(12, 4.5), layout="constrained")
    grid = [i / 1000 for i in range(1001)]
    ax.plot(grid, [3 * p*p - 2 * p*p*p for p in grid], color="#285bb4", label="Encoded: 3p² − 2p³")
    ax.plot(grid, grid, color="#bd621f", label="Bare: p")
    for arm, color, marker in (("encoded", "#285bb4", "o"), ("unencoded", "#bd621f", "s")):
        x = [p["p"] for p in data["points"]]
        y = [p[arm]["logical_error_rate"] for p in data["points"]]
        low = [max(0, value - point[arm]["logical_error_rate_ci95"][0]) for value, point in zip(y, data["points"])]
        high = [max(0, point[arm]["logical_error_rate_ci95"][1] - value) for value, point in zip(y, data["points"])]
        ax.errorbar(x, y, yerr=[low, high], fmt=marker, color=color, ms=4, capsize=3,
                    label=f"{arm.title()} trials (95% CI)", ls="none")
    ax.set(xlabel="Independent Z probability per data qubit, p", ylabel="Logical error probability",
           xlim=(-0.02, 1.02), ylim=(-0.02, 1.02), title="Exact channel simulation vs analytical model")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.18)
    delta.plot(grid, [p * (1 - p) * (1 - 2 * p) for p in grid], color="#38794e", label="Analytical improvement")
    x = [p["p"] for p in data["points"]]
    y = [p["error_rate_improvement"] for p in data["points"]]
    low = [max(0, value - p["error_rate_improvement_ci95_conservative"][0]) for value, p in zip(y, data["points"])]
    high = [max(0, p["error_rate_improvement_ci95_conservative"][1] - value) for value, p in zip(y, data["points"])]
    delta.errorbar(x, y, yerr=[low, high], fmt="o", color="#38794e", ms=4, capsize=3, label="Trials (nominal 95% CI)")
    delta.axhline(0, color="#555555", lw=0.8)
    delta.axvline(0.5, color="#555555", lw=0.8, ls="--")
    delta.text(0.12, 0.115, "Correction helps", color="#38794e")
    delta.text(0.64, -0.12, "Correction hurts", color="#8b3b3b")
    delta.set(xlabel="Independent Z probability per data qubit, p", ylabel="Bare − encoded logical error rate",
              title="Fixed decoder crossover at p = 0.5", xlim=(-0.02, 1.02), ylim=(-0.145, 0.145))
    delta.legend(fontsize=8, loc="upper right")
    delta.grid(alpha=0.18)
    fig.suptitle("Xi glyph-field · independent phase-noise benchmark", fontsize=14)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--ci-url")
    args = parser.parse_args()
    print(render(args.results, plot=args.plot, ci_url=args.ci_url))


if __name__ == "__main__":
    main()
