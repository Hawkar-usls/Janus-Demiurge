# ESSENCE v1.0 — real-model admission: policy and scientific boundary

This is a **read-only eligibility verifier** for potential future JANUS model updates, not a deployer.

The same candidate must demonstrate >5 percentage points absolute paired accuracy improvement on **both** post-freeze v0.7 cohorts (>=60 distinct tasks/cohort; exact one-sided McNemar p <= .005/cohort; no false rejection of healthy WAL). Candidate SHA, baseline, result SHA, raw-source SHA, canary and proven rollback must be bound. Two different **out-of-band provisioned** OpenSSH Ed25519 public identities must sign exactly the evaluation and safety context: source custodian and external model reviewer. Keys embedded by a candidate are not trusted. Source correctness and scientific independence require additional human evaluation.

Signing with two test keys under one owner DOES NOT establish independent scientific review. Even when crypto checks pass, this module returns only `CRYPTO_REVIEW_COMPLETE_OWNER_APPROVAL_STILL_REQUIRED`, never production authority or an activation action. In particular, a synthetic unit-test pass does not count as prospective evidence.

Separate downstream gates are mandatory before any real model change: independent access audit, source-license/privacy check, blinded new real-data confirmation, explicit owner's review/approval via protected PR, existing `janus_model/checkpoint_admission.py` bounded SHA preflight and safe weights-only checkpoint loader, bounded canary with regression guard, immutable rollback checkpoint, rollback exercise and release monitoring. The existing promoted checkpoint path and `JANUS_MODEL_STATE.json` are intentionally unchanged. Legacy untrusted `pickle` models are never loaded.

The currently validated result remains **HOLD**: external signers haven't been provisioned and post-freeze cohort measurements are not yet available. This implementation is not authority to enable automatic GitHub writes, self-merges, auto-promotion or 24/7 self-learning.
