# DADDY_KEYMASTER — real authorized ephemeral cloud compute

This lane complements the read-only 4-source registry. The user chose GitHub
Actions, OCI Always Free, BOINC and Ray. Of these only GitHub Actions offers
**already owner-authorized** compute without a separate account/volunteer grant.

## Two actual distinct GitHub VMs

`.github/workflows/janus-daddy-keymaster-compute.yml` runs two separate
ephemeral **GitHub-hosted** Linux jobs from the owner's public GitHub repo:

- x64: `ubuntu-24.04`, standard hosted 4-vCPU class
- ARM64: `ubuntu-24.04-arm`, standard hosted ARM CPU class

Each job runs a *different admitted shard* from a fixed work catalog:
- x64 — DADDY_KEYMASTER registry contract tests + Rex research→code safety;
- ARM64 — Oracle/BOINC/Ray provider admission tests + Rex research→code safety.
Both independently repeat the Rex suite for cross-architecture agreement.
This is fair-use task sharding, not account/limit rotation or arbitrary
remote code execution. Each emits a source
SHA256 manifest, observed GitHub-run ID, platform and counted real test cases.

A third **read-only** auditor runs on a separate Actions worker, rehashes
sources, checks exact commit/run ID, both platforms, independent counts and
denials of paid compute/remote authorization. A fourth short-lived job uses
a writable credential **only on trusted main pushes/dispatches**, independently
replays the audit and stores a receipt in the isolated state branch:

- `janus/daddy-keymaster-state/daddy_keymaster/state/compute/LATEST.json`
- `janus/daddy-keymaster-state/daddy_keymaster/state/compute/receipts/<run-id>-<attempt>.json`

No runnable worker remains in the permanent roster after the workflow.
The lane uses no Ray private API, Oracle token or BOINC volunteer account.

## Permission and rate boundaries

- Only standard public-repository GitHub Actions; no larger billed runners.
- Run on approved source changes, explicit dispatch, PR tests **and a deliberately
  conservative twice-daily UTC schedule (02:37 and 14:37)**; this is not a
  background continuous compute farm and never requeues itself. Scheduled
  triggers may be delayed or dropped by GitHub and are not uptime SLAs.
- At most 2 concurrent execution workers; **up to 10 minutes per worker job**,
  bounded two-suite workload per machine, 2 scheduled waves per day, results
  only 7 days in Actions artifact storage; private tokens scrubbed from tests.
  Additional manual runs/pushes are not automatically rate-limited by the
  workflow, so a future activity guard can apply stricter admission.
- PRs have read-only access. State writer exists only for non-PR events.
- No model-generated work passes this lane until an independent reviewed
  profile is implemented; Rex still cannot bypass auditor/Nexus admission.
- `TWO_EPHEMERAL_WORKERS_VERIFIED` means two separate, temporarily assigned
  cloud workers completed real JANUS checks. It is **not** two persistent
  dedicated servers, a Ray cluster, a real BOINC project or failure recovery.

Official docs:
[GitHub Actions standard runners](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job),
[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

## Three remaining source gates

**Oracle**: owner OCI tenancy and eligible instance must first exist.
**BOINC**: owner-operated project and explicitly opted-in volunteer clients
must exist. **Ray**: private owner-controlled cluster must exist.
The previous provider readiness reports remain fail-closed until then.
\n## Continuity contract\n\nDADDY_KEYMASTER has **asynchronous jobs and durable independent test receipts**, not a continuously running server. A new scheduled run requests new ephemeral standard GitHub workers, only while the repo stays public and actions are enabled. It does **not** attempt to maximize concurrency against GitHub terms, evade capacity limits, rotate identities, reuse external machines, or run mining/proxies. Failures halt a wave; they do not trigger unlimited retries. Deployment and arbitrary self-authored code remain outside the workload allowlist.\n