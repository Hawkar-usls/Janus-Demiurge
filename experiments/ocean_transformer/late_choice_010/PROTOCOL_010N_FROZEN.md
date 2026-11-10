JANUS-010N FROZEN PREDICTION BEFORE OPENING NEW ORIGINAL FILES
Freeze date: 2026-11-10

Independent archival source: Rosenfeld et al. event-ready entangled atoms Bell test, PRL 119 010402 (2017), newly archived on Zenodo 2026-09-24 at https://zenodo.org/records/22936124, DOI 10.5281/zenodo.22936124.

SOURCE DESIGN PRECOMMITTED FROM PUBLIC FILE LISTING, NOT CONTENT:
- Calibration source: Bell_2016-04-15.zip, authoritative Zenodo MD5 53544819317d4dcfbe5c63e039a8aa38.
- Frozen entirely separate test source: Bell_2016-06-14.zip, authoritative Zenodo MD5 030ce1a0c6c6cc7f1107e1cd608cce77.
- Do not inspect the June raw outcomes before freezing script, model definitions and test criteria.
- This is a previously published historic physical experiment, not a new prospective physics run. Cross-lab source independence from JANUS-010M ETH is strong; absolute guarantee of previous non-exposure is impossible.

FROZEN STANDARD PREDICTION:
- For unconditional complete event-ready trials, Alice at fixed own setting should have no dependence on Bob remote setting, and likewise Bob at fixed own setting should have no dependence on Alice remote setting, under standard quantum assumptions and proper lab independence/no communication.
- M0: local Bernoulli probability conditioned on own setting only.
- Mjanus: local Bernoulli probability conditioned on own and remote setting, a statistical alternative, not a physically late free setting.
- Mpost: conditioning on OTHER wing outcome may create strong apparent correlations, displayed only as an exploratory false-retro control, never a primary result.
- Conjectured generalization: Mjanus does not have reproducible material advantage over M0; prediction may be falsified on the entire June file. Never tune models based on June. Target effect for exploratory sensitivity |delta|=0.01 is a planning choice, not a measured value.

PREDECLARED REPLAY IF THE ORIGINAL SOURCE HAS COMPLETE EVENT-READY TRIALS:
- Respect original raw README as semantic source, not outcome-selected schema interpretations.
- Include all event-ready trials and no-click events, never select detections or coincident-only successes for primary no-signalling.
- Treat April 15 as ONLY calibration and June 14 as ONLY untouched within-program source validation.
- Use fixed Jeffreys Beta(1/2,1/2) smoothing for both M0 and Mjanus and score June full record log likelihood; report Mjanus minus M0 predictive bits/event separately for Alice and Bob (do not choose best wing).
- Four predeclared local-by-remote comparisons on June (Alice own settings 0,1 and Bob own settings 0,1): pooled z test and Holm familywise alpha 0.001. This is approximate and assumes sufficient independent trials.
- All failures, sample sizes, unknown channels, bad hashes, incompatible source runs, missing timing or missing no-click events must be reported. Do not substitute other data if either run fails compatibility.
- If original source has only selected coincidence counts or postselected outcome tables, report INELIGIBLE_PRIMARY_DATA_ONLY, without a physical no-signalling claim.
- Work in separate draft PR, preserve sha256 for all original source files and append-only registry evidence; no changes to sealed JANUS physical-010 or NAS.

PHYSICAL-LATE-CHOICE SEPARATE GATE:
- Original 2016 atom Bell experiment is not a physically late independent choice after independently signed earlier Alice readout unless original source explicitly verifies that ordering.
- Physical retrodirectional signalling requires a NEW experiment with early A committed before late QRNG setting C generated, independent clock timebase/cable delays, no postselection and outside laboratory replication.
- The available 2016 historical dataset cannot prove retrocausal transmission even if one marginal contrast is significant.
