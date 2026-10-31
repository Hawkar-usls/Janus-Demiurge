# JANUS ASYNC COMPUTE RELAY · R1 cross-worker engineering evidence

## Context and inherited JANUS contracts

This bridge reuses existing JANUS concepts, rather than asserting a new AI
runtime: Habitat HOME/RETURN (state outlives a worker), SWARM Objective Lease
Fencing (stale holder cannot mutate current state), SWARM Causal ACK Work Claim
(work receipt is not world truth), Genesis durable journal/fencing (intent is
not action), and the existing DADDY_KEYMASTER bounded rotation planner.

Related sources:
- Meta Registry: data/JANUS-SWARM-OBJECTIVE-LEASE-FENCING-PASS-2026-08-16-v1.0.json
- Meta Registry: data/JANUS-SWARM-CAUSAL-ACK-WORK-CLAIM-RUN-001-2026-08-23-v1.0.json
- Meta Registry: registry/experimental/JANUS-GENESIS-THIRD-WISH-GIT-HABITAT-LIVE-HOME-AND-RETURN-RECEIPT-v1.0.json
- janus-distributed-ai-swarm: docs/HABITAT_GIT_SWARM_CLIENT.md
- Janus_Genesis: protocol/JANUS_HABITAT_PC_INDEPENDENCE_CONTRACT-v1.0.json

## What actually runs in CI

.github/workflows/janus-daddy-keymaster-async-relay-e2e.yml:

1. X64 ephemeral job executes standard-library atomic SQLite stress tests
   (including two simultaneous claiming processes and a worker killed by
   os._exit after commit). It creates only two synthetic allowlisted tasks,
   completes task A and exports a self-contained checkpoint plus JSON receipt.
2. ARM64 ephemeral job receives that exact artifact, checks byte digest,
   GitHub run/source identity and hash-journal tip, then completes task B.
3. Independent X64 witness validates the final journal and both completed
   tasks. Each job has contents:read and persist-credentials:false.

All jobs run separately and sequentially; no secrets, model training, Rowan
credits, dispatch API calls, new accounts, or production state branch writes.
A GitHub artifact is a finite-retention handoff, not a guaranteed persistent
transactional queue.

## Local API

    Relay(db_path).enqueue(task_id, kind, pinned_sha256, cpu=1, priority=1)
    token = Relay(db_path).claim(holder_id, allowed_kinds, cpu, now=utc)
    Relay(db_path).checkpoint(token, checkpoint_sha256, now=utc)
    Relay(db_path).complete(token, result_sha256, now=utc)
    Relay(db_path).reconcile_expired(now=utc)
    result = Relay(db_path).witness()

Allowed kinds remain contract_test, readonly_index, pure_module_eval.
No arbitrary command field is accepted. SQLite BEGIN IMMEDIATE ensures a
single host's competing claimers serialize. A lease token includes an
incrementing generation, source identity, holder and deadline, and cannot be
replayed after completion. An expired possibly-executed lease becomes HOLD,
not a new runnable task. There is no generic automatic recovery for uncertain
external effects.

The hash-chained journal is checked for sequence, prev/next hashes, valid
state transitions and exact projection onto live task rows. The journal is
tamper-*evident* for unsupported mutation but not externally signed; an
attacker with write access to the entire DB could rewrite both history and
hashes. Production requires an independently authenticated custody domain.

## Important non-claims

- Does not provide a persistent GitHub runner or unrestricted free compute.
- Cross-job sequential artifact transfer is not multi-host transactional
  storage and not proof of distributed exactly-once execution.
- The local SQLite queue is not yet wired to provider-specific authenticated
  dispatch drivers; GitHub CI merely tests the developer-built relay.
- The system is not yet a full autonomous task scheduler across all JANUS
  organs or outside provider machines.
- No champion checkpoint promotion, no main deployment, no independent blind
  final issuer and no cross-consumer ACK gate has been granted.
- MAX_ACTIVE=2 is fixed for R2 safety; no claim that this alone globally
  limits every unrelated Actions workflow across the JANUS ecosystem.

## Next bounded gates

1. Source-authenticated durable shared state with CAS on immutable generation,
   replayable event cursor and independent offsite backup; test two different
   processes simultaneously using the real shared store, not an artifact.
2. Binding of explicit owner-admitted, repo-relevant workflows to typed task
   definitions and signed/verified outcomes, no arbitrary shell or
   unbounded GitHub workflow self-requeue.
3. Real process kill during a claimed task, frozen-source reconciliation,
   idempotent effect proof, crash recovery and duplicate-safe resume.
4. Multi-provider connectors only for owner-controlled or consenting nodes,
   with documented quota/billing restrictions, TTL, auth, revocation,
   per-provider capacity and independent load-admission checks.
5. Separate model champion R2 #385 and secure loader #301 admission before
   production model replacement. Only then trial bounded 2 -> 4 workers.

Truth boundary: this is a proof of transportable *state and work sequencing*
for synthetic project tasks, not proof of scientific model improvement.

## R2 staging · Git fast-forward cross-process CAS (separate PR branch)

`daddy_keymaster/git_cas_queue.py` now supplies an independent, JSON-native
queue using a dedicated **lab-only** Git branch:
`janus/daddy-keymaster-cas-lab-20261031` and fixed path
`state/relay_queue.json`.

This code is **not a dispatcher**. It creates a proposed journal append for
one typed synthetic or authorized project task, reads the exact ref SHA and
then commits a single-parent child. A normal non-forced Git push must be a
fast-forward, so two competing children of the same parent cannot both advance
the ref. A failed push is a terminal `Conflict` decision for the stale attempt:
no silent retry, duplicate external effect, or force push.

Two-clone tests initialize a dedicated local bare Git server, make independent
clones, then race distinct lease claims against the same remote branch. Tests
also check event-chain replay, stale source/result digests, timeout => HOLD and
checkpoint/complete handoff between independently re-fetched clones.

### Scope of evidence

- Simulated shared Git server via **separate local Git clones**, potentially
  competing processes on one CI host. This is a real Git ref race, **not** yet
  a live GitHub remote multi-host contention test.
- Real GitHub-hosted runners retain `contents: read` on PRs; production or
  remote lab writes require independent trusted authorization. The adapter
  deliberately denies GitHub writes outside a trusted main workflow_dispatch
  guard and the fixed lab-only branch.
- A Git ref fast-forward verifies the single-branch linear extension. It does
  not provide exactly-once external side effects, a signed remote audit
  authority, automatic machine discovery, multi-host availability, or a
  globally enforced worker budget across unrelated workflows.
- Because the state is append-only with a finite event cap, periodic safe
  compaction will require a separately reviewed snapshot witness.

### Next real acceptance gate

Run a **trusted, opt-in cross-host GitHub remote CAS test** against only the
isolated lab branch, under reviewed least-privilege credentials; verify that
one of two claims rejects and survives a remote worker crash without source
or champion mutation. Use separate readonly Witness for final receipt.
