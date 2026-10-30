# JANUS DADDY_KEYMASTER — Champion Release R2 (staged, fail-closed)

A **separate** native-weight promotion and rollback controller. This is a tested implementation, **not an enabled production promotion workflow**. It does not replace `janus-native-model.yml`, consume cloud GPU, start additional training jobs or change the incumbent.

## Protocol

1. Validate the original `BEST_CANDIDATE_REVIEW_ONLY` x64/ARM64 audit, its checksum, worker quorum, winning candidate SHA, source digest, and parent SHA. `INCUMBENT_RETAINED` always means HOLD.
2. In a separate evaluator, re-score the candidate and **current** incumbent against the native adaptive + frozen-anchor `promotion_gate`, then independently evaluate a **third withheld final corpus**. Require a meaningful improvement on the third corpus and passage through the original dual holdouts. Check configuration/tokenizer compatibility, source hashes and an actual short native inference.
3. Produce an admission **assessment**, not permission to publish. The blind corpus manifest carries hashes and source-binding claims. Its self-asserted flags **do not demonstrate that the data was withheld**; an independent custody authority / trusted CI must prove it was not part of training or candidate selection.
4. The separate `publish()` library building block checks exact local and remote main HEAD, SHA-matches the incumbent/candidate, stages model weights, lineage state, audit receipt, and a rollback record in **one Git commit**, then performs only an ordinary fast-forward push (`HEAD:main`). Any remote change => HOLD; no rebase, force push, or overwriting a newer model. Run only from a clean, isolated checkout, with independently authenticated issuer authorization and after rerunning assess at the actual commit.
5. `rollback_latest()` (explicit opt-in only) extracts the last known checkpoint from a prior Git ancestor, verifies its original state and SHA, creates a compensating new commit (no history rewrite) and marks the rollback receipt as CONSUMED. It fails closed on stale or repeated rollbacks.

## Important production HOLD

- The `publish` **CLI is sealed** with `CHAMPION_PUBLISH_CLI_SEALED_UNTIL_TRUSTED_BLIND_ISSUER`. This PR does not create a workflow with `contents:write`. Never trust a self-written `source_authentication` JSON field as proof of independent issuer identity; a subsequent CI adapter must externally authenticate exact GitHub run, artifact digest and protected final corpus. The Python `publish()` function is an internal building block only, not a public trusted endpoint.
- Confirm/merge or supersede the stale open checkpoint-security draft PR #301 before publishing untrusted candidate files.
- The running hourly native writer has separate authority. A production publisher must serialize against it and verify source HEAD immediately before commit.
- Downstream consumers (Corpus Callosum, Nexus and others) still need independent exact-SHA ACK and rollback verification.
- A successful held-out token-loss result alone is not proof of useful reasoning improvement.

## Read-only and synthetic tests

```bash
python -m unittest discover -s tests -p 'test_champion_release.py' -v
```

The regression suite uses a **temporary local bare Git remote**, no access to real GitHub main. Tests cover good/rejected/tampered/unproven receipts, wrong parent, history preservation, unclean and stale head refusal, refusal to publish without trusted issuer, rollback disabled by default, actual compensating fast-forward rollback and duplicate refusal. The GitHub CI job added by this PR has `contents:read` only.

## Next admission gates

- Independent encrypted/private source for a truly withheld final corpus, provenance, and contamination checks; workers must never see final labels.
- Reproducible actual-model tests for `assess()` with both a winning synthetic candidate and adversarial failures, including ZIP/tensor allocation bounds and evaluation stability.
- Trusted evaluator/issuer CI binding, candidate retention beyond short artifact expiry, canonical writer concurrency integration, reviewed promotion permissions, consumer ACK and post-promotion rollback monitoring.

**Current real decision:** calibration run `41139181887` is `INCUMBENT_RETAINED`. Nothing in this PR promotes or replaces the active checkpoint.

## R2 candidate quarantine (new, no deployment)

