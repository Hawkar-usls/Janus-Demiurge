# ESSENCE v1.7 — real JANUS model change, evidence admission only

This is the next step after v1.6.3–v1.6.6 demonstrated bounded
development-only native CPU INT8 adaptation, prospective public-source tests,
conservative reliability **HOLD**, and simulated in-process shadow fallback.

**Purpose:** define exactly what real evidence a human reviewer must receive
before considering changing the working JANUS GPT checkpoint. The checker
never installs a model, swaps weights, deploys a service, merges a PR or
grants production authority.

## Missing prerequisites — all currently HOLD

1. **Independent, closed, training-disjoint source.** An externally controlled
   custodian keeps the evaluation text out of JANUS repositories and source
   training. Two cohorts with at least 100 independently sourced documents
   each must be evaluated once against the fixed, SHA-256-bound original
   `promoted.pt` and mask-7 native INT8 candidate. The verifier accepts
   anonymized per-document hashes, token counts, original/candidate
   cross-entropy and Top-1 agreement; it resamples at **whole-document**
   level for a 1,000-iteration lower confidence bound. On each cohort,
   the lower bound must reach 97% and **token-weighted corpus cross-entropy**
   regression stay within 0.5%. Weighting by token count prevents many short
   documents from hiding a substantial regression on long documents. A statement that data are unseen must be independently
   attested: document hashes cannot prove this alone.
2. **Real target hardware.** A designated device with the same runtime and
   compute architecture as the intended model service must supply at least
   five *separately identified* measurement runs from independent processes,
   each with median and P95 CPU forward time and process RSS, source profile
   digests, and the exact candidate artifact SHA. On each paired run, median
   slowdown must not exceed 5%, P95 slowdown 10%, RSS rise 5%. Serialized
   model state must save at least 25%. These are provisional engineering
   thresholds for this candidate, not proof of application-level impact.
3. **Genuine deployed canary and rollback.** A real service identifier and
   the actual target device ID must be recorded. The release operator must
   independently attest the baseline model revision, the deployed canary
   artifact, at least 100 actual canary requests, a deliberate rollback
   on that real service, restored baseline checkpoint SHA, genuine
   monitoring and response hashes. The v1.6.6 GitHub shadow experiment
   *cannot* be substituted for this proof.

## Independent cryptographic assurance

Four roles sign their scoped canonical JSON evidence with separate external
Ed25519 SSH keys: `holdout_custodian`, `external_evaluator`,
`target_hardware_operator`, `deployment_operator`. The owner must
establish and provide their trusted public-key pins **out of band**, not
from files supplied by the candidate or a public PR. Keys/closed datasets
must not be committed into JANUS or uploaded as CI artifacts.

Each attestation body is canonical UTF-8 JSON with:
`schema=janus.essence.real_model_role_attestation/1.7`,
`role`, `candidate_id=native_dynamic_int8_ffn_mask7`,
`candidate_sha256` (canonical digest of the complete locked candidate
manifest), `payload_sha256` (of the signed role-specific evidence),
`signed_at_utc`, and
`scope=INDEPENDENT_REVIEW_NO_MODEL_DISPATCH`.
Sign it using `ssh-keygen -Y sign` under namespace
`janus-essence-v17-external-review`. The verifier independently
checks each signature using `ssh-keygen -Y verify` against out-of-band
pinned trust roots and requires distinct keys and different organizations
for custodian and evaluator. Identical signing keys cannot be counted
twice. Even valid signatures **only** establish possession of the keys
and a signed claim; scientific independence and signer authorization
still need manual confirmation.

## How to run

The ordinary CI job **intentionally** does not provide external evidence
or trust roots:

`python tools/essence_v17_three_gate_review.py --out runtime/essence_v17/admission.json`

It must produce:
`HOLD_INDEPENDENT_BLIND_TARGET_HARDWARE_AND_REAL_SERVICE_ROLLBACK`,
`production_authority=false`, `automatic_promotion=false`.

An authorized operator can separately perform an offline *read-only* review,
after obtaining genuine documents and externally authenticated owner trust
pins:

`python tools/essence_v17_three_gate_review.py --evidence /secure/review.json --owner-trust-file /secure/pins.json --out /secure/review_result.json`

The final favorable result is only
`REVIEW_EVIDENCE_CRYPTO_VERIFIED_OWNER_APPROVAL_STILL_REQUIRED`.
It **never** grants production authority. A separate human-approved,
versioned model-change PR and operational protections remain mandatory.

The unit suite constructs synthetic data and ephemeral keys **solely to test
the verifier**; these are not actual independent evaluators, measurements
or live-service proofs. No NAS, external service mutation or hidden
production key is used in CI.

## v1.7.1 anti-replay hardening

All four external attestation bodies are additionally bound to the
canonical SHA-256 of the entire candidate manifest. A valid, already signed
holdout or device receipt cannot be transplanted onto a different model
commit, candidate checkpoint, or selected layer mask. This is an additional
negative-control requirement; older unsigned/non-cryptographically valid
receipts are not promoted. The ordinary GitHub CI still lacks genuine
out-of-band owner trust pins and must remain HOLD.
