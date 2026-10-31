# JANUS DADDY_KEYMASTER · Bounded CI heartbeat R2 staging

This is an **event-triggered, checkpointed development/test supervisor**, not an
always-on model host, free compute marketplace or production model dispatcher.

## Cycle

Every scheduled window (04:41 and 16:41 UTC, twice daily) or human-issued
`workflow_dispatch` on trusted `main`:

1. A clean main-source runner validates tests and checks the shared state ref.
2. The prepare job appends at most **two unique tasks per main commit** to an
   isolated `janus/daddy-keymaster-ci-queue-state` branch.
3. Separate x64 and ARM64 runner jobs each claim at most one *typed project
   development test suite* using a fast-forward-only Git compare-and-swap.
4. Each job executes only hard-coded repository unit tests, uploads a
   SHA-bound receipt, then commits CHECKPOINT and COMPLETE using the current
   lease generation. A stale holder cannot commit its result.
5. A fresh **read-only** Witness independently compares uploaded worker receipts
   with the exact completed Git journal state and fails if any task was put
   into unresolved HOLD.

When a commit has already been processed, the next scheduled run is idle;
**there is no recursive Actions dispatch, no continuous spin loop and no
execution unrelated to this repo's production/testing/release**. GitHub
workflows may be delayed or skipped: a cron expression is NOT a service-level
heartbeat guarantee.

## Authority boundaries

- GitHub-hosted runners are ephemeral. They are not pinned user-controlled
  VMs and GitHub may place eligible workloads on different backend clouds.
- Only `main` on `schedule` / `workflow_dispatch` may request writes to the
  fixed state branch. PRs run unit tests with `contents:read` only.
- `MAX_ACTIVE=2` limits this queue only, and does not globally limit other
  Janus-Demiurge or JANUS repository workflows.
- Work dispatch is *in-process CI execution of fixed allowlisted tests*, not an
  API to arbitrarily create workflow runs or start general computation.
- Remote Oracle/BOINC/Ray provider registration remains empty and disabled.
  No external machine, hardware device, owner credentials or paid research
  provider is commandeered or activated.
- Meta Registry is an archival source of evidence, not a transactional CAS
  lock service. Source code is always fetched independently from `main`.
- R2 #385 blind native champion validation, secure loader PR #301,
  independent consumer ACK and rollback remain separate production gates.

## Operational limits

A single Git queue revision is intentionally bounded to 32 task records and
256 events (about 16 distinct two-task source commits in the current format).
On reaching either cap the heartbeat fails **closed** rather than evicting
unreviewed history or recycling IDs. **A signed immutable archive + segment
rotation and off-GitHub backup are not yet implemented**: this is a known
blocker to unbounded unattended operation.

Leases that expire with uncertain outcomes go to `HOLD`, never silently
restart. Fenced CAS prevents stale state commits, but does not guarantee
exactly-once execution of arbitrary external side effects. Any unresolved
HOLD causes Witness failure and must be reconciled with real receipts.

GitHub Actions schedule delivery and limits are controlled by GitHub.
For high availability, integrate an owner-operated permitted always-on
coordinator with independently durable queue storage and enrolled workers.
Do not use GitHub-hosted Actions as a permanent AI inference server.

## Verification

```
python -m unittest discover -s tests -p test_daddy_keymaster_bounded_ci.py -v
python -m unittest discover -s tests -p 'test_daddy_keymaster_git_cas_*.py' -v
```

PR CI verifies the engine but never mutates the runtime queue branch. Actual
cron/dispatch execution starts only after reviewed merge of the workflow
onto the repository default branch. A green unit test must never be
misreported as a successful live scheduled cycle.
