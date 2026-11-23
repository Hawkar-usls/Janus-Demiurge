# JANUS DADDY_KEYMASTER · Full JSON DB mirror and lightweight NAS role

## Sources and custody

This Meta Registry workflow stores a **complete, source-SHA-pinned JSON copy
of the Keymaster CI task queue**, including the current event log, all
verified archived segments, archive head and source-dedup markers.
It does **not** copy the whole JANUS HRAiN scientific memory, secrets,
private model weights or NAS file system. Expansion to other databases
requires separate, explicitly specified data contracts.

- Source: public \`Hawkar-usls/Janus-Demiurge\`,
  \`janus/daddy-keymaster-ci-queue-state\`.
- Every GitHub read is pinned to one exact 40-hex Git commit.
- \`scripts/keymaster_db_verify.py\` independently replays every event,
  checks archive receipts and verifies source markers.
- \`scripts/keymaster_db_sync.py\` generates
  \`data/daddy_keymaster_db/snapshots/<source-commit-sha>.json\`,
  the SHA-bound \`LATEST.json\`, and stable \`MIRROR.json\` +
  \`MIRROR.sha256\` for cold replication.
- Existing snapshots are immutable; any same-SHA collision or rewritten
  prior source is a hard failure. Zero-content changes produce no new commit.
  Every update is a normal **non-forced push**; competing changes fail closed.

## GitHub Actions duty

The workflow \`janus-keymaster-db-json-sync.yml\` runs at two UTC windows
per day (05:19 and 17:19), manual dispatch or a main source change.
Pull requests can validate only and cannot write Meta Registry.

The workflow uses project-relevant export/verification tasks, not generic
always-on AI inference, not a third-party GPU farm, and not a workaround for
GitHub Actions quotas or terms. The workflow has a strict time budget and
per-file size and archive count limits. GitHub schedules are best effort and
may be delayed or disabled after prolonged repository inactivity.

## Optional QNAP TS-433 cold store

The NAS is a **passive backup appliance**. Do not run an LLM, Ray head,
training loop, Docker orchestration or a Github self-hosted runner on it.

Optionally, the owner may install \`scripts/nas_keymaster_cold_pull.sh\` in a
non-admin QNAP account and schedule it at most once or twice a day, pointed
to an existing private folder via \`JANUS_COLD_DIR\`. It performs only two
short HTTPS GETs for a fixed SHA file and (if changed) a JSON file.
When the digest matches an existing verified local copy it performs no disk
rewrite. A checksum mismatch, unavailable network or missing required
utilities yields HOLD; it never erases the prior verified copy.

This optional script is **NOT deployed** by GitHub Actions, cannot infer a
private NAS address and needs the owner to configure permissions and schedule.
It does not register a compute worker, expose SMB/SSH publicly or modify
model checkpoints. If disks must hibernate, schedule the pull alongside
existing wake periods rather than waking them solely for JANUS.

## Security and recovery

The Meta Registry is a **mirror**, not the primary CAS authority. Its JSON
cannot be used as an execution request. The primary journal and fencing stay
with Demiurge. To recover, independently verify pinned Git source SHA,
archive chain, all receipts and a suitable current source head; never
automatically replay completed or uncertain operations. No model champion
promotion occurs without the R2 safety gates.

Current bounded exporter permits up to 64 archive segments and 8 MB per
snapshot. These limits are intentional and fail closed if reached; adding
incremental segment export is the next scale stage. No signed offsite
custody or uninterrupted 24/7 NAS connectivity is claimed.
