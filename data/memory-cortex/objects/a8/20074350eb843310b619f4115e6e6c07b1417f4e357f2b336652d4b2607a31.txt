# ESSENCE v1.4 — owner-wide Github-only fleet audit

This audit inspects **all 48 publicly enumerable owner repositories currently returned by GitHub**,
including projects whose primary purpose is games, hardware or infrastructure.
This is a read-only audit, not approval to install or execute new code in them.

It resolves each repository's current default-branch commit SHA and fetches
three source/data files as bytes: `.janus/essence/manifest.json`,
`.janus/essence/fixture.json`, and `.janus/essence/kernel.py`.
The fetched remote Python is **never executed**. Instead the auditor requires
the remote kernel's Git blob identity to equal the audited
`de5199978fbafcbda836b77da370943f7ea2514e` and runs the locally
installed Meta Registry ESSENCE core against the repo's own manifest/fixture.
Checks include the role contract, synthetic six-role receipt chain,
proposed (inactive) coding child, integrity replay and negative mutation tests
for source-repo identity, unauthorized repo-write and forged receipt.

For each repository, the report also checks (without executing) whether the
source-pinned ESSENCE v1.3 organogenesis / peer inbox exist and whether their
own native GitHub Actions have a recent main-branch PASS, and notes the
presence of v1.2 real-algorithm or v1.0 model admission gates.

The job runs **only in GitHub Actions**, with contents:read/actions:read.
It neither reads or changes NAS, nor installs, trains, or promotes a model.
It cannot prove that currently deployed neural models are learning.

## Readiness levels

- **F0**: repo exists, origin SHA pinned.
- **F1**: six-role synthetic microkernel replays + mutation controls.
- **F2**: read-only module-governor research cycle verified by native CI.
- **F3**: peer research idea received with native CI and source chain.
- **F4**: genuine algorithm candidate evaluated on frozen data, research-only.
- **F5 (NOT ESTABLISHED)**: trained model checkpoint with repeatable training,
  proper quality/latency/RAM tests, independent untouched holdout.
- **F6 (NOT ESTABLISHED)**: two independently provisioned attestations,
  proper canary rollback against an actual checkpoint/service.
- **F7 (NOT ENABLED)**: review-authorized production model change with
  monitoring, rollback and clear criteria for halting automatic changes.

F1 success **does not mean F2-F7**, and F4 code presence does not mean
genuine learning. Signed declarations or self-hashed receipts do not
substitute for an independent custodian. Never silently replace the true
starting checkpoint or change working model weights during research.

## GitHub Actions

Workflow: `.github/workflows/essence-v14-fleet-audit.yml`.
Full JSON results are uploaded as the named `essence-v14-all-owner-repo-fleet-audit`
artifact. Partial results are retained even when the gate fails.

Data is public GitHub commit metadata and synthetic test receipts only,
not private deployment status. An unreachable GitHub endpoint produces an
explicit hold or incomplete finding rather than fabricated PASS.

Non-public connected repositories are assessed in their **own repositories' GitHub CI**; this public Meta Registry audit does not publish their names, commits, test data or paths. An independent success in a separate private repository is not counted among the 48 public successes.

## Central fallback for incomplete public repositories

When an otherwise pinned public repository does not yet carry its own `.janus/essence/fixture.json`, the central GitHub audit uses **exactly the known Git-blob-pinned synthetic fixture** from Meta Registry. The report marks `fixture_origin=PUBLIC_META_REGISTRY_FALLBACK_NOT_REPO_LOCAL` and counts such repos separately. Thus the six-role *contract* can pass independently, but that repo is still **not self-contained**. Native repository-level read-only CI must pass and be merged before the local fixture gap closes. Failures in an unrelated app build remain visible and are not bypassed by this audit.
