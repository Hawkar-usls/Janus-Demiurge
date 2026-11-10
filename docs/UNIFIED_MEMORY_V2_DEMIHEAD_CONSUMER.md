# JANUS Demiurge: Unified Memory v2 evidence-context consumer

**Mode:** ISOLATED_PROBATION / READ_ONLY / NO_AUTO_PROMOTION.

Source chain:

    janus-meta-registry (JSON / pinned commit)
       -> read-only SQLite FTS5 current-tree cache (Meta Registry PR #503)
       -> Demi_Head tools/unified_memory_v2_bridge.py (bounded query receipt)
       -> Janus-Demiurge tools/demiurge_unified_memory_v2_consumer.py
       -> context proposal for restored/memory_graph_query.py

DemiHead's new adapter is staged in its separate draft PR. This repository's consumer accepts only the exact packet schema, SHA-256 self-consistency and mandatory independently supplied source commit + manifest digest. It checks original file links, limits results to 20 and related links to 8 per match, and rejects authority escalation even if a forged packet is rehashed.

The resulting graph uses standard nodes/edges arrays and can be passed to restored/memory_graph_query.related_subgraph to inspect local structure without a new mutable graph owner.

## Manual bounded handoff

    python tools/demiurge_unified_memory_v2_consumer.py --packet /tmp/demihead-memory-packet.json --expect-source-commit VERIFIED_COMMIT_SHA --expect-manifest-sha256 VERIFIED_MANIFEST_SHA256 --output /tmp/demiurge-context.json

The output file is created only if it does not exist. No GitHub issue, PR, commit, API call, network dispatch, agent promotion, model training, or production graph update is performed. Source-revision pinning is necessary; a packet self-hash alone does not establish sender identity or authenticity. A sender may fabricate a packet and its unkeyed hash, so the expected source pins MUST be obtained independently and a trusted upstream index verifier must be run before using the context for conclusions.

## Verified isolated end-to-end trial (2026-11-10)

Against real Meta Registry current-tree SHA 7da4d8aaa1c228ea398e3f820ba8bcec7c2b519c and manifest 32eafed4eaa27900355be80280145f1929c754cbdfd2cf6cda1dbde41b471abc:
- DemiHead returned 8 SCOBY matches.
- Demiurge projected 36 nodes and 44 explicit links.
- packet_sha256 equals input_receipt_sha256.
- authority_delta=0; no training, graph mutation, module admission or network dispatch authorization.

**Not yet done:** live runtime registration, continuous cross-repo fetching, private NAS ingestion, scientific independent corroboration, historical Git lineage or production deployment.
