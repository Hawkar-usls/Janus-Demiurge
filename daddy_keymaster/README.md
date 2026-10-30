# JANUS DADDY_KEYMASTER — Distributed Compute Broker

**Scope:** resource discovery, lease-health and *dry-run* scheduling for four user-selected compute sources. This is distinct from the existing `janus_model/keymaster.py`, which collects scientific training material and does **not** manage compute nodes.

## Selected resources (all registered)

| Source | Contract | First production status |
| --- | --- | --- |
| GitHub Actions | Official standard ephemeral runner in the owner's public repo; only usable **inside the current job** | Real worker observation; bounded contract test |
| Oracle Cloud Always Free | Explicitly owner-controlled tenancy and eligible home-region VM; independently verified zero-billing guard | `WAIT_OWNER_REGISTRATION` |
| BOINC voluntary computing | A project operated/authorized by the JANUS owner and opt-in volunteer clients; **not** BOINC's existing unrelated projects | `WAIT_OWNER_PROJECT_AND_VOLUNTEERS` |
| Ray | Scheduler **within** an owner-approved private cluster; Ray is not a source of free servers | `WAIT_OWNER_CLUSTER` |

No VM, BOINC server, Ray cluster, or billing agreement is created by this change. No provider token is stored in git. Publicly reachable SSH/RDP, leaked credentials or an arbitrary "free dedicated server" **never** count as owner permission.

## Contract and execution

The policy in `POLICY.json` pins all four source identities and denies network host scanning, cloud instance provisioning, paid tasks, permission escalation, remote execution and automatic merge. `OWNER_REGISTRY.json` starts empty by design. The owner must separately review a worker's provider, allowed task kinds, capacity, cost=0, 30-minute heartbeat freshness, and expiration. All other registrations are refused. Non-GitHub providers remain disabled until an actual account/project/cluster exists and a separate security-reviewed driver is created.

The only current executable cloud worker is GitHub Actions itself. `broker.py` observes its **real** per-run environment, determines bounded capabilities, and computes a deterministic non-executing task plan. It does not treat an ephemeral runner as a permanently owned server. `TASKS.json` contains two safe example tasks; they are not executed or sent anywhere by the broker.

Workflow `JANUS DADDY_KEYMASTER Compute Registry Witness` runs scheduled six-hourly, on explicit dispatch, when code changes merge into main and as read-only PR CI. Each cloud pass performs adversarial tests and publishes a source-bound report. Trusted runs save a post-job persistent-capacity roster in `LATEST.json` and immutable per-run observations under `receipts/` in isolated `janus/daddy-keymaster-state`, **never** in main. The GitHub runner is counted as ready only *during its own witness job*; the persisted roster retires that ephemeral runner and explicitly reports zero reusable capacity outside that job. History stays available in append-only receipts.

## Activation path for each source

- **GitHub Actions**: ready when the first trusted workflow run confirms a real current runner; task dispatch remains `DRY_RUN_NOT_DISPATCHED`. Existing workflows already execute JANUS tests independently.
- **Oracle Always Free**: requires an OCI tenancy, explicit per-resource zero-cost policy/quotas and an owner-registered instance. No IAM keys should be entered into chat or committed. ARM shape and capacity can vary by region; idle instances may be reclaimed. A future driver needs constrained identity and separate review.
- **BOINC**: establish or receive explicit permission for a project server and recruit consenting volunteers. Project admins control the workloads; discovering public BOINC client hosts is prohibited.
- **Ray**: start a private, access-controlled Ray cluster on machines already authorized through another provider or owned hardware, with bounded jobs and no public unauthenticated dashboard/API.

When a provider becomes real, its adapter must provide authenticated heartbeats, capability attestation, specific authorized workloads, exact job receipts and a cancellation/revocation mechanism. This v0.1 code never interprets external discovery text as authority.

## Acceptance levels

1. **CONTROL_PASS**: unit tests, registry validation, anti-injection, no costly resources, expired workers excluded.
2. **CLOUD_WITNESS_PASS**: a real owned GitHub-hosted runner observed and the receipt durably persisted.
3. **DISTRIBUTED_RECOVERY_PASS** (not claimed): two independently authorized workers, target-local verification, forced failure of one worker, exactly-once recovery, durable receipt.
4. **FULL_AUTONOMY** (not claimed): admission across multiple provider types, long-duration unattended operation and verified independent improvement.

Do not claim actual Oracle, BOINC, or Ray CPU capacity until a real user-owned endpoint/cluster/project and independent evidence are available.
