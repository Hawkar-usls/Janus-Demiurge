# JANUS Divergent Mind R2: HEAD-consistent public source audit

**Draft-only read-only experiment. No native runtime calls, training, repository
writeback, automated scientific claim promotion or live interhemisphere bypass.**

R2 builds on R1's six real, pinned HRAiN/iNaiHR/EYE organ file excerpts.
Instead of trusting old snapshots at run time, an optional public GitHub
reader checks three repository HEADs, retrieves **complete native JSON files
at exact commit IDs**, verifies each returned blob SHA against a locally
recomputed `git blob` hash, extracts strictly whitelisted native fields,
validates the R1 semantics and checks all three HEADs **again** before
offering question-only advisory packets. The GitHub Contents API verifies
the path at the specified commit; a blob digest alone cannot do so.

## Source drift observed before R2

At inspection on **2026-10-18 UTC**, each source repository's HEAD had moved
away from its R1 immutable snapshot:

| Public source | R1 frozen HEAD | HEAD observed 2026-10-18 |
| --- | --- | --- |
| `Hawkar-usls/Hrain` | `b0316d951adda5ced4fdfb74815aff2b31327255` | `f88fd0fb5e0ee2ef79a6e85b92f5b8462759f6b4` |
| `Hawkar-usls/iNaiHR` | `3d650f659629f869d0312a79ec3af2d2100c1145` | `bf0a352b090d88aef6ca93b1134ca8dc61da5518` |
| `Hawkar-usls/janus-meta-registry` | `f5247002d3d85539fc9c9acb946161cbddc4467a` | `31411343d37daff93055c4a25422718c18166241` |

Those are time-bound observations; they do not assert current HEAD forever.
`require_frozen` rejects any mismatch **before** downloading source blobs.
`read_fresh` may, with explicit operator opt-in, acquire a new in-memory
snapshot and revalidate all six blobs. A HEAD change during acquisition
returns `HOLD_SOURCE_HEAD_DRIFT`; no packet survives a failed gate.

## Run, intentionally and read-only

From the Janus-Demiurge repository root:

```bash
# Offline, synthetic-data tests: NO GitHub HTTP requests.
python -m unittest discover -s tests -p 'test_janus_divergent_mind*.py' -v
python -m janus_model.divergent_mind_benchmark
python -m janus_model.divergent_mind_r1_benchmark

# EXPLICIT optional public-only GET requests; never runs in PR CI.
# First command normally returns HOLD if live HEADs differ from R1 pins.
python -m janus_model.divergent_mind_r2 --policy require_frozen

# Re-pin fresh public native source state in MEMORY, not in repositories.
python -m janus_model.divergent_mind_r2 --policy read_fresh
```

Both commands print a JSON capture receipt to stdout; any non-success
returns exit code 2. They access only the public GitHub Contents and branch
API for the three allowlisted repositories and six paths, using anonymous
GETs without stored credentials. HTTP access failures are `UNKNOWN`, never
evidence of an absent problem. Digest mismatch, schema/authority change and
HEAD drift are `HOLD`, never an automatic retry with weaker checks.

Even a `READ_ONLY_QUESTIONS_READY__NOT_RUNTIME_INTEGRATION` receipt means
only a **question set**, not an intervention or discovery. The result has
`authority_delta=0`, `scientific_claim_promotion=false`,
`source_writeback=false`; all advisory items require falsifiers. The R1
head's declared archive status is not proof that an agent read that archive.

## R2 future holdout: preregistration, not a retrospective score

The machine-readable design is at
`eval/DIVERGENT_MIND_R2_HOLDOUT_CONTRACT.json`. It freezes:

1. The first **eight distinct valid commit triplets** acquired after
   **2026-10-20 00:00 UTC**, in chronological order without selecting only
   promising cases. Log abstentions and head drift separately.
2. Both arms use the **same six source files from the same checked commits**,
   with **four questions each**: native-source baseline and R1 divergent
   composition. The baseline is *not* claimed to be an equally powerful LLM.
3. Seal question text, source refs and falsifiers before human scoring.
   `seal_trial(capture, contract, nonce=...)` produces public anonymized
   `arm_a`/`arm_b` questions plus a **private** mapping and SHA-256
   commitment; `verify_reveal` later verifies both after ratings freeze.
   Keep the private mapping outside the reviewer packet.
4. An external judge, conflict-of-interest check, ratings and actual
   source-native falsification are **not yet provided or executed**.

This is **arm-label blinding only**: a knowledgeable evaluator might infer
which composition strategy generated a question from its contents. Neither
the seal nor a hash proves independent review, source truth, statistical
benefit or concealed algorithm identity. A local mock establishes only
implementation behavior, not prospective efficacy.

## What R2 actually tests

| Gate | Implemented | Scientific implication |
| --- | --- | --- |
| Exact public origin path, commit, 6 complete blob SHA checks | Yes, opt-in | Source bytes identifiable, not world truth |
| HEAD consistency before and after acquisition | Yes | Detects changes within retrieval, not future changes |
| Native schema and zero-authority validation | Yes | Unsafe/unsupported state halts without actions |
| Equal question budgets and hashed arm-label sealing | Yes | Auditable submission, not equivalent model capacity |
| Prospective unseen cases after cutoff | Protocol only | No holdout cases scored yet |
| Independent judge and source-native replay | **Pending** | Scientific gate remains **OPEN** |
| Integration into running organs or `main` | **No** | Draft-only experiment |

R2 must not merge or take effect in JANUS until separately reviewed. Passing
test automation, verifying data hashes or producing interesting questions
never closes `P_VS_NP OPEN` or authorizes causal/scientific claims.
