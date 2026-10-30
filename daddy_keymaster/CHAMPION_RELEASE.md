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
