# JANUS PNP evidence — durable, append-only Meta Registry importer

This importer is a non-authoritative scientific **observation archive**. It
takes the latest `janus.pnp_autoresearch_context.v1` from the exact live
`Janus-Demiurge/main` commit and archives a source-checked content summary.

## What it really verifies

1. Download the existing supervisor context as immutable public Git bytes
   at the freshly observed Demiurge HEAD.
2. Recompute `context_sha256` and `bundle_sha256` from canonical JSON,
   require the supervisor and all candidate routes to retain `BLOCKED`.
3. Re-read Fundamentum's research status and TOPA's specific Policy-0A
   refutation report by the immutable source commits in the context; require
   exact SHA-256 match against the original bytes.
4. Re-read Beetle's context and processing ACK at the recorded
   `beetle-memory` SHA and compare the hash, processing cursor and receipt
   pointer. Do not treat Beetle discoveries as independent science.
5. Write a new immutable `records/<context_sha256>.json`, append one
   journal entry to `HISTORY.jsonl` and atomically update `LATEST.json`
   in the same Git commit. If an identical scientific context was already
   archived at another Demiurge commit, skip it.
6. A source hash, missing evidence, changed scope, claimed proof status or
   already-used key with different scientific payload is a **HOLD**, not a
   second history record.

The scheduled workflow runs every two hours at UTC minute 58, after the
normal Demiurge PNP cycle at minute 37; GitHub Actions may delay/skip runs.
A trusted, single-writer Meta Registry job alone has `contents: write`.
Validation is read-only. GitHub's Git commit history preserves the complete
sequence of archive revisions.

## Scientific and security boundary

- `P_VS_NP = OPEN`. No bridge action permits theorem promotion.
- A numerical pass on n=3, citation, metadata or source hash is not a
  universal proof, original research reproduction or model learning.
- Other repo source code is **never executed** by this importer.
- It never reads private repositories or sends credentials to raw content.
- It archives provenance and reported findings, not arbitrary model instructions.
- It does not overwrite past receipt records; Git commit rebase conflicts
  terminate rather than force-push.
- The archived content evidence reflects **the last completed source-bound
  supervisor run**, and does not independently verify that every external
  theorem or Beetle link is true.

All new source validations and append-only invariant tests are in
`tests/test_pnp_evidence_importer.py`.
