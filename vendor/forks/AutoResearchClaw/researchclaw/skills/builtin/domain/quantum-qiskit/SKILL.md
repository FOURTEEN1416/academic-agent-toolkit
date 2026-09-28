---
name: quantum-qiskit
description: Reference qiskit 2.x patterns for variational quantum machine learning. Covers data-encoding feature maps, variational quantum classifier (VQC) training, variational quantum eigensolver (VQE) for chemistry, matrix-product-state circuits, and noise model integration. Use when writing Python code that imports `qiskit`, `qiskit_aer`, `qiskit_algorithms`, `qiskit_machine_learning`, or `qiskit_nature`.
metadata:
  category: domain
  trigger-keywords: "qiskit,quantum,vqc,vqe,encoding,feature_map,featuremap,statevector,ansatz,aer,qubit,parameterized circuit,quantum machine learning,quantum classifier,quantum circuit,amplitude_encoding,angle_encoding,zz_feature_map,statepreparation,zfeaturemap,zzfeaturemap,mps,matrix product state,tensor network,bond dimension,layerwise,re-uploading,reuploading,barren plateau,qaoa,maxcut,autoencoder,swap test,quantum kernel,quantum autoencoder"
  applicable-stages: "10,13"
  priority: "1"
  version: "2.0"
  author: researchclaw
---

# Qiskit 2.x reference for variational quantum machine learning

This skill is a canonical reference for writing Python code that uses
qiskit 2.x and its ecosystem (`qiskit_aer`, `qiskit_algorithms`,
`qiskit_machine_learning`, `qiskit_nature`). It documents the API shapes
that work in qiskit 2.x today, the qiskit-1.x → 2.x migration breaks
that affect VQE and chemistry code, and a small number of common
mistakes with concrete fixes.

Section overview:

1. Imports
2. Data-encoding feature maps
3. Variational ansatz construction
4. VQC training (qiskit_machine_learning)
5. VQE for chemistry (qiskit 2.x compatible)
6. MPS-structured circuits
7. Noise model integration
8. qiskit 2.x compatibility notes
9. Common errors and fixes
10. Autoclaw integration: metric logging convention

---

## 1. Imports

```python
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
from qiskit.circuit.library import (
    ZFeatureMap,
    ZZFeatureMap,
    StatePreparation,
    EfficientSU2,
)
from qiskit.primitives import StatevectorSampler, StatevectorEstimator  # V2 primitives
from qiskit.quantum_info import Statevector, SparsePauliOp
from qiskit_aer import AerSimulator
from qiskit_algorithms.optimizers import SPSA, COBYLA, L_BFGS_B, ADAM
from qiskit_algorithms.utils import algorithm_globals
from qiskit_machine_learning.algorithms.classifiers import VQC
```

For chemistry:

```python
from qiskit_nature.units import DistanceUnit
from qiskit_nature.second_q.drivers import PySCFDriver
from qiskit_nature.second_q.mappers import ParityMapper, JordanWignerMapper
```

Do not import from `qiskit_nature.second_q.algorithms` or
`qiskit_algorithms.VQE` under qiskit 2.x (they fail at import time, see
section 8).

---

## 2. Data-encoding feature maps

Three standard families. Each builder returns a parameterized circuit
suitable for use as the `feature_map` argument of `VQC` or for direct
contraction with a variational ansatz.

