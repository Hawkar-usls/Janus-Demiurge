# JANUS-PHYSICAL-LATE-CHOICE-010 — falsifiable physical retro-signalling gate

**Status:** CODE/SIMULATION ONLY; **physical experiment NOT performed**. This is a standalone prospective protocol, not a change to frozen OPEN-009A/B/C/D, 009E/F, QPU-005 or LIGHT-008. A significant simulated or unsigned score is never proof of retrocausality.

## Observable, prediction and physical null

In each *heralded, pre-registered* trial of an entangled-photon experiment, detector Alice records its early raw binary outcome `A` (click=1, otherwise=0 in an objectively fixed early gate). **After the early measurement**, a physically independent quantum random-number generator produces a setting `C ∈ {0,1}`, which physically selects one of two measurement bases on the **still-delayed partner photon** Bob; Bob later records `B`. Photon B is delayed sufficiently to guarantee the ordering, with both timestamp and uncertainty logged.

For the Bell state |Φ+⟩=(|00⟩+|11⟩)/√2, Alice's reduced state is ρ_A=I/2. For any standard trace-preserving operation E_C local to Bob:

ρ_A(C) = Tr_B[(I⊗E_C)(ρ_AB)] = Tr_B(ρ_AB).

More generally, **no signalling** predicts `P(A=1 | do(C=0)) = P(A=1 | do(C=1))`. Observational `P(A|C)` estimates this only if C is a valid independent intervention and conventional causal mechanisms are excluded. Entanglement correlations conditioned on B do not constitute an unconditional early signal.

A physical, late, *independent choice* matters: a precomputed seed, later-read ancilla prepared before A, future drand beacon unrelated to a physical change, or a retrospective split DOES NOT satisfy this criterion. The existing QPU-005 is not promoted by this new protocol.

## Sample size and preregistered statistics

- One locked candidate run with **N=16,384 heralded trials**, every attempted trial counted (including no-click and Bob misses).
- The first published endpoint is the raw 2×2 table of A outcomes by late C setting, without conditioning on B, coincidence detection, quantum postselection, success-only trials, environmental flags, or particular windows selected after measurement.
- The single **two-sided Fisher exact** test uses **α=0.001**. Effect `Δ=P(A=1 | C=1)-P(A=1 | C=0)`, its full table and n must be published. An unusual p-value is an **anomaly under the specified null**, NOT a sufficient causal explanation.
- The sample size and α are methodological choices, not measured physical constants. A power analysis and independent feasibility review are needed before any expensive physical hardware time; don't change sample size after observing outcomes. This pilot cannot rule out arbitrarily small signals.
- Fix the complete trial schedule and inclusion gate independently before the first physical late choice. No early stopping, replacement of failed or missing trials, unlimited runs until one passes, or retrospective retuning. If a trial or chronological record is missing, **NO SCORE**.
- B-based postselection is displayed ONLY as an explicitly secondary *false-retrocausality* control, never included in the primary statistic.
- Any confirmatory result requires a **new, independently registered cohort** and an **independent laboratory replication**, including full instrument, clock, choice-source and data provenance audits. No scientific promotion on one unusual p-value.

## Physical custody chain required; not satisfied by software

