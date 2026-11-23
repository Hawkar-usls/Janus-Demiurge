# JANUS Unified Memory v2 — isolated full-current pilot

Status: **experimental / not deployed / read-only / no NAS mutation**.

A rebuildable SQLite FTS5 index of all Git-tracked JSON in this repository, with:
- An exact current-tree coverage ledger, per-file SHA-256 and pinned source commit;
- Full-text search over JSON bytes, including malformed JSON (marked, not silently discarded);
- Explicit path/source-URL graph edges only; never promote semantic guesses to evidence;
- A compact read-only graph.json for an isolated HRain preview;
- Independent rebuild/verify, without overwriting SQLite or source files.

## Run in an isolated checkout

Use Python 3.12+ with Git installed and enough temporary disk space.

    python experiments/unified-memory-v2/janus_unified_memory.py build --registry-root . --db /tmp/janus-umv2.sqlite
    python experiments/unified-memory-v2/janus_unified_memory.py verify --registry-root . --db /tmp/janus-umv2.sqlite
    python experiments/unified-memory-v2/janus_unified_memory.py search --db /tmp/janus-umv2.sqlite --query SCOBY
    python experiments/unified-memory-v2/janus_unified_memory.py rebuild-verify --registry-root . --db /tmp/janus-umv2.sqlite
    python experiments/unified-memory-v2/janus_unified_memory.py export --db /tmp/janus-umv2.sqlite --output /tmp/janus-umv2-graph.json
    python -m unittest discover -s experiments/unified-memory-v2/tests -v

Do not build SQLite directly on an SMB share or put output inside the source repo. Build refuses to overwrite existing files, including a damaged index. Recovery creates a **new** database from sources; it is not an in-place repair.

## First real-corpus local read-only proof

Independent local sandbox on Yaksa, 2026-11-10, on source HEAD 7da4d8aaa1c228ea398e3f820ba8bcec7c2b519c:

- total_tracked_json=7201, excluding 44 self-export catalog JSON.
- indexed_json=7157, parsed_json=7153, malformed_json=4.
- explicit_relations=38922 (exact literal JSON path and source URL links, not vetted knowledge).
- Deep source SHA-256 verification PASS; SQLite integrity PASS.
- Fresh rebuild-verify PASS with source_manifest_sha256=32eafed4eaa27900355be80280145f1929c754cbdfd2cf6cda1dbde41b471abc.
- FTS query for SCOBY returned actual named JSON documents.
- Read-only HRain projection: 7157 nodes, 38922 edges, 7128122 bytes.

The GitHub Actions workflow runs independent validation on the code's proposed PR HEAD; do not conflate local proof with an Actions PASS before its run finishes.

## Boundaries and follow-up

Only this repository's current tracked JSON snapshot is indexed. It does **not** cover the other 13 public repositories, historical commits, private NAS journals, or non-JSON document bodies. Full graph rendering is intentionally bounded; search is provided by the SQLite index, not by the browser preview. The existing NAS database, services, containers, Hrain/main, and archived HRain state remain unchanged. Production integration requires separate approval, backup verification and fail-closed source access.
