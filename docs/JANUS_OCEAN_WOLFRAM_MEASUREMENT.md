# JANUS Ocean × Wolfram|Alpha — scientific mathematical source (research only)

**Status:** review branch; offline tests available immediately. A live provider connection needs the repository owner's Wolfram|Alpha AppID and explicit workflow dispatch. No production model or Retro Lab checkpoint is changed by this proposal.

## Purpose and lineage

The original Rowan bridge in `Hawkar-usls/Janus_Genesis/.janus/ROWAN_RESEARCH_SOURCE_LINK.json` is a **read-only reference and evidence gate**, not authority to spend provider credits, mutate model weights, or promote scientific claims. The Ocean Wolfram source follows the same separation:

1. Offline physics fixtures and unit tests (no provider traffic).
2. Optional, explicitly opted-in Wolfram|Alpha Full Results JSON queries.
3. Bounded strict numeric checks of six public predeclared mathematical identities.
4. A SHA-256-linked advisory receipt attached to a research-only training run of the **existing** `janus_model.model.JanusTinyTransformer`, not to any production weights.
5. Standard holdout scores and no-signalling control. No postselection-assisted claims about an accessible earlier signal.

The official Full Results API is documented at https://products.wolframalpha.com/api/documentation/ and uses an application AppID. The user must create an appropriate provider application and comply with provider terms.

## What is verified

- `cos(pi/4)^2=1/2` and `sin(pi/4)^2=1/2`: Born measurement probabilities of a balanced state.
- `cos(pi/4)^2+sin(pi/4)^2=1`: norm preservation.
- Partial dephasing and phase-basis calculation each give `1/4` for the listed inputs.
- An eight-Bell-pair postselection toy has theoretical acceptance `1/256`. **This is a conditional event, never an early usable byte.**

The learner's actual training labels remain reproducible locally and are evaluated on a disjoint settings-level holdout. Wolfram is a finite mathematical cross-check, not a stream of unknown future physical outcomes. No model-generated arbitrary queries are sent.

## How to enable live Wolfram|Alpha

1. Obtain an AppID using https://developer.wolframalpha.com/portal/myapps/ (provider account required).
2. In the **Janus-Demiurge** GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**. Set the name to **`WOLFRAM_ALPHA_APPID`** and supply your AppID. Never commit or paste the AppID into issues, logs, prompts, artifacts or source files.
3. After reviewing/merging the research PR, open Actions → **JANUS Ocean / Wolfram Alpha Read-Only Measurement Lens** → Run workflow. Enable `live_wolfram=true` to make **at most six fixed requests**; enable `train_experimental=true` to train a sandbox model.
4. Inspect the Action artifacts `live_math_receipt.json`, `measurement_lens_report.json`, and the checksum-bound **experimental** checkpoint. If any provider response is unavailable, unexpected, or numerically inconsistent, the live job **fails closed**.

Provider credentials are not currently provisioned by this code. No request is made by pull-request checks, automatic push checks, or by default offline dispatch. The provider's returned JSON is checked and hashed, but is **not cryptographically signed** by Wolfram|Alpha and does not establish provider-authenticated physical data.

## Local development

```bash
python -m unittest discover -v -s experiments/ocean_transformer -p 'test_wolfram_ocean_bridge.py'
python -m unittest discover -v -s experiments/ocean_transformer -p 'test_janus_measurement_temporal_lens.py'
python experiments/ocean_transformer/wolfram_ocean_bridge.py --out artifacts/wolfram/offline.json
python experiments/ocean_transformer/janus_measurement_temporal_lens.py --physics-only
# Requires torch. Isolated from janus_model production:
python experiments/ocean_transformer/janus_measurement_temporal_lens.py --steps 160 --out artifacts/wolfram/research
```

## Scientific boundary

- An apparatus that records a measurement can produce a definite measurement outcome and entangle with the quantum system; it does not require a conscious observer.
- An interaction that distinguishes paths decreases interference (decoherence). Projection is a **conditional probability update**; the existence and nature of objective wavefunction collapse remain interpretation-dependent.
- Wheeler–Feynman time-reversal diagrams and Cramer's transactional picture are interpretational descriptions; neither implies that measured electrons have spacelike/tachyonic dispersion.
- The late-gate Bell controls reproduce \(P(A|X_{\text{late}})=P(A)\). Late herald conditioning may give correlations without a usable future-to-past message.
- All measured mathematical verification and model accuracy results are independent of a physical future-random-bit experiment. For actual retrocausality, use JANUS's precommitted external-future / causal-isolation protocols and require independent, no-leakage evidence.

The read-only source contract is `.janus/WOLFRAM_OCEAN_MATH_SOURCE_LINK.json`. GitHub workflow permissions are `contents: read` and there is **no automatic promotion**.