The existing scheduled/PR native-calibration workflow now runs the
`daddy_keymaster.quarantine` verifier **only after** the independent native
auditor. It is a narrow bytes-custody mechanism, not a new issuer:

- `INCUMBENT_RETAINED`: produces only a `NO_ACCEPTED_WINNER` local receipt,
  exports **no** candidate checkpoint. The production model is untouched.
- `BEST_CANDIDATE_REVIEW_ONLY`: checks the audit digest, exact GitHub run/
  attempt/commit, two-worker quorum, worker/training receipt checksums, source,
  evaluation-contract SHA, parent SHA, candidate SHA and size. Then copies
  `CANDIDATE.pt` into a `QUARANTINED_REVIEW_ONLY` artifact with SHA-bound
  metadata. No Git push or `contents:write` permission.
- Artifact retention is **14 days**, including exact corpus and worker artifacts,
  to permit replay. Retention is bounded; it may consume GitHub artifact storage
  quota and does not constitute durable, externally witnessed preservation.
- Any absent, expired or conflicting artifact is HOLD. The quarantine receipt
  explicitly asserts `independent_blind_final_proven:false` and
  `automatic_production_promotion:false`.

## Evidence and independent verification

- Owner-authorized Yaksa Windows: 13 CAS/audit safety tests PASS;
  one actual PyTorch training→gate→preview publish→rollback E2E PASS;
  three **real committed production incumbent** negative controls PASS;
  six quarantine receipt/bytes/replay safety tests PASS.
- Current canonical `promoted.pt` validated as SHA-256
  `fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463`
  with a normal `weights_only=True` load, forward loss and short inference.
  A candidate with identical bytes is explicitly rejected.
- The local isolated trained checkpoint improved synthetic losses on three
  held-out *fixture* sets, and the prior R2 version passed on Linux x64 and ARM64.
  This is engineering verification, NOT a production champion result.
- The release preview itself now rejects all non-local Git remotes
  (`CHAMPION_REAL_REMOTE_PUBLISH_FORBIDDEN`) even if an untrusted caller
  self-labels its report `TRUSTED_WORKFLOW_VERIFIED`.

**True production admission remains blocked** until: independent *prospective*
blind final material under separate custody; contamination audit against the
canonical corpus, historical weights and replayed experiments; trusted identity
and artifact verification in a least-privileged issuer; secure checkpoint
deserialization (PR #301 reconciliation); actual nonregressing candidate
measured against the current canonical checkpoint; current-head CAS; and
consumer ACK/rollback supervision. Do not interpret any synthetic or rehearsal
receipt as authority to promote.

## Quarantined real candidate B and two-architecture replay

A genuine owner-local bounded candidate, checkpoint SHA
`e89352cf649c67d8fb88e9cb6b929897460fd99e0d5bcd29e6c096b4ff39a321`,
is stored in public research-only branch
`janus/champion-r2-quarantine-20261031`, immutable commit
`1ae68da4ab52e79d8a3788426939f3c7807427ca`.
It derives from the original canonical parent
`fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463`;
the original adaptive and frozen-anchor gate passed, and an independently
chosen technical RFC test improved for five preregistered evaluation seeds.
Trial A was rejected; candidate B was retained **in quarantine, not main**.

The PR safety job now reads that exact Git commit and SHA-pinned
`candidate.pt` on Linux x64 and ARM64, verifies original training receipt,
reruns frozen-anchor and RFC 9113 comparisons with a CPU-only PyTorch loader,
and uploads a **research-only** read-only receipt. It never promotes
weights or grants review/report fields deployment authority.

This is independent **cloud execution and byte identity**, not an
independently escrowed blind test. The precise adaptive corpus is not
replayed in that job; promotion still requires external data custody,
a genuinely independent source/split leakage audit, source and issuer
authentication, secure checkpoint loader PR #301 review, consumer ACK
and an authenticated CAS promotion workflow.
