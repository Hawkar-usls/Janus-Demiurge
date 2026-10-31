# DADDY_KEYMASTER Dynamic Compute Pool · R0 (SEALED)

## Owner intent

One queued JANUS task per authorized execution worker. After a **verified**
terminal receipt, release the capacity and consider the next queued task.
Rotate placements across permitted machines according to historical usage,
rather than pinning an agent to a server. The queue must survive worker death.

**GitHub-hosted runners are ephemeral per Actions job**: GitHub, not the broker,
chooses the physical VM. A completed GitHub worker is gone. A future project
workflow may receive a new runner, but no user-controlled GitHub VM can be
retained, handed off, or used as an always-on AI service.

## What this PR actually provides

- A deterministic and SHA-bound **offline** planning preview that considers
  owner-authorized *currently* observed workers, task priorities, CPU matching,
  per-provider concurrency guards, a global R2 ceiling of 2 and historical
  usage for fair selection.
- Each worker can appear in **at most one** proposed task assignment.
- LEASED means never silently start another copy. Expired leases stay
  HOLD_EXPIRED_LEASE_RECONCILE pending a trusted, idempotent outcome check.
- Terminal COMPLETE tasks are skipped and do not occupy capacity.
- Task admission is limited to bounded public/synthetic, non-secret, non-shell
  project work. No arbitrary code from a queue or remote host discovery.
- Example data is **synthetic** and deliberately not a persistent operational
  queue.

The preview **never** dispatches, creates a runner, issues leases, updates
weights, changes provider permissions, or spends external credits.
MAX_PARALLEL=2 and current provider policy remain unchanged.

### Try locally (read-only)

~~~sh
python -m unittest discover -s tests -p test_daddy_keymaster_dynamic_pool.py -v
python -m daddy_keymaster.dynamic_pool --out daddy-output/ROTATION.json
~~~

Inside the currently running GitHub Actions job only, the broker may observe
its own GitHub runner. Outside that job, the roster correctly offers zero
persistent GitHub capacity. A plan result is **not** evidence that a VM was
reserved or that a job finished.

## Next production milestones (not claimed by this preview)

1. Define durable queue transitions (QUEUED -> LEASED -> COMPLETE / HOLD) in an
   independent store with exact-state compare-and-swap, monotonically
   increasing epochs and tamper-evident receipts.
2. Authenticated provider-specific dispatcher adapters, allowing **only**
   repo-relevant development/test/release Actions jobs; Oracle/BOINC/Ray only
   for explicit owner-authorized resources and per-provider allowed workloads.
   No public machine hunting or provider/account rotation to avoid quotas.
3. Leases with heartbeat, cancellation, duplicate reconciliation, retries
   with backoff, checkpoint-resume, bounded task cost, and per-worker failures.
   In particular, a timeout is **not** evidence the previous worker stopped.
4. Separate coordinator (on owner-controlled permitted infrastructure) from
   ephemeral workers. The coordinator must observe GitHub's own concurrency,
   quotas, pricing, job queues and Terms; it must not self-requeue GitHub
   Actions to emulate a persistent hosted server.
5. Keep the native-model production champion promotion sealed until issue
   #385 and security draft #301 are independently closed with authentic
   blind final evaluation, secure loader, exact consumer ACK and rollback.
6. After that, perform a measured **2 -> 4** capacity trial, then gradually
   adapt to actual authorized provider capacity under explicit ceilings.
   Reserved evaluation capacity must remain independent from training.

No production queue, dispatch, new cloud account, or unlimited compute is
activated by this document or by a green CI run.