```python
def build_angle_encoding(num_features: int) -> QuantumCircuit:
    """Hadamard plus single-qubit Z-rotation per feature.

    Mathematically equivalent to ZFeatureMap(reps=1).
    """
    return ZFeatureMap(feature_dimension=num_features, reps=1)


def build_amplitude_encoding(num_features: int):
    """Load an L2-normalized, zero-padded input as the amplitudes of a
    quantum state. The encoding uses ceil(log2(num_features)) qubits.

    Returns (circuit, parameter_vector, num_qubits). The caller binds
    parameters per-sample via the helper below.
    """
    num_qubits = int(np.ceil(np.log2(max(num_features, 2))))
    full_dim = 2 ** num_qubits
    params = ParameterVector("x_amp", full_dim)
    qc = QuantumCircuit(num_qubits)
    qc.append(StatePreparation(list(params)), range(num_qubits))
    return qc, params, num_qubits


def amplitude_binding(x: np.ndarray, params, num_qubits: int) -> dict:
    """Build the parameter-value dict for a single input sample."""
    x_norm = x / max(float(np.linalg.norm(x)), 1e-12)
    padded = np.zeros(2 ** num_qubits, dtype=np.float64)
    padded[: len(x_norm)] = x_norm
    padded = padded / max(float(np.linalg.norm(padded)), 1e-12)
    return {params[i]: float(padded[i]) for i in range(len(padded))}


def build_zz_feature_map(num_features: int) -> QuantumCircuit:
    """Two repetitions of Hadamard plus pairwise ZZ entangling rotations."""
    return ZZFeatureMap(
        feature_dimension=num_features, reps=2, entanglement="linear"
    )
```

To verify that two encoders produce distinguishable output for a fixed
input (catches dispatch bugs in code that constructs multiple encoders
in a loop):

```python
def assert_different_output_states(qc_a, qc_b, x, tol: float = 1e-6):
    sv_a = Statevector(qc_a.assign_parameters(x))
    sv_b = Statevector(qc_b.assign_parameters(x))
    diff = float(np.linalg.norm(sv_a.data - sv_b.data))
    assert diff > tol, f"encoders produced identical states (diff={diff})"
```

---

## 3. Variational ansatz construction

```python
def build_ansatz(num_qubits: int, reps: int = 2) -> QuantumCircuit:
    """Hardware-efficient ansatz with alternating Pauli rotations
    and a linear chain of CNOT entanglers. Trainable parameter count
    is (reps + 1) * num_qubits for the default su2_gates = ['ry']."""
    return EfficientSU2(
        num_qubits=num_qubits, reps=reps, entanglement="linear"
    )
```

`ansatz.num_parameters` gives the trainable parameter count, useful
for matching parameter budgets against classical baselines.

---

## 4. VQC training (qiskit_machine_learning)

```python
def train_vqc(
    feature_map: QuantumCircuit,
    ansatz: QuantumCircuit,
    X_train: np.ndarray,
    y_train: np.ndarray,
    seed: int,
    maxiter: int = 200,
) -> VQC:
    algorithm_globals.random_seed = seed
    vqc = VQC(
        feature_map=feature_map,
        ansatz=ansatz,
        loss="cross_entropy",
        optimizer=COBYLA(maxiter=maxiter),
        sampler=StatevectorSampler(seed=seed),
    )
    vqc.fit(X_train, y_train)
    return vqc
```

Supported `VQC.__init__` kwargs in qiskit_machine_learning:
`feature_map`, `ansatz`, `loss`, `optimizer`, `sampler`,
`initial_point`, `callback`, `warm_start`. Other names raise
`TypeError`.

Use `VQC.fit(X, y)` and `VQC.predict(X)`. Do not write a custom
optimization loop that calls the Sampler directly inside a COBYLA
closure: `VQC.fit` already does this with correct parameter-shift
gradients and shot accounting.

---

## 5. VQE for quantum chemistry (qiskit 2.x compatible)

Build the qubit Hamiltonian from PySCF, then run a manual optimization
loop over a `StatevectorEstimator`. The classes `qiskit_algorithms.VQE`
and the `qiskit_nature.second_q.algorithms.*` submodule are not
importable in qiskit 2.x (see section 8); the pattern below uses only
the safe parts of those packages.

