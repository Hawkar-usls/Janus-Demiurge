# JANUS DADDY_KEYMASTER R4: owner-operated opportunistic node

The source under owner_node/ is a **zero-credential, read-only local** proof:
independently validate one Git-CAS snapshot, then run a single bounded
synthetic SHA-256 computation on the owner-connected Windows host.

## Actual observations

- Successfully replayed an archive-backed snapshot: one archived segment,
  active queue epoch 8 and two completed tasks.
- Rejected an intentionally corrupted temporary ZIP with ZIP_SHA_MISMATCH.
- Completed a deterministic 40,000-iteration SHA-256 canary and saved a
  local receipt containing an exact source SHA and digest.
- On repeated invocation verified the existing proof without recomputation.
- A twice-daily Windows scheduled backup invokes the verifier and canary
  with bounded execution and without any GitHub write credentials.

No credentials, usernames, local drive paths, IP addresses, hostnames,
scientific model weights or machine-specific receipts are published.

## Strict truth boundary

Owner-connected does not mean continuously powered or online. The owner node
is an **opportunistic experimental computer**, not a live general-purpose
compute provider. The canary explicitly records:
- owner_node_availability = OBSERVED_ONCE_NOT_24_7
- remote_dispatches = 0
- champion_promotions = 0
- authority_delta = 0

It does not consume instructions from the Git queue, open inbound ports,
execute arbitrary commands, dispatch cloud jobs, train the current model,
change model checkpoints, access Rowan or claim network shares as workers.
The existing OWNER_REGISTRY.json worker list stays empty until separate
authenticated enrollment and revocable owner approval.

## Independent verification

The ZIP verifier uses only Python standard library. It checks SHA-256,
allowlisted bounded archive paths, all event hashes and ordinal sequences,
exact task-state projection, archive segment links, and per-source terminal
markers. It detects both damaged bytes and inconsistent inner JSON.

Archived source identity is evidence, not new authorization to execute an
old task. Proof is held on missing, modified or ambiguous receipts.

## Still required for continuous JANUS

A truly always-available owner-operated coordinator, external signed
backups, continuous heartbeat/revocation and lease-safe worker drivers,
independent blind model evaluation R2 (#385), secure loader (#301),
consumer ACK and tested rollback. GitHub Actions remains project CI only.

Merging source control does not remotely install or change the owner's
local Windows scheduled task; deployed local code is managed separately.