1. Experimentalist and an independent external custodian first sign the immutable protocol, source commit, optoelectronic schematic, detector calibration, fixed trial schedule, inclusion windows and physical QRNG calibration. Only later new physical target data can be accepted.
2. For **each** heralded trial, Alice's A result and physical timestamp with uncertainty must be written to an **independently audited append-only early log before C is generated**. Pre-release signed WORM/event-clock evidence must be verifiable independently from the acquisition software. Merely hashing a completed file after all settings is insufficient.
3. The external late physical QRNG produces C **after Alice has completed and committed its outcome**; report the actual photon-entropy process, entropy characterization, firmware/source hashes, setting latch and timing, without assuming that NIST statistical tests certify physical independence.
4. The setting changes Bob's real physical analyzer. Bob measurement B happens only after C. Clock offsets, drifts, uncertainty envelopes, cables, channels and photon-path delays must be measured independently. For each trial, require `t_A + u_A < t_C - u_C` and `t_C + u_C < t_B - u_B` on one *calibrated common timebase*. CSV/JSON self-reported nanoseconds alone cannot prove that timebase.
5. Isolate Alice, source, Bob, QRNG and the signing witness; audit electronic crosstalk, delayed classical communication, environmental common causes, source drift, feedforward, trial-synchronization, QRNG predictability, detector dead time, missingness and coincidence selection.
6. Randomize setting C at the stated physical time (not preset at the photon source). Preserve **all** raw early, late and Bob data, calibration traces, hardware job IDs, raw SHA-256 hashes, witness signatures, firmware/build hashes and missing/failure records.
7. Give original files and preregistration to a **second independent external analyst** who repeats the unconditional score. Only then evaluate the claim; if no trusted lab signatures, mark `EXTERNAL_DATA_UNVERIFIED` regardless of p-value.

## Data contract

The script accepts separate JSON arrays:

- `early`: one record per trial, `{"trial":0,"a":0,"t_a_ns":1000000000,"u_a_ns":100}`.
- `late`: one record per trial, `{"trial":0,"c":1,"t_c_ns":1000300000,"u_c_ns":100,"t_b_ns":1000600000,"u_b_ns":100,"choice_origin":"PHYSICAL_QRNG_GENERATED_AFTER_EARLY_MEASUREMENT","b":0}`. Missing B detector readouts may be `null` but cannot remove Alice's raw trial.
- `precommit`: `{"schema":"janus.late_choice_010.v1","protocol_version":"1","alpha":0.001,"n":16384,"primary_test":"two-sided Fisher exact conditional on A and C counts","postselection_allowed":false,"required_choice_origin":"PHYSICAL_QRNG_GENERATED_AFTER_EARLY_MEASUREMENT"}`.

These fields are declarations, **not independently verified physical provenance**. Code rejects any missing/reordered trial, wrong N, malformed outcomes or temporal uncertainty overlap, but it cannot cryptographically authenticate a laboratory or prove its QRNG physically independent. Even a clean externally supplied real dataset stays `PHYSICAL_ORIGIN_AND_CUSTODY_AUDIT_REQUIRED`; no auto-promotion or secrets access.

## Safe computational preflight

`python -m unittest discover -v -s experiments/ocean_transformer/late_choice_010 -p 'test_late_choice_010.py'`

`python experiments/ocean_transformer/late_choice_010/late_choice_010.py simulate --output-dir /tmp/janus010`

The simulation writes the early record using fsync, then generates OS random C (not physical QRNG) and a synthetic `B=A XOR C`. This **makes strong A-C correlation in the B=0 postselected subset** while the full A-C sample stays independent. It is intentionally a control illustrating how a fake backwards signal can be manufactured by conditioning on future B.

To score independently provided data later:

`python experiments/ocean_transformer/late_choice_010/late_choice_010.py assess --precommit prereg010.json --early early010.json --late late010.json --output-dir audit-output`

Any manual QPU-005 IBM credentials and hardware cost approval remain outside this workflow. An IBM 3-qubit device without a verified after-A free setting and independent physical timing does **not** satisfy the physical 010 admission criteria.

## Grounding

- Y.-H. Kim et al., *Delayed “Choice” Quantum Eraser* (PRL 84, 1; 2000): https://doi.org/10.1103/PhysRevLett.84.1
- M. Waaijer, J. van Neerven, *Delayed choice experiments: an analysis in forward time* (2024): https://doi.org/10.1007/s40509-024-00328-5
- L.K. Shalm et al., *A Strong Loophole-Free Test of Local Realism* (2015): https://doi.org/10.1103/PhysRevLett.115.250402
- NIST Statistical Test Suite: cannot *by itself* certify a physical randomness source: https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final

**Evidence threshold:** not “find any significant result” but eliminate mundane paths, preserve all trials, repeat under independent oversight, and seek confirmation on new physically independent runs. The standard quantum no-signalling theorem is a physical null, not a no-cost retrocausal channel.