```python
def build_h2_hamiltonian(bond_length_angstrom: float):
    driver = PySCFDriver(
        atom=f"H 0 0 0; H 0 0 {bond_length_angstrom}",
        basis="sto3g",
        charge=0,
        spin=0,
        unit=DistanceUnit.ANGSTROM,
    )
    problem = driver.run()
    num_particles = tuple(problem.num_particles)         # (1, 1) for H2
    mapper = ParityMapper(num_particles=num_particles)   # 2-qubit reduction
    qubit_op = mapper.map(problem.hamiltonian.second_q_op())
    e_nuclear = float(problem.nuclear_repulsion_energy)
    # H2 in STO-3G with parity mapping plus 2-qubit reduction produces a
    # 2-qubit Hamiltonian (not 4-qubit).
    return qubit_op, e_nuclear


def run_vqe(qubit_op, e_nuclear, optimizer_name: str, seed: int):
    algorithm_globals.random_seed = seed
    rng = np.random.RandomState(seed)
    ansatz = build_ansatz(num_qubits=qubit_op.num_qubits, reps=2)
    initial_point = rng.normal(0.0, 0.1, ansatz.num_parameters)

    estimator = StatevectorEstimator(seed=seed)
    energy_history: list[tuple[int, float]] = []

    def energy(theta: np.ndarray) -> float:
        bound = ansatz.assign_parameters(theta)
        result = estimator.run([(bound, qubit_op)]).result()
        e = float(result[0].data.evs) + e_nuclear
        energy_history.append((len(energy_history) + 1, e))
        return e

    optimizers = {
        "spsa": SPSA(maxiter=200),
        "cobyla": COBYLA(maxiter=200, rhobeg=0.1, tol=1e-4),
        "lbfgsb": L_BFGS_B(maxiter=100, ftol=1e-6),
        "adam": ADAM(maxiter=200, lr=0.05, beta_1=0.9, beta_2=0.999),
    }
    if optimizer_name not in optimizers:
        raise ValueError(f"unknown optimizer: {optimizer_name}")
    result = optimizers[optimizer_name].minimize(energy, initial_point)
    return result, energy_history
```

The number of energy evaluations is `len(energy_history)`. Cumulative
shots equals `len(energy_history) * shots_per_eval`. For shot-budget
studies, emulate shot noise by adding Gaussian noise N(0, sigma) to
each value with sigma ≈ ||H||_1 / sqrt(shots_per_eval).

A running-mean convergence check is needed at low shot counts because
the per-evaluation energy variance can exceed the chemical-accuracy
threshold even when the optimizer has converged:

```python
from collections import deque


def cumulative_shots_to_threshold(
    energy_history: list[tuple[int, float]],
    e_target: float,
    threshold: float = 0.0016,    # 1.6 mHa
    shots_per_eval: int = 1024,
    window: int = 5,
) -> int | None:
    """Return cumulative shots at the first point where the running mean
    over `window` evaluations stays within `threshold` of `e_target` for
    `window` consecutive windows. Return None if never reached."""
    buf = deque(maxlen=window)
    streak = 0
    for eval_count, energy in energy_history:
        buf.append(energy)
        if len(buf) < window:
            continue
        if abs(sum(buf) / window - e_target) <= threshold:
            streak += 1
            if streak >= window:
                return eval_count * shots_per_eval
        else:
            streak = 0
    return None
```

---

## 6. MPS-structured circuits

A matrix product state classifier with bond dimension chi is
mathematically equivalent to a qiskit circuit with one qubit per input
feature (or pixel), a linear-chain entangling ansatz of depth
`reps = log2(chi)`, and class-label measurements as expectation values.
Running this on `AerSimulator(method="matrix_product_state")` with an
internal bond-dimension cap gives an efficient classical simulation
even at 32 to 128 qubits.

