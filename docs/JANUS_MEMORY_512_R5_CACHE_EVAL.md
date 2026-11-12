# JANUS Memory Cortex R5 — cross-run source cache and actual native answer evaluation

**Engineering-only. No model promotion. Never label as independently blinded science.**

## What changed

R4 merged [#537](https://github.com/Hawkar-usls/Janus-Demiurge/pull/537)
and provided a read-only on-demand JSON search from Demiurge, but each
GitHub-hosted run rebuilt a 47.17-MiB eligible text SQLite FTS index.

R5 introduces a **GitHub Actions cache** that can retain the same SQLite
database across future runs for the **exact same source snapshot and index
code hash**. The normal R4 worker calls the new cache-restoring adapter.
The separate R5 CI on main creates/saves the cache only *after* source
checks and native evaluation finish successfully.

### Cache integrity

The cache key pins:
- Meta Registry source commit:
  \`c8e47bb54e954ab122e111c97198131f048bd5fd\`;
- its full-memory catalog at commit
  \`6c9259c43d89569b11351bf8579a3775025fa2f0\`;
- source index and cache adapter code hashes;
- runner OS.

On hit, JANUS reaudits the 43 catalog shards, checks all 4,712 source paths,
byte lengths and SHA-256, compares every one of 14,496 retrieved text chunks
against the pinned source contents and checks explicit typed graph edges.
It checks the SQLite digest/receipt and SQLite integrity before query.
On cold miss, it builds and verifies a new local index. A corrupt or
mismatching cache is **HOLD**, not silently trusted or promoted.

The SQLite file is stored only in the GitHub Actions cache and runner
working directories; it is **never committed or uploaded as an Actions
artifact**. Cache data is derived from the public pinned source corpus.

**GitHub Actions cache is not durable, guaranteed permanent storage**: it
may expire or be evicted, and there is no always-on process. This provides
cross-run reuse and safe rebuilding, not a 24/7 API or an archival database.
A genuinely permanent store requires a separately authorized, versioned
object/asset storage policy with retention, recovery and source permissions.

## Model answering — new source families

The fixture \`JANUS_MEMORY_512_R5_NEW_QUESTIONS_V1.json\` was committed
**before** evaluation code. Five new short questions (EDEM, EYE, Rowan/TRUMP
research, AURA and Gamarjoba public source records) target source families
outside the earlier R4 Rowan-only development QA.

For each:
1. Validate the fixture source path is in the eligible SHA-verified corpus.
2. Independently replay its exact bytes at pinned Git SHA. Match a public
   top-level scalar to the precommitted expected answer (fail if it changed).
3. Run the **real promoted native v1 checkpoint** at its original 128-byte
   context with an identical question both **without** source data and
   **with** an oracle-supplied compact correct source field/value.
4. Score deterministic greedy exact answers and mean teacher-forced target
   byte negative-log-likelihood on both inputs. Record source SHA, prompt
   bytes, raw answer SHA and separate metrics; do not score by model opinion.
5. Leave the checkpoint, model weights, train corpus and scientific holdouts
   untouched.

This evaluation measures whether the 128-byte model can use a *provided*
field/value, which is an upper-bound on actual end-to-end RAG. The evaluator
already inspected source labels, so **not independently blinded**. No
generalization, external reproducibility or independent improvement is
claimed regardless of numeric result. The data is excluded from training
and ranker tuning.

## Acceptance

- R5 synthetic cache/QA integrity guards PASS.
- Source-pinned full index restored or reconstructed, with verified
  chunk/edge equality; main branch saves a best-effort cache for next use.
- Five cross-domain prospective development questions evaluated by real
  unmodified promoted checkpoint, even if 0/5 and no NLL gain.
- Baseline and memory NLL/exact counts published; negative results preserved.
- Native v1 promoted model SHA remains
  \`fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463\`,
  context 128 bytes.
- Independent sealed QA, source governance, actual multi-source semantic
  reasoning, and 512-MiB eligible corpus remain separate open gates.

**No source JSON becomes an instruction, source link becomes an independent
scientific fact, or cached byte becomes a trained weight by this change.**
