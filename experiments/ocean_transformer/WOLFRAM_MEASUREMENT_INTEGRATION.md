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

## Rowan-style Ocean/Wolfram council (additional integration)

`ocean_wolfram_council.py` consumes **the exact emitted** measurement-priors
JSON, a bound Wolfram arithmetic verification receipt, and, when present,
the native `JanusTinyTransformer` benchmark JSON. It is run in the same
GitHub Actions job **after** training, then writes
`artifacts/ocean_wolfram_council.json` with source hashes, comparative
synthetic Brier gain, science status, and explicit non-promotion restrictions.
Each class of input is separately checked; a missing or tampered source
fails closed instead of being treated as a successful provider result.

The workflow provides two equivalent-to-Rowan boundaries:
- **Offline**: all calculations and tests run directly on GitHub CPU.
  The council reports `OFFLINE_MATH_ONLY`, not external verification.
- **Live, opt-in only**: after `WOLFRAM_ALPHA_APPID` is configured as a GitHub
  Actions secret and `live_wolfram=true` is selected manually, exactly four
  fixed public expressions can be independently checked. The science council
  sees only the verification flags and never raw Wolfram output.

No Wolfram provider content is persisted: the API terms prohibit result
caching without separate written authorization. The audit receipt records
our own formula, our expected scalar and a pass/fail check, not Wolfram's
textual or numerical results.

This is not an autonomous paid research agent and cannot reprogram JANUS's
production model. Even if the native Ocean benchmark improves, the gain is
only learning a synthetic Born-rule dataset, and no physical result is implied.