```python
def encode_features_to_circuit(x: np.ndarray, n_qubits: int) -> QuantumCircuit:
    """Per-feature embedding equivalent to phi(x) = [cos(pi*x/2), sin(pi*x/2)].
    Apply RY(pi * x_i) on qubit i so |0> maps to cos(pi*x_i/2)|0> + sin(pi*x_i/2)|1>."""
    qc = QuantumCircuit(n_qubits)
    for i in range(n_qubits):
        qc.ry(float(x[i]) * np.pi, i)
    return qc


def build_mps_ansatz(n_qubits: int, reps_for_chi: int) -> QuantumCircuit:
    """Linear-chain entangling ansatz; effective bond dimension <= 2 ** reps_for_chi.
    reps_for_chi=4 covers chi up to 16."""
    return EfficientSU2(
        num_qubits=n_qubits, reps=reps_for_chi, entanglement="linear"
    )


def mps_class_logits(
    x: np.ndarray,
    theta: np.ndarray,
    ansatz: QuantumCircuit,
    n_classes: int,
    max_bond: int = 16,
) -> np.ndarray:
    """Return one logit per class, computed via AerSimulator MPS method.

    Each class c corresponds to a Pauli observable acting on the first
    ceil(log2(n_classes)) qubits with sign pattern fixed by the bits of c."""
    import math

    n_qubits = ansatz.num_qubits
    sim = AerSimulator(
        method="matrix_product_state",
        matrix_product_state_max_bond_dimension=int(max_bond),
    )
    bound_ansatz = ansatz.assign_parameters(theta)
    qc = encode_features_to_circuit(x, n_qubits)
    qc.compose(bound_ansatz, inplace=True)

    n_label_qubits = max(1, math.ceil(math.log2(n_classes)))
    logits = []
    for c in range(n_classes):
        pauli = list("I" * n_qubits)
        for bit_idx in range(n_label_qubits):
            if (c >> bit_idx) & 1:
                pauli[bit_idx] = "Z"
        obs = SparsePauliOp.from_list([("".join(pauli[::-1]), 1.0)])
        qc_with_save = qc.copy()
        qc_with_save.save_expectation_value(obs, list(range(n_qubits)))
        result = sim.run(qc_with_save).result()
        logits.append(float(result.data(0)["expectation_value"]))
    return np.array(logits)
```

Train with parameter-shift gradients on the cross-entropy of
`softmax(logits)` against the one-hot labels.

When a manual NumPy MPS implementation is used instead, three subtle
errors are common and produce silently-degenerate models:

- Initialising tensors near the identity makes every class share the
  same logit. The classifier collapses to test accuracy = 1/n_classes
  independent of bond dimension.
- Manual bond-index bookkeeping in the contraction can leave some
  tensors disconnected from the gradient and never updated.
- The cos/sin embedding requires the factor of pi. Forgetting it gives
  a feature map that is approximately constant across inputs.

Using the qiskit-circuit form above avoids all three: the circuit
representation is unambiguous, parameter-shift gradients are correct by
construction, and `matrix_product_state_max_bond_dimension` enforces
the bond cap inside the simulator.

---

## 7. Noise model integration

The qiskit primitive samplers (`Sampler` V1 and `StatevectorSampler`
V2) do not accept a `noise_model` argument; they are noiseless by
definition. To inject noise, the noise model must live on a
`qiskit_aer.AerSimulator` backend, and the sampler then wraps that
backend via `BackendSamplerV2`:

```python
from qiskit_aer.noise import NoiseModel, depolarizing_error
from qiskit.primitives import BackendSamplerV2


def build_noisy_sampler(depolarizing_rate: float, seed: int) -> BackendSamplerV2:
    noise_model = NoiseModel()
    if depolarizing_rate > 0:
        single_qubit_error = depolarizing_error(depolarizing_rate, 1)
        noise_model.add_all_qubit_quantum_error(
            single_qubit_error, ["ry", "rz", "rx", "h"]
        )
        two_qubit_error = depolarizing_error(depolarizing_rate, 2)
        noise_model.add_all_qubit_quantum_error(two_qubit_error, ["cx"])
    backend = AerSimulator(noise_model=noise_model, seed_simulator=seed)
    return BackendSamplerV2(backend=backend)


def build_ideal_sampler(seed: int) -> StatevectorSampler:
    return StatevectorSampler(seed=seed)
```

Use it with VQC:

```python
sampler = build_noisy_sampler(depolarizing_rate=0.005, seed=seed)
vqc = VQC(
    feature_map=fm,
    ansatz=ansatz,
    sampler=sampler,
    optimizer=COBYLA(maxiter=200),
)
vqc.fit(X_train, y_train)
```

Each evaluation regime needs its own sampler instance. A model trained
on a noisy sampler at rate p_train can be evaluated on a separate
noisy sampler at a different rate p_test to probe noise robustness, or
on `build_ideal_sampler` to probe the clean-test transfer.

