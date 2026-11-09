# OPEN-CAUSALITY-009D — independently sealed negative control

**This is an optional control alongside, NOT a replacement for 009A/009B/009C.**
The main \`open_causality_009/README.md\` documents the earlier eight-cohort
NOAA forecast, frozen JanusTinyTransformer, and SUNLU glow-memory adapter.
These components and their independent 8-day calendar are unchanged.

## What 009D uniquely adds

The file \`precommit_009.json\` was committed to a public GitHub branch
**before 2026-11-12**, containing:

1. Exactly **1024 fixed-seed xorshift32 control bits** predicting all 1024
   future drand Quicknet rounds at one-minute spacing starting
   2026-11-12 00:00 UTC, from pinned chain hash and genesis.
2. Exactly **60 precomputed physical solar-geometry proxy** predictions
   for NOAA SURFRAD Bondville's 2026-11-12 16:00–16:59 UTC irradiance.
3. A complete timestamp, source/QC/missing-data protocol, no retraining,
   no retroactive change in targets, no privileged data and no selection
   of successful cases.

These forecasts are frozen **negative-control benchmarks**, not a trained
JANUS transformer, not a high-performance irradiance model and not any
physical future-to-past receiver. The earlier 009B model does actual
frozen transformer inference and verifies BLS signatures. 009D is useful
only as an extra blind control against overfitting of the other lanes.

## Data retrieval and evidence

The \`open009.py\` scorer is read-only. It checks two distinct drand
public HTTPS relays, confirms SHA256(signature) equals the transmitted
randomness and refuses to score if even one beacon is missing.
**It does NOT do the BLS pairing verification.** The signed result is
therefore status \`BLS_VERIFICATION_PENDING\`, not independently
cryptographically authenticated. A subsequent audit must use the existing
official \`drand-client@1.4.2\` verifier from 009B, against exactly these
1024 rounds, before scientific promotion.

NOAA readings come from the official historical SURFRAD archive, in
real physical W/m² with original source raw SHA-256; 60 preselected
minute rows must all exist and have QC=0. Missing or invalid values are
reported as no-score, not silently removed.

After all target releases, the new GitHub Actions workflow
\`janus-ocean-open-causality-009.yml\` has a **bounded** scheduled
reconciliation window on November 13, 16, 19 2026. Artifacts are
read-only and no automated commits, research hypothesis changes or
hardware actions occur.

## Scientific position

- A statistical outlier is **not** retrocausality proof.
- NOAA solar forecasting is classically causal.
- Neither drand nor NOAA couples an early physical measurement to a
  future free quantum choice. This is a prospective leakage-resistant
  prediction benchmark, not a physical reverse-signalling experiment.
- QPU-005, LIGHT-008, SUNLU/Glow, 009A/B/C and NAS remain unchanged.
- An external custodian must verify original GitHub
  precommit publication times **before** future targets.
- Register 009D as an append-only subsidiary record, not an amendment to
  the previously frozen main 009 preregistration.

Run offline tests without network or cloud hardware:

    python -m unittest discover -v -s experiments/ocean_transformer/open_causality_009 -p 'test_open009.py'
    python experiments/ocean_transformer/open_causality_009/open009.py validate
