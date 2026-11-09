# JANUS / Measurement–Retro Temporal Lens (2026-11-09)

**Evidence class:** STANDARD_QUANTUM_PREDICTIONS + SYNTHETIC_MODEL_FIT. No tachyon, physical backward communication, or objective-collapse discovery is claimed. **Owner:** experimental JANUS Ocean Transformer; All Star-inspired research adapter, not an import of the unreviewed local All Star directory.

## Exact source being interpreted

- Video: https://youtu.be/KkKMZLvlmKA (Russian transcript)
- 22:35–23:53: Wheeler/Feynman one-electron world-line story; reinterpretation of a positron as backward-time electron is a calculational representation, **not evidence of a tachyon**.
- 25:05–28:46: John Cramer's transactional interpretation; the video describes a retarded offer and advanced confirmation wave. The narrator overstates its status when claiming future detector decisions **physically send usable messages** into the past.
- Feynman, Nobel lecture (1965): https://www.nobelprize.org/prizes/physics/1965/feynman/lecture/
- Cramer, Rev. Mod. Phys. 58, 647 (1986): https://doi.org/10.1103/RevModPhys.58.647

## What provokes an observed measurement outcome?

A physical detector couples to the system. Its pointer state becomes correlated (entangled) with alternatives; interaction with the uncontrolled environment can destroy observable coherence. A measurement record is sampled according to the Born rule. A mathematical projective state update, conditioned on the observed record, is standard. An *objective*, irreversible collapse as a fundamental new dynamical process is interpretation-dependent and not established by this simulation.

For a qubit |psi> = sqrt(p0)|0> + exp(i phi)sqrt(1-p0)|1>, and a dephasing strength gamma in [0,1], this lab predicts:

- P(1|Z) = 1-p0
- P(1|X) = 1/2 - (1-gamma)sqrt(p0(1-p0))cos(phi)
- P(1|Y) = 1/2 - (1-gamma)sqrt(p0(1-p0))sin(phi)

The "which-path detector" is the dephasing channel, NOT an observer's consciousness, a retrocausal instruction, or a signal-generating switch. At gamma=1, transverse coherence is lost, and X/Y probabilities go to one-half.

A Bell-pair check applies each of I, X, Z, H locally on the future-side qubit and verifies the early-side Z and X marginals remain (1/2,1/2). Postselection using a *later disclosed* herald can change conditional distributions; it cannot be exploited to read a future freely chosen bit from a frozen early record.

## Concrete code change

- New janus_measurement_temporal_lens.py: quantum measurement oracle, Bernoulli detector model, exact no-signalling controls; trains the **existing JanusTinyTransformer** on Born probabilities for a grid of preparation parameters, environmental couplings, and measurement bases.
- Input sequence order: preparation population, phase, dephasing, **current measurement setting**. The model only predicts the outcome **at/after the setting is known**. It is not a past-output oracle for a future freely chosen detector setting.
- Output targets are *exact probabilities*, not selectively retained lucky outcomes. Unobserved setting combinations are held out by deterministic SHA-256 splitting into train/validation/test.
- A 0.5 baseline and cross-entropy/Brier-vs-exact-Born metrics are preserved even if the learned approximation loses.
- Experimental checkpoint and JSON receipt are saved only in a GitHub Actions artifact. No production checkpoint, Meta Registry current-authority record, live HRAiN memory, NAS, or other service is touched.
- No candidate is promoted to autonomous decision-making without an independent gain and external blind test.

## How to run

Standard library checks (no torch required):

    python -m unittest discover -v -s experiments/ocean_transformer -p 'test_janus_measurement_temporal_lens.py'
    python experiments/ocean_transformer/janus_measurement_temporal_lens.py --physics-only

Native experimental training (requires CPU PyTorch):

    python experiments/ocean_transformer/janus_measurement_temporal_lens.py --steps 160 --out artifacts/measurement_lens

This is a simulated quantum probability-learning task, **not** an experiment that changes or controls the quantum world through CPU predictions. The separate retro_calibrator.py, retro_channel_trial.py and existing independent-future guards remain the only research path for claims about temporally anomalous information. No passing CI is evidence of a physical retrocausal channel.

## Future falsifiable phases

1. Confirm all exact Born/decoherence and no-signalling controls; any violation invalidates the simulator.
2. Measure whether the transformer learns held-out measurement-setting probabilities better than a constant-half baseline. Retain losses.
3. Only then compare with more meaningful physical baselines and precommitted independent hardware data.
4. Register future-target bits *before* generation, externally isolate seeds and clocks, evaluate **all** attempts without post-hoc filtering. Do not confuse smoothing with forecasting.
5. Do not interpret the Wheeler-Feynman backward-in-time graphical representation as superluminal electron motion. Tachyonic dynamics would need a distinct mathematical proposal and new empirical predictions.