Do not silently swallow exceptions raised by `vqc.fit`. If training
fails at high noise rates, either let the cell fail with a documented
error or record a `training_failed=True` marker in the metrics rather
than calling `vqc.predict` on an unfitted model, which raises
`QiskitMachineLearningError: 'The model has not been fitted yet'`.

---

## 8. qiskit 2.x compatibility notes

Qiskit 2.0 removed `qiskit.primitives.Estimator` and
`qiskit.primitives.BaseEstimator` (the V1 interfaces). Two consequences:

- `from qiskit_algorithms import VQE` fails because the file imports
  `BaseEstimator`. Use a manual VQE loop with
  `qiskit.primitives.StatevectorEstimator` (V2) and the
  `qiskit_algorithms.optimizers.*` classes' `.minimize()` methods
  directly. See section 5.
- `from qiskit_nature.second_q.algorithms import GroundStateEigensolver`
  fails for the same reason. The `qiskit_nature.second_q.drivers` and
  `qiskit_nature.second_q.mappers` submodules are still safe.

Other 2.x notes:

- `transpile(circuits=list, coupling_map=single)` raises
  `TranspilerError`. Either call `transpile` per circuit or omit
  `coupling_map` (statevector backends do not need it).
- `Statevector(qc)` returns a `Statevector` object; use `.data` for
  the numpy array of amplitudes.
- `algorithm_globals.random_seed` is the global seed for SPSA and
  random ansatz initialization. Set it before each training run.

---

## 9. Common errors and fixes

| Wrong | Why | Correct |
|---|---|---|
| `Sampler(noise_model=NoiseModel())` | V1/V2 Samplers are noiseless | `BackendSamplerV2(backend=AerSimulator(noise_model=...))` |
| `from qiskit_algorithms import VQE` | imports removed V1 `BaseEstimator` | Manual loop over `StatevectorEstimator` plus `optimizer.minimize()` |
| `VQC(..., gradient=...)` | not a supported kwarg | Drop the kwarg; `VQC.fit` handles gradients internally |
| `params = pv_a.concatenate(pv_b)` | `ParameterVector` is not numpy | `params = list(pv_a) + list(pv_b)` |
| Plain `qc.rz(x[i], i)` for angle encoding | RZ on `|0>` is a global phase, has no effect | Use `ZFeatureMap(reps=1)`; H + RZ is the standard angle encoding |
| `qc.ry(x[i], i) + qc.cx(...)` labeled as amplitude encoding | This is angle encoding, not amplitude | Use `StatePreparation` over the L2-normalized, zero-padded vector |
| `scipy.optimize.minimize(...)` in VQE | requires hand-rolled shot accounting and convergence checks | `qiskit_algorithms.optimizers.{SPSA, COBYLA, L_BFGS_B, ADAM}.minimize(energy, x0)` |
| Per-step `abs(raw_energy - e_fci) <= threshold` for convergence | Per-step noise can exceed the threshold even when converged | Running mean over a window (see `cumulative_shots_to_threshold`) |
| Report `maxiter * evals_per_iter * shots_per_eval` as "shots to convergence" when not actually converged | This is the upper bound, not a measurement | Report `None` (or a documented sentinel) for non-converged runs |
| `near_identity_init` for a NumPy MPS classifier | every class logit collapses to the same value | Random initialization, or use the qiskit-circuit form (section 6) |

---

## 10. Autoclaw integration: metric logging convention

When this skill is used inside the autoclaw bench runner (stage 12 or
stage 13 sandbox), per-cell metrics should be emitted to stdout as
single lines starting with `METRIC_RESULT` followed by a JSON object.
The autoclaw sandbox parser aggregates these into `condition_summaries`
at stage 14.

```python
import json


def emit_metric_result(condition: str, dataset: str, seed: int, **metrics) -> None:
    payload = {"condition": condition, "dataset": dataset, "seed": int(seed)}
    payload.update({k: float(v) for k, v in metrics.items() if v is not None})
    print("METRIC_RESULT " + json.dumps(payload))
```

This section is specific to the autoclaw pipeline. Outside of autoclaw,
choose a metric-logging convention appropriate to the host system.
