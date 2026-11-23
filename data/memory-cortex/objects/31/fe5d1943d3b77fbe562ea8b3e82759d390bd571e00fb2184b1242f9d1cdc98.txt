# JANUS autonomous roadmap loop v2

Canonical human roadmap: https://github.com/Hawkar-usls/Janus_Genesis/issues/302

The cloud workflow runs hourly, after the trusted Rowan Durable Observer, and on reviewed implementation changes. Its completion wakes the independent Rowan and cross-organ witnesses. GitHub schedules may be delayed. It does not rely on an owner PC, NAS, local model daemon or chat remaining alive.

The loop freezes each public Git ref, reads JSON at exact commits, records raw SHA-256 and Git blob SHA, derives current findings, regenerates an ordered roadmap and persists immutable receipts. A separate worker rereads exact source bytes and verifies the derived result before recording phase acceptance.

Live files:
- data/autonomy_loop/ROADMAP.md — automatically regenerated priorities, work/idle/degraded metrics and evidence-driven tasks.
- data/autonomy_loop/LATEST.json — last observed state and immutable receipt pointer.
- data/autonomy_loop/CHECKPOINT.json — verified continuation and accepted phases.
- data/autonomy_loop/receipts/ — preserved observations, including faults and unknown sources.

The approved order is P0.1 through P0.6, then P1 through P5. Findings can add bounded tasks inside their phase; they cannot reorder prerequisites or grant capabilities. An absent verifier or implementation remains WAIT/HOLD.

v2 adds a reviewed metadata-only P0.2 handler: strict Rowan/AURA/council reconciliation into own immutable coordination receipts, followed by an exact-pinned full public-source witness. A separate worker repeats the witness before phase acceptance. Later mutation handlers require reviewed executable code and their own acceptance evidence. A successful collector does not imply a code change, model synthesis, source synchronization, scientific validation or full #162 acceptance.

Generated data/autonomy_loop/ status, roadmaps and checkpoints are excluded from EYE and native corpus selection; they must not become self-confirming training evidence.

No provider API is called and no Rowan credits are spent. Reads are fixed to public status metadata. Runtime writes are limited to this repository's data/autonomy_loop/ surface and the existing data/rowan/coordination/ metadata lane. Model/issue text is not executed. No source-history deletion, force push, arbitrary shell command, automatic main-code merge, secret management or authority expansion is present.


The live collector also pins Beetle's own delivery-health and routing-gate receipts (18 fixed sources total). A green producer workflow does not clear a pending queue: aggregate receiver states, unknown ACKs and routing HOLD remain explicit P0.3 tasks. Inbox ACKs never attest downstream runtime consumption. Public roadmap output uses aggregate counts, without naming opaque/private receivers.
