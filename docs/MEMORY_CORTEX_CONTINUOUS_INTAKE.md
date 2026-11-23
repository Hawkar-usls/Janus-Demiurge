# Continuous Memory Cortex intake

The previous R3/R4/R5 snapshot remains a reproducible regression reference.
The growing route uses a separate durable `memory-cortex-state` branch and is
called by the existing Demiurge unified-memory query alongside that reference.

Every 20 minutes, subject to GitHub scheduling, the collector:

1. Migrates the previously verified 4,712-document / 49,460,266-byte R3 baseline
   exactly once; migration is not new information.
2. Pins the current public Meta Registry Git SHA and checks newly encountered
   blob IDs. Existing/rejected blobs are not read again. Exact SHA-256 content
   duplicates, including renamed copies, contribute no new capacity.
3. Resumes Universal Beetle's `candidates.parts` ledger from durable byte cursors.
   Canonical arXiv/Zenodo IDs enter a persistent queue. Cortex independently
   fetches the corresponding official API record, validates its identifier and
   stores only actual title/abstract/description text with provider digest and
   Beetle provenance. These are primary abstract/metadata, not full papers,
   verified scientific claims, generated answers, or training labels.
4. Accumulates up to 512 new registry document reads and eight bounded provider
   fetches per scan. Errors use exponential backoff, pausing after five failed
   fetches. Arbitrary discovered URLs, redirects and executable content are not
   fetched/executed. Source confidentiality/holdout exclusions are retained.
   A separate tail cursor reserves space for recent discoveries, with Cortex
   direction leads ahead of historical backlog. Historical cursors and queued
   records are preserved when backfill pauses; old successes are never refetched.
5. Publishes after **4 MiB of new distinct text OR 128 new documents**. Pending
   text survives all intermediate runs. It rebuilds FTS from exact CAS objects,
   rechecks all hashes and SQLite integrity, then appends a generation manifest
   and advances `CURRENT.json`. A normal single Git commit atomically publishes
   all state; conflicting pushes fail instead of overwriting history.

After every actual generation publication, a separate read-only job checks out
the persisted branch on a fresh runner, replays its object hashes, reconstructs
FTS and queries the newly active generation. No-publication cycles skip this
consumer job. The same reusable worker is wired into the standard Demiurge query.

`objects/` contains exact UTF-8 source bytes keyed by SHA-256, not a binary
SQLite database. `STATE.json` retains seen blobs, completed provider IDs, errors,
cursors and pending/active document membership. `generations/` preserves all
previous manifests. The active-generation query replays object hashes, builds
FTS and returns source citation pointers. It never answers from uncited model
text. No raw provider response or SQLite database is uploaded as an artifact.

The 512-MiB counter is the sum of distinct stored source-text documents actually
indexed in the active generation. Pending bytes and all metadata, repeated source
hashes, SQLite overhead and synthetic seeds are excluded. Source versions remain
separately addressable; SHA distinctness does not establish semantic novelty or
independent scientific evidence. The corpus cap is 512 MiB; text documents remain
bounded to 1 MiB each. Full-history and arbitrary repository ingestion are absent.

No-new-input runs do not rebuild or publish generations. Baseline migration,
source intake and search are different from training weights or improving QA.
Independent unseen-question evaluation and all model-promotion gates remain open.

The initial main push starts a real collection immediately. Subsequent scheduled
collection is GitHub-hosted, not dependent on a chat or an owner's computer.

## Validation

`python -m unittest discover -s tests -p 'test_memory_cortex_growth.py' -v`

Tests cover threshold accumulation/restart, exact-content and provider-ID dedupe,
no-op runs, source/worktree drift, exclusions, corrupt CAS/state, generation
parentage, append-only Beetle cursor continuation, provider mismatches/backoff,
arXiv identifier/XML checks, citation provenance, abstention and symlink refusal.
