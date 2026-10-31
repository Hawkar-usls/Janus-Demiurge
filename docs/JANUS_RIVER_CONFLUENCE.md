# JANUS River Confluence — Demiurge intake of the brain and scientific rivers

## Why one intake, not a second P-vs-NP solver

`Janus-Demiurge` already runs `janus-pnp-autoresearch.yml` every two hours,
which fetches Fundamentum and supervises candidates with a strict promotion
barrier; `Janus-Demiurge` also already consumes Beetle memory through its
existing receipt-checked path. TOPA independently runs falsification research.

This bridge **does not duplicate or replace** these processes. Its task is to
bring independent source identities and upstream GitHub Actions delivery
metadata into one bounded read-only Demiurge observation report.

## Upstream architecture

```text
Demi_Head   AIFC   Janus   janus-io-public
   \         |      |        /
        janus-distributed-ai-swarm
       (GitHub Actions Face Bus / ACK)
                     |
             Demiurge Confluence
                     |
           EXISTING P-vs-NP supervisor
            /         |         \
    Fundamentum      TOPA       Lapis/Beetle
      (theory)     (falsify)    (discover)
                     |
          existing receipt-checked memory
```

The SHA-pinned Brain Five and their independent peer ACK system are deployed
in `Hawkar-usls/janus-distributed-ai-swarm` (merged PRs #21, #22 and #23).
That system runs GitHub Actions workers, **not five live LLMs**.

## What the intake actually checks

- Fetches exact current Git `main` commits from five approved brain repos.
- Reads one size-bounded public contract file per repo using the immutable
  commit SHA; checks expected schemas for AIFC and I0.
- Re-reads the frozen Swarm five-Face allowlist and its zero-permission policy.
- Observes the latest successful Brain Five workflow at the **same Swarm HEAD**;
  requires 5 observe jobs, 5 receive jobs, a route job, a plan job, the
  independent Witness job and expected non-expired artifact names.
- Reads immutable Git source files in Fundamentum, TOPA and janus-lapis,
  recording their SHA-256 digests and their **current scientific boundary**:
  `P_VS_NP_OPEN`, TOPA `p_vs_np: OPEN`, Beetle discovery ≠ proof.
- Re-validates Demiurge's own research supervision policy:
  `p_vs_np_auto_promotion: false`,
  `fundamentum_mutation: false`,
  `autonomous_merge: false`.
- Emits a JSON artifact with exact source commits, document SHA-256s, run
  metadata, HOLD decisions and explicit claim ceiling.

The workflow runs after the Swarm's configured 04:23 UTC daily cycle, at
05:49 UTC. GitHub Actions schedules are best effort and may be delayed.
It also tests the code on PRs, main-branch changes and manual runs.

## Explicit non-claims and hard safety limits

- An Actions `success` and artifact name do **not** attest to the artifact's
  bytes. This v1 does not download or replay cross-repo artifact ZIP bodies.
- A historical successful run is accepted only when its HEAD equals the
  currently observed Swarm HEAD. An absent/currently stale run returns HOLD.
- Re-reading a contract at its exact SHA does not itself prove its claims.
- GitHub failures, unknown Face identities, missing or forged source schemas,
  missing final Witness jobs and scientific status drift fail closed.
- The bridge invokes no LLM/Copilot, Rowan, local shell from remote source,
  remote workflow dispatch, target repository write, scientific promotion,
  automatic merge or change to the Beetle direction.
- The report is a GitHub Actions artifact kept for 14 days, **not** persistent
  Meta Registry memory. A verified append-only registry importer is needed for
  cross-run durable memory; it must not ingest unverified claims as truth.
- The existing P-vs-NP supervisor remains owner of hypothesis generation and
  bounded falsification; general polynomial-time correctness and complexity
  bounds, independent proof checking and unrestricted Exact-One coverage
  remain open.

## Verify

```bash
python -m unittest -v tests/test_janus_river_confluence.py
python tools/janus_river_confluence.py --out runtime/river-confluence/JANUS_RIVER_CONFLUENCE.json
```

The workflow's `READ_ONLY_INTAKE_OK` status means source contracts and
run/artifact **metadata** were observed under their stated checks. It does
not mean new knowledge, machine intelligence, scientific proof, or full JANUS
autonomy has been achieved.
