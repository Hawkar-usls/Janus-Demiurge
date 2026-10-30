# DADDY_KEYMASTER — Oracle → BOINC → Ray activation runbook

## Scope and current evidence

The `daddy_keymaster/providers.py` command evaluates **onboarding gates only**.
It does not connect cloud accounts, create a VM, submit work, run Ray, collect
volunteers, access remote SSH/RDP, test public IPs or grant dispatch.
`PROVIDER_ACTIVATION_REQUESTS.json` deliberately starts with all claims false.

Cloud workflow: `JANUS DADDY_KEYMASTER Compute Registry Witness`.
Persisted public outcomes (without account IDs, credentials or host addresses)
are in isolated `janus/daddy-keymaster-state/daddy_keymaster/state/PROVIDERS_LATEST.json`.
The existing `LATEST.json` continues to be the authoritative record for
**persistent** available capacity and must remain empty until independently
verified workers exist. Neither manifest grants live activation.

## Stage 1 — OCI Always Free (mandatory first external source)

1. **Owner action**: use the official Oracle Cloud Console to create or sign
   in to an account, confirm the home region and Always Free eligibility, and
   review account-specific quotas. Do not share a password, API secret,
   SSH private key, OCID, billing card or session token in chat, GitHub issues,
   repository files or GitHub workflow logs.
2. **Conservative proposal** (not a provisioning script):
   `VM.Standard.A1.Flex`, **1 OCPU**, **6 GB RAM** and the minimum
   eligible boot volume (normally 50 GB); no extra billable IPs, volumes,
   backups or network products. Confirm the `Always Free` label and actual
   monthly usage with OCI's own account billing and limits before creating
   anything. Official documentation pages differ on A1 monthly quota
   presentations, so do not blindly infer available hours from a web page.
   Do not upgrade the tenancy or create a paid shape.
3. **Authorized read-only inventory**: after a personally created OCI VM
   exists, in an authenticated local OCI CLI context, run
   `oci compute instance get --instance-id "$INSTANCE_OCID" > /tmp/daddy-oci-instance-get.json`.
   This output may include private metadata: keep the original *local*.
   From a trusted checkout of the repository run
   `python -m daddy_keymaster.providers --oci-instance-get /tmp/daddy-oci-instance-get.json --out /tmp/daddy-oci-local-preflight.json`.
   The preflight emits only shape, CPU, RAM and running status; it removes
   instance IDs, networking metadata and any other fields. **Do not commit
   the input**, and don't infer ownership or free billing from a passing shape.
4. **Admission to future real workloads requires** an independently trusted
   read-only IAM identity (prefer instance identity/least privilege), actual
   free-tier and home-region verification, cost guard plus zero-billing
   evidence, owner authorization, an authenticated heartbeat, private network
   path, expiry, revocation, recovery and an exact job receipt.
   Until that future separately reviewed driver exists: `WAIT`.

References:
- [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [OCI CLI compute instance get](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/compute/instance/get.html)

## Stage 2 — Own BOINC project with voluntary opt-in

- Establish a project server on infrastructure the owner actually controls;
  do not rely on other projects' volunteers or enumerate BOINC clients.
- Follow [BOINC's official server cookbook](https://github.com/BOINC/boinc/wiki/Create-a-BOINC-server-%28cookbook%29)
  to set up a project and work generator, validator and assimilator.
- Use HTTPS, protect administrator operations, protect workunit signing keys
  separately and publish an understandable description of task content.
  Volunteers must intentionally attach to **this** project, be able to
  disconnect at any time and be subject to bounded resource use.
- First eligible demo: public/synthetic deterministic workunit sent to an
  explicitly attached owner-operated test client; verify independent result
  and a clean revocation. Server hosting may cost money, so do not claim a
  zero-cost deployment before resources are verified.

Reference: [BOINC Going public](https://github.com/BOINC/boinc/wiki/Going-public).

## Stage 3 — Private Ray cluster

- Ray is a **scheduler**, not a supplier of machines. Cluster nodes must
  already be owner-authorized (e.g. verified OCI or separately approved host).
- Never expose the Ray Jobs API, dashboard or Ray Client to the public internet.
  Ray can execute arbitrary submitted Python; use private-only networking,
  token authentication when supported, tightly scoped job submitter and
  per-job allowlisted trusted workloads. No Ray endpoints or secrets in Git.
- Start with an **isolated local two-worker development test**, then expand
  to actual authorized separate hosts and demonstrate failure/recovery.
- No true distributed recovery claim until two distinct authorized nodes
  execute source-bound work with independently verified outputs.

Reference: [Ray security](https://docs.ray.io/en/latest/ray-security/index.html).

## What a real provider activation will change

It must come as its own reviewed PR containing a minimal read-only driver,
provider-specific tests, and an independent actual-run receipt. A local
self-asserted JSON claim, public service availability, or an unauthenticated
network response can **never** turn on `providers.*.enabled`, grant remote
dispatch, create a paid resource, authorize a third-party server, or extend
JANUS code-writing powers.
