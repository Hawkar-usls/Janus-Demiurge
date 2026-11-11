# JANUS Ocean R3.1 — real model against independent historical baselines

## Why this gate exists

On 2026-11-11 a real four-river Ocean run (#43052765103) trained the existing JanusTinyTransformer on Meta Registry JSON-addition **path categories** (not article content). Its heldout score was 0.747706 over n=218, while train-majority was 0.766055 and first-order Markov was 0.770642. The model does not beat either baseline. No production checkpoint was deployed.

## Separate, cryptographically linked training pack

The R3.1 audit fetches the exact real GitHub Actions artifacts from run #43052765103 with read-only Actions permission. It validates that the snapshot comes from Hawkar-usls/janus-meta-registry, that every commit SHA and event ID is distinct, that the chronological 70/15/15 train-validation-test partitions have a 16-event context buffer, and that no R3 quarantine or quality receipts enter the chronology.

It writes a separate `ocean-r31-train-only-chronology.json` with only training target events, the exact source HEAD and original snapshot SHA; the holdout target labels remain outside this exported training pack. The original training code's frozen model receipt, checkpoint file SHA, event counts and held-out denominators are checked against exact original artifacts. No new training runs or synthetic substitute results are used.

The retrospective research evaluator records accuracy and margin against the strongest baseline. A numeric improvement of 2 percentage points would at most become a *development candidate* requiring a new prospective external assessment, not scientific admission. Because previous Ocean reporting does not include paired raw per-case predictions, statistical paired uncertainty is NOT claimed. Success on its accessible holdout cannot be called blind independent validation.

Output `ocean-r31-real-frozen-baseline-gate.json` includes full exact source and checkpoint digests, losses/wins, an unambiguous `NO_REPRODUCIBLE_BASELINE_GAIN` or provisional development-gain status, all flags `production_model_promotion=false` and `scientific_admission=HOLD`.

## Distinct scientific learning streams

Ocean's train data here is verifiable **Git history metadata** for the narrowly defined task predicting the next path category. Its scientific applicability is NONE. TACHYON's proposed new data is a different, equation-grounded physics pack in Demi_Head R3.1 (OpenStax Lorentz time dilation and IBM quantum projective measurements). Neither pack is GDELT news, external blind measurements, nor proof of time-reverse information transfer.

To demonstrate real scientific model improvement: obtain independent unseen source-family tasks and an externally committed future/holdout key, compare raw probabilities, calibration, OOD refusal, proper baselines, and all attempted trials before a candidate can be selected. Keep all failed candidates and artifact SHA proofs. Any production deployment needs a separate explicitly reviewed change.

## Runtime resources

Only one bounded GitHub Actions job (9 minutes), one read-only fetch of two previously recorded artifacts, no PyTorch or model fitting, no NAS calls, no registry writes, no changes to production model weights. Reports kept as Actions artifacts for 30 days. After reviewer acceptance, this benchmark can be run on additional frozen Ocean checkpoints via an updated pinned experimental run, not by silently changing the source.

Status: `OCEAN_R31_HISTORICAL_TRAIN_HOLDOUT_AUDIT / FROZEN_WEIGHTS / SCIENTIFIC_HOLD`.
