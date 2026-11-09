# JANUS Ocean / Prospectively frozen transformer vs independent future randomness · 004

**Research state:** development-only, exactly one prospective software forecasting trial. This is not an experiment demonstrating physical retrocausality. No production weights change.

## What's new and genuinely different from 003

JANUS-ZENO-TEMPORAL-003 compared **OS-random early bits** against a future signed drand Quicknet beacon; 132/256 were equal (p=0.662), consistent with chance. That run tested the timing protocol, not the neural model.

This new experiment runs the ACTUAL previously trained `JanusTinyTransformer` (the existing model in `janus_model/model.py`). The checkpoint is pinned to the historical GitHub Actions run **42596763409**, artifact **13663149173**, archive digest `sha256:45c8b063b08973b06b88ec843e9a5d16976c983a8e35b39ef33e9304201e5515`. Its embedded `report.json` SHA is checked against the exact safe-loaded model checkpoint (`torch.load(..., weights_only=True)`).

That checkpoint was trained only on synthetic Born-rule measurements and not on future drand labels. This is **cross-domain exploratory transfer**, not a retrocausal mechanism or a new retrocausal-trained network. It has no demonstrated route to information about independently generated future entropy. Under ordinary physics, forecast performance should be near the uniform 50% chance baseline.

## Prospectively frozen protocol

1. **Before future drand release:** Install CPU Torch and cryptographically verified drand-client; download and verify the exact historical trained-model artifact. Fetch an already published signed Quicknet round. Predeclare the target **80 rounds** later (about 240 seconds).
2. **Actual model inference:** For every 256 target bit positions, build deterministic public feature tokens from only the target round and position. No future beacon bytes, early/later labels or drand output enter the input. Run the frozen transformer in `eval()` with gradients disabled. Record 256 `P(bit=1)` probabilities, 256 thresholded predictions, the original checkpoint SHA, the target round, its release timestamp, and an SHA256 precommit.
3. **External early timing:** Upload the entire JSON into a GitHub Actions artifact. A later independent runner reads GitHub's own `created_at` and must confirm the artifact was published **at least 30 seconds before** the target release.
4. **Independent late source:** Only after target release, fetch precisely the committed drand Quicknet round using the pinned official `drand-client@1.4.2` and BLS signature verification. Check its chain hash and predeclared round.
5. **Predeclared scoring:** Score ALL 256 bits without postselection. Primary metric: **Brier score** relative to the uniform probability-0.5 baseline (0.25). Secondary diagnostic: thresholded binary match accuracy with exact two-sided binomial probability under independent fair bits. Also report log loss and predicted-one fraction. Retain the full negative or positive result.

An isolated branch-only GitHub workflow performs ONE such trial; there is no `schedule`, no `workflow_dispatch` and no recurring external query. If model checkpoint retrieval or a security gate fails, the run must fail closed rather than fabricate a result. A failure **after** a valid early precommit cannot be discarded as though no trial occurred. It needs an explicit failure record in Meta Registry and no rerun of the same target.

**Interpretation:** Brier improvement or a chance-level p-value in a single trial cannot prove signals from the future. If there were a repeatable anomaly, the next stage would require advance registered sample size/power and frozen pipeline, independent external custodian of model forecast and time, independently administered physical receiver/late free choice, audit for ordinary information leakage, and replication outside JANUS. A classical transformer and drand beacon are not in themselves quantum hardware.

## Reference run and files

- Forecast and scoring logic: `experiments/ocean_transformer/ocean_future_model_prediction.py`
- No-network protocol tests: `test_ocean_future_model_prediction.py`
- One-shot workflow: `.github/workflows/janus-ocean-future-model-004-one-shot.yml`
- CI: `.github/workflows/janus-ocean-future-model-004-ci.yml`
- Source frozen model: [historical JANUS training run #42596763409](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/42596763409)
- Previous genuine future randomness negative control: [run #42629539750](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/42629539750)
- Independent late randomness: [drand Quicknet](https://docs.drand.love/developer/http-api/)

**No evidence status should be promoted to physical retrocausality because of software scores alone.**
