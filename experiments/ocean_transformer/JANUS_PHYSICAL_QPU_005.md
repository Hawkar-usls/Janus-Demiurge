# JANUS-RETRO-PHYSICAL-005 — independently hosted QPU hardware admission (not retrocausality proof)

**Status: development-only / physical QPU NOT YET EXECUTED.** The repository contains a fail-closed research protocol, offline CI, and a separately approved manual IBM Quantum provider workflow. It does not contain any recorded results from a physical quantum processor at the time of authoring. Do not relabel simulator, CPU results, drand-only timestamps, or mocked data as physical evidence.

## Why this experiment

All JANUS Ocean tests through 004 used CPUs or an independently signed **classical** future-randomness source. The actual frozen transformer got 133/256 drand bits correct, p=0.574, with Brier 0.33257 versus the uniform baseline 0.25. That does not support a useful future-information channel. An external QPU is the first step toward seeing **real quantum measurements**, not proof of retrocausality.

IBM's Open Plan offers up to 10 minutes of *QPU runtime per 28-day window*, not unlimited access. Current service documentation supports dynamic circuits with mid-circuit measurement and `if_test`, subject to each backend's capabilities.

- IBM Open Plan: https://www.ibm.com/quantum/products
- IBM dynamic circuits: https://quantum.cloud.ibm.com/docs/en/guides/execute-dynamic-circuits
- IBM Runtime API: https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/sampler-v2
- Historical delayed-choice quantum eraser: Kim et al., https://doi.org/10.1103/PhysRevLett.84.1
- Genuine causally-disconnected independent choice: Ma et al., https://doi.org/10.1073/PNAS.1213201110

## Frozen 3-qubit physical circuit

**A** and **B** start in a Bell pair. **A** is recorded first in Z. Only then is the third ancilla **C** prepared in `|+>` and measured; its 0/1 output selects the later measurement basis on B. If `C=1`, apply an H gate to B before measuring in Z, thereby measuring B effectively in X. Otherwise, B is measured in Z.

The circuit contains barriers between early A, random late-choice generation C and final B readout. The Qiskit offline CI validates the explicit `if_else` branch and instruction order. However, the QPU's **physical timing is not certified per shot** by these program barriers. IBM's backend may have hardware scheduling limitations and crosstalk; all compiled QPY bytes and the provider job ID must be archived for later timing/operation review.

**Predeclared primary test:** the raw early outcome A must not depend statistically on the later C setting. Count every shot in the full 2×2 A-versus-C table and perform one two-sided Fisher exact test. Descriptive `difference P(A=1 | C=1) - P(A=1 | C=0)` is recorded. Nominal predeclared alpha is 0.001 (strict exploratory alert, not a retrocausality verdict). A significant difference, even if observed, might be device drift, shared hardware noise, measurement crosstalk, or a programming/timing artifact. It cannot on its own imply causal influence from the future.

**Independent diagnostic controls:** for `C=0` (Z/Z measurements) Bell correlations ideally give P(A=B) near 1. For `C=1` (Z/X) correlations should be approximately random, P(A=B) near 0.5. These are *secondary* and must not be used for tuning which raw shots enter the primary test. All 4096 shots, including failures and diagnostics, are retained. If fewer than a quarter of shots occur in either setting, mark `SETTING_QUALITY_HOLD` and retain all data; never try multiple runs to hide that result.

## Source-bound and cost-controlled admission

Files:

- `experiments/ocean_transformer/physical_qpu_005_protocol.py`: immutable preregistered plan hash, exact Fisher test, 4096-shot unselected scorer, refusal to promote a physical claim.
- `experiments/ocean_transformer/physical_qpu_005_ibm.py`: actual conditional IBM Quantum circuit; no simulator fallback; cryptographically hashes the compiled QPY and records the IBM job ID, then retrieves exactly that job.
- `experiments/ocean_transformer/test_physical_qpu_005.py`: synthetic-only offline tests, strict plan, anti-tampering and no-secrets safety gates.
- `.github/workflows/janus-physical-qpu-005-ci.yml`: PR/test admission with no provider authentication or QPU usage.
- `.github/workflows/janus-physical-qpu-005-manual.yml`: manual-only single job `submit` and separate `retrieve`, no `push`, `schedule`, or automatic QPU requests.

The user must independently establish an IBM Quantum Open Plan account and put **IBM_QUANTUM_API_KEY** and **IBM_QUANTUM_OPEN_INSTANCE** in **GitHub Actions Secrets**; never paste these credentials in source files, PR text, Meta Registry, or chat. Only the user can authorize `workflow_dispatch` by checking both opt-in boxes. The code cannot verify provider billing tier solely from the secret name: the user must confirm the instance really belongs to their Open Plan to avoid unintended billing.

Submit mode creates a fixed 4096-shot single physical QPU job; it saves the plan, compiled QPY SHA and resulting job ID as a GitHub artifact. The workflow **does not automatically rerun** if a provider job remains queued or fails. Retrieve mode requires the exact original GitHub submit run ID, loads the original artifact, checks its frozen plan SHA, retrieves **the same** IBM QPU job and saves all raw shots plus analysis. A new submission must not be substituted for an unfavorable result.

## Crucial difference from an independent spacetime laboratory

IBM is a provider external to JANUS and is genuine physical hardware; **it is not a second independent human adjudicator**. C is generated later in the circuit program, but on the same processor, rather than by an independently operated distant choice station. This **does not close locality, timing, or ordinary common-cause loopholes**. A true hypothesis test of usable backwards-in-time signalling would require:

1. Two independently administered, spatially isolated photonic measurement stations; independently time-tagged early detection and a separately generated late setting, with verified light-cone separation and device clocks.
2. An unaffiliated data custodian who receives an immutable, signed early raw stream **before** the late free setting exists; the custodian must be unable to modify earlier records or filter by later outcomes.
3. One preregistered raw early-marginal endpoint with fixed sample size, blocked randomization, expected effect size, power analysis, baseline drift/calibration controls, and correction for every model/protocol variant tried.
4. A precommitted shutdown/negative-result reporting rule and independent replication at a second facility.

Quantum eraser correlations can be strong **after conditioning on later records** while no earlier unconditioned message is available. The operational claim must concern *unconditioned* earlier data that can actually be read before the later choice. A significant Fisher test from one QPU is **not** proof of time travel.

**Expected next gate:** GitHub CI PASS and merged peer-reviewable protocol; then user explicitly authorizes Open Plan quantum hardware. Unless the real IBM job ID and shot-level results exist, the honest evidence status remains `PHYSICAL_QPU_NOT_YET_RUN`.
