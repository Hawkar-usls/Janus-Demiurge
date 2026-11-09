# JANUS Ocean / Wolfram|Alpha / quantum measurement research lane

**Scope:** development-only, isolated from JANUS production, Rowan budgets and
historical proof claims. Source of truth is the existing
`experiments/ocean_transformer/` implementation of `JanusTinyTransformer`.

## Why this exists

Source video: https://www.youtube.com/watch?v=KkKMZLvlmKA&t=1505s
(25:05–28:46 discusses transactional interpretation, measurement and the
two-slit experiment). The video is a **discussion of interpretations**, not
experimental verification of signalling to the past.

A physical which-path detector can entangle with a quantum system; an unread
detector can suppress interference (decoherence). A registered projective
measurement has a stochastic result with probabilities predicted by the Born
rule. This does not require a conscious observer, and it does **not** let
the experimenter select the outcome or read a freely chosen future message.

This module makes three separately falsifiable and provenance-bound objects:

1. `measurement_priors.py` — exact two-dimensional density matrices for
   `|psi> = cos(theta)|0> + sin(theta)|1>`, optional unread Z-dephasing
   `rho -> (1-q)rho + q sum_z P_z rho P_z`, and a final Z or X measurement.
   X outcome 1 means `|->`, Z outcome 1 means `|1>`. It also imports the
   **existing** JANUS Bell no-signalling test.
2. `ocean_quantum_train.py` — uses the native `JanusTinyTransformer`
   on samples generated from these Born probabilities. The resulting
   checkpoint is a *research candidate* only. It is not trained on
   independent future randomness and provides no evidence of retrocausality.
   The calibrated analytical Born oracle is a non-neural baseline; no
   post-hoc holdout fitting is permitted.
3. `wolfram_alpha_bridge.py` — bounded **read-only** four-query calculator
   using the official Wolfram|Alpha Full Results API JSON endpoint
   (https://products.wolframalpha.com/api/documentation/). Its public
   arithmetic results can cross-check numeric constants, not certify
   physical theories or retrocausal communication.

## How to run

Run free deterministic checks:

```sh
python -m unittest discover -v -s experiments/ocean_transformer -p 'test_measurement_wolfram_bridge.py'
python experiments/ocean_transformer/measurement_priors.py --output /tmp/janus_measurement_priors.json
python experiments/ocean_transformer/wolfram_alpha_bridge.py --mode offline --output /tmp/janus_wolfram_offline.json
```

Optional local research training (requires PyTorch):

```sh
python experiments/ocean_transformer/ocean_quantum_train.py --steps 160 --batch 128 --output /tmp/janus_ocean_measurement_candidate
```

In GitHub Actions open **JANUS Ocean / Wolfram Alpha Measurement Research**
and use **Run workflow**. Offline tests run without access to credentials.
For live arithmetic checking, obtain a Wolfram|Alpha Developer AppID,
register it as repository Actions secret `WOLFRAM_ALPHA_APPID`, and set
`live_wolfram=true` explicitly. Exactly four fixed public computations are
queried; no open-ended third-party prompts or future outcome data are sent.
API access, quotas and any cost remain subject to the user's Wolfram plan.
For bounded experimental training select `train_ocean=true`.

The API secret is never printed or written to artifacts; transport failure is
replaced by a fixed error code. A URL containing credentials is never put in
the evidence report. The network mode is never enabled on pull requests.

## Verified mathematical receipt → Ocean model evidence

The canonical Wolfram adapter now exposes `verify_live_math_receipt()`. It checks
the exact fixed-query IDs, expression strings, numerical answers, prior-grid hash,
provider-mode indicator, and absence of promotion or retrocausal claims.

When both `live_wolfram=true` and `train_ocean=true` are explicitly selected,
the workflow passes `artifacts/wolfram_live.json` to
`ocean_quantum_train.py --wolfram-receipt ...`. The research report then
contains a SHA-256 binding to that exact JSON and a
`LIVE_MATH_RECEIPT_VALIDATED_RESEARCH_ONLY` label. No samples or target bits
are sourced from Wolfram; the mathematical receipt is **not part of training
labels**, and the provider does not cryptographically sign it.

Offline runs record `wolfram_advisory_receipt.status=NOT_PROVIDED`. A mocked
or offline receipt is explicitly refused at the training intake boundary.

This avoids maintaining a second Wolfram adapter alongside the canonical
`wolfram_alpha_bridge.py`, and reuses the existing Rowan-style read-only gate.

## Rowan-like boundary

This design borrows the important **research-governance** property of the
existing `tools/rowan_research_council.py`:
independent outside input is *read-only*, tied to known source
formulas/checksums, and must not promote scientific/production authority.
It neither invokes Rowan nor changes Rowan allocation/scheduling.

### Scientific boundaries

- Nonselective decoherence (loss of an off-diagonal density-matrix element)
  is not the same as proving an ontic collapse mechanism.
- An observer can induce detector interaction, but cannot force a chosen
  random quantum result by deciding to look.
- A backwards-in-time Feynman diagram interpretation is not a tachyon.
- Late conditioning/postselection changes selected distributions, not
  already available raw earlier records.
- Wolfram arithmetic agrees with physics *equations* by construction; it
  cannot independently confirm an exotic physical channel.
- Empirical retrocausality requires preregistered, independently anchored
  early data, late free target selection, side-channel isolation and an
  independent external replication.
- If the research benchmark improves, its gain is **synthetic statistical
  learning only**; production weights stay unchanged.
