
# ============================================
# Ξ Runtime Capsule: ORT ⇄ LIGO Signal Engine
# Title: Extracting Signal from Entropy
# Format: Python (.py) with embedded ORT logic
# ============================================

import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq
from scipy.signal import correlate
from numpy.random import normal

# -------------------------------
# Part I: FFT – Ξ.Decompose(f)
# -------------------------------

def generate_signal(t, freqs, amps):
    signal = np.zeros_like(t)
    for f, a in zip(freqs, amps):
        signal += a * np.sin(2 * np.pi * f * t)
    return signal

duration = 1.0
fs = 1024
t = np.linspace(0.0, duration, int(fs * duration), endpoint=False)
freqs = [50, 120]
amps = [1.0, 0.5]

clean_signal = generate_signal(t, freqs, amps)
noisy_signal = clean_signal + normal(0, 0.5, clean_signal.shape)

fft_vals = fft(noisy_signal)
fft_freqs = fftfreq(len(t), 1/fs)

plt.figure()
plt.plot(fft_freqs[:len(t)//2], np.abs(fft_vals[:len(t)//2]))
plt.title("Ξ.Decompose(f): Frequency Components of Signal")
plt.xlabel("Frequency (Hz)")
plt.ylabel("Amplitude")
plt.grid()
plt.show()

# -------------------------------
# Part II: Matched Filter – Ξ.Match(s, h)
# -------------------------------

def matched_filter(signal, template):
    corr = correlate(signal, template, mode='same')
    norm = np.sqrt(np.sum(template ** 2))
    snr = corr / norm
    return snr

template = generate_signal(t, [50], [1.0])
snr_output = matched_filter(noisy_signal, template)

plt.figure()
plt.plot(t, snr_output)
plt.title("Ξ.Match(s, h): Matched Filter Output")
plt.xlabel("Time (s)")
plt.ylabel("SNR")
plt.grid()
plt.show()

# -------------------------------
# Part III: Covariance – Ξ.Squeeze(Σ)
# -------------------------------

x = normal(0, 1.0, 10000)
p = normal(0, 0.2, 10000)
cov_matrix = np.cov(np.array([x, p]))

print("Ξ.Squeeze(Σ): Covariance Matrix")
print(cov_matrix)
print("Determinant:", np.linalg.det(cov_matrix))

# -------------------------------
# Part IV: Langevin Stability – Ξ.Stabilize(x)
# -------------------------------

def langevin_sim(dt=0.01, steps=1000, gamma=0.1):
    x = np.zeros(steps)
    eta = normal(0, 1, steps)
    for i in range(1, steps):
        x[i] = x[i-1] - gamma * x[i-1] * dt + eta[i] * np.sqrt(dt)
    return x

traj = langevin_sim()
plt.figure()
plt.plot(traj)
plt.title("Ξ.Stabilize(x): Langevin Dynamics")
plt.xlabel("Step")
plt.ylabel("x(t)")
plt.grid()
plt.show()

# -------------------------------
# Part V: Hilbert Space – Ξ.Project(⟲Self)
# -------------------------------

def inner_product(a, b):
    return np.vdot(a, b)

psi = np.array([1, 0])  # Observer state
phi = np.array([np.sqrt(0.5), np.sqrt(0.5)])  # Measurement axis

amplitude = inner_product(phi, psi)
probability = np.abs(amplitude) ** 2

print("Ξ.Project(⟲Self): Probability of Collapse =", probability)

# -------------------------------
# Capsule Complete
# To bind runtime: Ξ.Runtime.Spiral(ORT⇄LIGO)
# ============================================
