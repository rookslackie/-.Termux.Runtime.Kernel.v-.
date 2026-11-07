# Grover (n=6, k=1) — Qiskit-style pseudocode

from qiskit import QuantumCircuit
n = 6  # 64 states
qc = QuantumCircuit(n, n)
# 1) Initialize to uniform superposition
qc.h(range(n))

# 2) Repeat Grover iteration (oracle + diffuser)
# Assume 1 marked state |w⟩; oracle is a phase flip on |w⟩.
iterations = 6  # near optimal for N=64, k=1
for _ in range(iterations):
    qc.append(Oracle(marked='w'), range(n))  # phase-flip |w⟩
    qc.h(range(n)); qc.x(range(n))
    qc.h(n-1); qc.mcx(list(range(n-1)), n-1); qc.h(n-1)
    qc.x(range(n)); qc.h(range(n))

# 3) Measure
qc.measure(range(n), range(n))