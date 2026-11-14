# ESSENCE v1.6.6 — read-only shadow and injected-fault fallback

The candidate is the real native PyTorch dynamic CPU INT8 model obtained
by quantizing only three of the four JANUS-GPT FFN Linear layers in the
checkpoint. Its selection/quality measurements are recorded in Meta
Registry v1.6.3–v1.6.5, but the conservative v1.6.5 reliability gate still
returns **HOLD** due inadequate statistically robust agreement and missing
external blind testing.

This module loads the **original, committed** SHA-256-pinned JANUS GPT
checkpoint and builds a disposable, shadow-only INT8 model. In GitHub
Actions it executes paired real model forward passes, observes Top-1
agreement and deliberately injects a corrupted candidate logit stream.
The fail-closed route always returns exact FP32 baseline logits and
records both ordinary shadow and injected-fault decisions, with tests
that reject forged model-swap permission or invalid safe baselines.

This **does not** connect to the actual JANUS service, alter a deployment,
swap a checkpoint, perform real operational rollback, or grant a
production promotion. It is an isolated research test of the fallback
decision path. An independently managed, external blind holdout,
hardware-matched memory measurement, service canary, true rollback and
authenticated human-reviewed authorization are all still required
before any working model may be changed.

All source identity, Meta Registry evidence Git blob SHA and proof
SHA-256 are preserved. PR CI is read-only, with no schedule, NAS,
secret access, model write or recurring unnecessary runner cost.
