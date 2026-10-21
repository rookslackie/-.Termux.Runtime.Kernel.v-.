"""Seeded numerical counterparts to the recovered ORT/LIGO signal sketch.

The default data are synthetic. Matched-filter statistics assume independent
Gaussian white noise with the declared sigma; no detector data are implied.
"""
from __future__ import annotations

import math

import numpy as np

from .common import Profile, QuantumComputeError, finite, integer


def signal_lab(*, sample_rate=1024, duration=1.0, frequencies=None, amplitudes=None,
               noise_sigma=.5, gamma=.1, dt=.01, seed=20261021, profile=Profile()):
    integer(sample_rate, "sample_rate", 16, 65536)
    integer(seed, "seed", 0)
    duration, noise_sigma, gamma, dt = [finite(v, n) for v, n in
        ((duration, "duration"), (noise_sigma, "noise_sigma"), (gamma, "gamma"), (dt, "dt"))]
    if not .01 <= duration <= 60 or not 0 < noise_sigma <= 100 or not 0 < gamma <= 100 or not 0 < gamma*dt < 2:
        raise QuantumComputeError("SignalLab requires .01..60 s, positive noise, and 0 < gamma*dt < 2")
    count = int(sample_rate * duration)
    if count < 16 or count * 128 > profile.memory_mib * 1024 * 1024:
        raise QuantumComputeError("SignalLab sample workspace exceeds the profile or has fewer than 16 samples")
    frequencies = [50.0, 120.0] if frequencies is None else frequencies
    amplitudes = [1.0, .5] if amplitudes is None else amplitudes
    if (type(frequencies) is not list or type(amplitudes) is not list
            or not 1 <= len(frequencies) <= 32 or len(frequencies) != len(amplitudes)):
        raise QuantumComputeError("frequencies and amplitudes must be equal-length lists of 1..32 values")
    frequencies = [finite(f, "frequency") for f in frequencies]
    amplitudes = [finite(a, "amplitude") for a in amplitudes]
    if any(not 0 < f < sample_rate/2 for f in frequencies):
        raise QuantumComputeError("Frequencies must lie strictly below the Nyquist frequency")
    rng = np.random.default_rng(seed)
    t = np.arange(count) / sample_rate
    clean = sum(a*np.sin(2*math.pi*f*t) for f, a in zip(frequencies, amplitudes))
    observed = clean + rng.normal(0, noise_sigma, count)
    spectrum = np.abs(np.fft.rfft(observed)) * 2 / count
    bins = np.fft.rfftfreq(count, 1/sample_rate)
    peaks = np.argsort(spectrum[1:])[-min(8, len(spectrum)-1):][::-1] + 1
    # Normalize for known iid white-noise variance; zero-lag projection statistic.
    template = np.sin(2*math.pi*frequencies[0]*t)
    correlation = np.correlate(observed, template, mode="same") if count <= 8192 else None
    statistic = float(np.dot(observed, template) / (noise_sigma*np.linalg.norm(template)))
    samples = rng.normal(size=(2, 4096)) * np.array([[1.0], [.2]])
    covariance = np.cov(samples)
    trajectory = np.zeros(min(count, 8192))
    for i in range(1, len(trajectory)):
        trajectory[i] = trajectory[i-1]*(1-gamma*dt) + rng.normal()*math.sqrt(dt)
    return {"algorithm": "SignalLab", "input_kind": "seeded synthetic signal",
            "source_lineage": "Ξ_ORT_LIGO_SignalEngine.py (attached original retained)",
            "seed": seed, "sample_rate": sample_rate, "samples": count,
            "frequency_components_hz": frequencies, "amplitudes": amplitudes,
            "noise_sigma": noise_sigma, "fft_peaks": [{"hz": float(bins[i]), "amplitude": float(spectrum[i])} for i in peaks],
            "matched_filter": {"statistic": statistic, "normalization": "white-noise sigma * template L2 norm",
                "correlation_preview": correlation[::max(1, count//256)].tolist() if correlation is not None else None},
            "covariance": {"matrix": covariance.tolist(), "determinant": float(np.linalg.det(covariance)),
                           "interpretation": "classical sampled covariance; no quantum squeezing assertion"},
            "langevin": {"scheme": "Euler-Maruyama OU: x += -gamma*x*dt + sqrt(dt)*N(0,1)",
                "gamma": gamma, "dt": dt, "trajectory": trajectory[::max(1, len(trajectory)//256)].tolist()},
            "hilbert_projection": {"bra": "+", "ket": "0", "probability": .5},
            "preview": {"times": t[::max(1, count//256)].tolist(),
                        "observed": observed[::max(1, count//256)].tolist()},
            "resources": {"estimated_workspace_bytes": count*128, "memory_budget_mib": profile.memory_mib}}
