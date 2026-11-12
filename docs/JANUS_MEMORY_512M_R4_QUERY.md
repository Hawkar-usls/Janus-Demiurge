# JANUS Memory Cortex R4 — controlled query from Demiurge

Status: **read-only source retrieval / visible development QA / not model training**.

## Why this exists

R3 [PR #536](https://github.com/Hawkar-usls/Janus-Demiurge/pull/536)
validated 43/43 full HRain/Meta Registry metadata shards, **4,712 unique
structurally eligible text objects**, **49,460,266 verified source bytes**
(≈47.17 MiB), and 14,496 source chunks. The original R3 FTS index was a
runner-local temporary file; it was not yet part of the standard
Demiurge memory-read route.

The R4 reusable workflow
\`.github/workflows/janus-memory-512m-r4-query.yml\` provides a **stable
GitHub Actions entrypoint** via \`workflow_dispatch\` and \`workflow_call\`.
The existing \`demiurge-unified-memory-v2-query.yml\` now invokes this R4
read-only worker *after* its previous v2 reader succeeds.

The R4 worker:
1. Reconstructs a SQLite FTS5 index from the same pinned public
   Meta Registry source and HRain catalog commits, after verifying raw source
   SHA, encoding, JSON validity, deduplication and exclusion policy.
2. Exposes bounded public text-search queries, returning **source paths,
   exact commit, SHA-256 and file sizes**, with no unverified source content.
3. For an **explicit indexed source path**, optionally extracts one of a
   **small allowlist of public top-level scalar JSON fields**. Returns that
   exact value with SHA provenance, or \`VERIFIED_SOURCE_FIELD_NOT_PRESENT\`.
   No guess is produced when the source or field is unavailable.
4. Produces a hash-bound receipt and validates the original Git worktrees
   remained unchanged. No raw indexed text or SQLite database is uploaded.

This makes the R3 index **reproducibly queryable from the standard Demiurge
memory route and callable by other GitHub workflows**. It is NOT a persistent
SQLite process or 24/7 server: GitHub-hosted runners are ephemeral, so the
index is rebuilt per query. This deliberately avoids publishing the raw source
corpus or full-text database into public GitHub artifacts and caches.

## Controllable query interface

The workflow accepts:
- \`query\`: required public search terms (max 120 characters).
- \`source_path\`: optional exact relative public path, which must already
  exist in the eligible index.
- \`field\`: optional **allowlisted** public scalar; requires \`source_path\`.

Example without field: \`query=SCOBY\`. The output consists of verified
source pointers, **not a model answer**.

Example exact-source development probe:
\`query=Rowan pipeline source run\`,
\`source_path=data/rowan/health/PIPELINE_STATE.json\`,
\`field=latest_completed_source_run\`.
The pinned source contains \`42969641041\`, but this is known development
data, not an independent scientific or language-generalization finding.

An empty search produces \`NO_VERIFIED_SOURCE_MATCH\`; unavailable field
produces \`VERIFIED_SOURCE_FIELD_NOT_PRESENT\`. An unsupported field, stale
commit, path traversal or SHA mismatch **fails closed**.

## Evaluation truthfulness

\`JANUS_MEMORY_512_R4_DEVELOPMENT_QA.json\` freezes five transparent,
known-source checks for expected scalar extraction, missing field and
unfindable query. These test the **retrieval and deterministic JSON extraction
pipeline**. They are *not* sealed independent QA and do not demonstrate
a Transformer has learned to reason over memory.

The canonical native v1 remains a 128-byte, 446,208-parameter model.
It receives no bulk JSON in this workflow. No checkpoint is loaded,
trained, mutated or promoted. The R2 256/512-byte experimental candidate
weights remain untrained.

## Next gated milestone

Independently authored, sealed *source question–answer* labels, controlled
query difficulty and source-family splits, honest comparison with the
filename-only and v2 readers, multi-document evidence merging, negative
questions and refusal. Only thereafter test whether a separately trained
longer-context model can produce grounded answers. **512 MiB remains a
capacity target**, not an achieved trained-context window.
