# ESSENCE v4.4 — GitHub Actions native asynchronous model inference

## Reality: a logical service, NOT a continuously running process

GitHub-hosted Actions jobs are **ephemeral** (each job ends, maximum 6 hours).
Scheduled events run no more often than every five minutes, are best effort,
may be delayed/dropped, and public-repo schedules can be disabled after
60 days with no activity. There is no guaranteed 24/7 HTTP listener solely
inside GitHub-hosted Actions. For a real always-on API, a separately
operated host or self-hosted runner plus a service deployment is needed.

This v4.4 implementation keeps the *application state and async request
queue* alive in GitHub, not a permanent process. Each wake continues work
from immutable previous results. No external host/NAS/Vercel is involved.

## Workflows

- .github/workflows/essence-v44-seal-g4-store.yml: on trusted main/push
  bootstraps two exact original research checkpoints from Actions artifacts
  into permanent branch essence-actions-state/model-store, checking every
  FP32 weight hash and signed-by-structure manifest hash. There is no pickle.
- .github/workflows/essence-v44-github-async.yml: main branch scheduled
  at 3,8,13,...58 minutes past each UTC hour (best effort) and manually
  via workflow_dispatch. It checks the queue without installing PyTorch
  when idle; up to four requests per wake are scored with one model load.
  Commits immutable SHA-verified results to the data branch and ends.

## Submit tasks (two options)

1) GitHub Actions > ESSENCE v4.4 GitHub-native asynchronous model worker >
   Run workflow > mode=infer, input_hex= exactly 48 hex characters encoding
   a **nonprivate** 24-byte byte-level prompt. E.g. the 24-byte text
   def f(x): return x + 33 followed by newline:
   64656620662878293a2072657475726e2078202b2033330a.

2) On branch essence-actions-state, add a fresh, unique file
   essence-runtime/inbox/demo-001.json using:

    {
      "schema":"janus.essence.github_async_request/4.4",
      "request_id":"demo-001",
      "input_hex":"64656620662878293a2072657475726e2078202b2033330a"
    }

Every valid job yields essence-runtime/results/demo-001.json.
Direct workflow_dispatch yields results/dispatch-RUN-ATTEMPT.json.
All result names are immutable; malformed requests are rejected and recorded.
A job can be triggered manually for immediate queue processing (mode=pulse).
GitHub's workflow-run UI and summaries provide per-wake observability.

## Scientific and production safety

- Active experimental model ALWAYS fixed 14-step G4 control.
- Frozen Physarum G4 receives the same context as a **shadow**; its output
  is research data only, not deployed to the JANUS real model or any API.
- A preexisting 14-step control **beat Physarum** on known development tasks.
- No training, automatic promotion, state branch code execution, unpickling,
  production routing, cross-repo dispatch or external network services.
- All four-byte-accurate FP32 checkpoint digests are hardcoded and checked.
- The external independent scientist/closed exam remains missing.

## Reliability/operational constraints

- Cron wakes are not service uptime and may be late; a missing wake does
  NOT imply healthy service. GitHub Actions is a **job processor**.
- Pending work is data in a separate branch, immune to runner replacement.
- Maximum four tasks per wake, maximum 1000 queue file scan entries.
- Every successful job writes append-only response JSON and run receipt.
- Concurrency serializes scheduled wakes; direct workflow_dispatch jobs
  have unique run IDs and retry rebases on any branch conflicts.
- GitHub state branch can be recovered from its Git history; no destructive
  rewrites, no delete of original requests, no force push.
- GitHub Actions job history and artifacts may be expired; model checkpoints
  are also in versioned Git data branch so the worker is not dependent on
  90-day model artifacts after initial source-verified bootstrap.
- Cron at 5-minute intervals uses substantial workflow invocations;
  repository owner can disable workflow or set repository variable
  ESSENCE_EVOLUTION_PAUSED=true. Costs/quotas remain GitHub-dependent.

## Verification milestones

1. Unit/negative-contract tests pass on PR.
2. Main bootstrap action persists both unchanged model checkpoints.
3. Scheduled or manually queued wake verifies config and processes input.
4. Real workflow_dispatch must yield a research receipt with both FP32
   next-byte predictions, but baseline14 only is marked active.
5. LIVE_PRODUCTION_ROLLBACK remains HOLD; v4.3 only proved isolated runner
   HTTP rollback. Independent scientific Physarum gain remains HOLD.

Reference: https://docs.github.com/en/actions/reference/limits
Reference: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
