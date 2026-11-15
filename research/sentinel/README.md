# JANUS SENTINEL · A/B/C redundant GitHub Actions guardians

**Intent:** special small, genuinely trained Transformer for GH Actions monitoring and bounded self-calibration; two interchangeable guardian roles A/B, third C repairs one of them; A/B monitor C. The source `tools/sentinel_core.py` is identical for all roles. C is intentionally deterministic and independent of Torch.

## Roles and cadence (UTC, GitHub best effort)

| Workflow | Role | Cron | Watches and may safely dispatch |
| --- | --- | --- | --- |
| `sentinel-node-a.yml` | A / Alpha | :07, :22, :37, :52 every hour (**15 minutes**) | B, C, ESSENCE v4.4 worker |
| `sentinel-node-b.yml` | B / Beta | :12, :27, :42, :57 every hour (**15 minutes**) | A, C, ESSENCE v4.4 worker |
| `sentinel-node-c.yml` | C / Custodian | :02, :17, :32, :47 every hour (**15 minutes**) | A or B |
| `sentinel-train-transformer.yml` | shared A/B trainer | :19, :49 every hour (**30 minutes**) | Research candidates only; **no dispatch** |
| `sentinel-forward-calibration.yml` | shared model temperature | :14, :44 every hour (**30 minutes**) | 64/64 prospective gate; no changed weights |
| `sentinel-cadence-audit.yml` | independent *workflow* observer | :11, :41 every hour (**30 minutes**) | 24-hour real scheduled heartbeat PASS/HOLD/FAIL; no dispatch |

Each wrapper uses `sentinel-shared-guardian.yml`, but has its own workflow identity, cron and concurrency. Resuming a fallen node is an explicit, restricted `workflow_dispatch` with `recovery_only=true`; the recovered workflow can only observe, never trigger another recovery chain.

## Genuine neural subsystem

`tools/sentinel_transformer.py` trains **all parameters** of a 1-layer 2-head causal self-attention Transformer (16-d hidden), PyTorch CPU. Supervision: actual dated GitHub Actions completed run success/failure labels; input: eight PREVIOUS workflow outcome/duration/event tokens and the NEXT known workflow ID bucket, never the future outcome. Chronological train/calibration/test splits (65%, 17%, 18%); AdamW 30 steps and selected temperature (0.5–4.0) minimizing calibration Brier. Final chronological test compares Brier and ECE with a Laplace-smoothed constant-prior baseline. Failures and negatives remain visible.

The first verified real checkpoint is persisted in **`sentinel-state/sentinel/model/checkpoint.json`**. Both A/B load EXACTLY the same weights and temperature for LIVE research failure-risk inference on latest GitHub run history. No weights training in A/B guardian runs. Follow-up half-day trainer writes bounded **candidate** weights; it DOES NOT automatically replace the shared checkpoint on already-read benchmarks. Real neural forecasts may prioritize human inspection but never authorize/forbid a dispatch, overwrite code, change model-served production weights, or bypass deterministic recovery rules.

## Recovery invariants

- Exact same-repo allowlist: `sentinel-node-a.yml`, `sentinel-node-b.yml`, `sentinel-node-c.yml`, and `essence-v44-github-async.yml` (pulse only).
- A/B truly interchangeable **controller source**. Either can observe the peer or rescue C. C does not depend on the trained neural weights and can dispatch one failed A/B node per run.
- No recovery on never-seen workflow, missing GitHub API data, pending/in-progress jobs or after transient failure under **6 minutes**. A/B/C are considered stale after **40 minutes** of missed runs (allowing >2 cron opportunities); the ESSENCE worker retains **65 minutes** to avoid unnecessary worker dispatches. A failed GitHub cron alone is not proof of an outage; this is a bounded heuristic.
- Global per-target cooldown **30 minutes**. New tests enforce the 29/30-minute boundary, separate worker liveness and B→C real-evidence attribution. Every permitted dispatch requires an **atomic, non-force Git push** of `sentinel-state/sentinel/recovery.json` with expected epoch; if simultaneous A/B/C claims race, loser fails closed and never dispatches.
- On successful claim, recheck remote workflow's newest run ID BEFORE dispatch. If target revived in the meantime, cancel dispatch. Outcome is marked `ATTEMPTED_NOT_CONFIRMED`, never `RECOVERED` until a later independent run/observation.
- Worker `pulse` can be dispatched only when there is unprocessed public queue work and the worker itself is stale, with same cooldown, and A/B cannot launch arbitrary workflow names.
- Synthetic fault-injection tests cover A missing, B missing, C missing, both A/B missing, any unknown workflow, race/CAS conflict, cooldown, concurrent live worker and GitHub common outage.

## Hard limitations

All three jobs and the model trainer share the **GitHub** platform, authorization token, repo and scheduled event service. If GitHub itself, the repository, token, or `sentinel-state` is unavailable, **all three may fail**. A GitHub Actions cron is best effort and cannot sustain a permanent 24/7 process. A disabled/deleted workflow generally cannot be revived by a dispatch while disabled, and token policies/branch protection may reject writes; an authorized human operator must then intervene.

Before any automatic dispatch we require a target workflow that was PREVIOUSLY observed healthy. The first post-merge cycles intentionally record `UNKNOWN_NO_OBSERVATIONS` and do not fabricate a repair.

Model quality on internal chronology cannot certify external validation, and a Sentinel control-plane success cannot certify that existing ESSENCE G4 neural descendants outperform 14-step control. The G4 Physarum remains research shadow, production and live model promotion remain **HOLD**.

### Emergency stop
Set GitHub repository variables `SENTINEL_PAUSED=true` (all guardian/trainer jobs skipped) or `ESSENCE_EVOLUTION_PAUSED=true`; or disable Sentinel workflows. Do not store any private prompt or secret on this public data branch. Only minimal GitHub run metadata is processed. Default evidence retention for Actions artifacts is 30 days, backed by Git state.

### Evidence
- Code: `tools/sentinel_core.py`, `tools/sentinel_transformer.py`.
- State-only branch: `sentinel-state`, `sentinel/recovery.json`, shared trained checkpoint and candidates.
- Tests: `tests/test_sentinel_core.py`, `tests/test_sentinel_transformer.py`.
- GitHub Actions wrappers for A/B/C and shared runner, plus training workflow.
- **Certification ladder:** SYNTHETIC_TESTED → GITHUB_ACTIONS_BOOTSTRAP → REAL_TRAINED_CHECKPOINT → FENCED_RECOVERY_IN_ISOLATED_FAULT_TEST → REAL_GITHUB_DISPATCH_RECORDED (only after genuine controlled fault recovery).

Status should never be raised without corresponding run IDs and inspected artifact receipts.

## Minute-cadence acceptance gates (November 2026)

The initial real GitHub Actions drills proved **C→A→B** and **A→C**, but not
**B→C**. The new one-shot `sentinel-real-b-rescues-c-drill.yml` triggers from
`research/sentinel/locks/b-to-c-minute-one-shot-lock.json` after merge, waits
only for a *real existing* C cooldown claim (no fabricated time), injects one
C-only failure, requires a new CAS claim **issued by B**, and verifies an
entirely new successful C run with exact recovery nonce. It emits
`PASS_REAL_GH_B_RESCUES_C` or explicit HOLD; pending runs do not count.

`sentinel-cadence-audit.yml` collects real `event=schedule`, `main`,
completed/success metadata for each A/B/C role. Its 24-hour gate cannot PASS
until at least 24 hours after this policy's actual Git commit and then only if
at least 77 of 96 expected wakes succeeded per role, with no gap exceeding
45 minutes. `push`, `pull_request`, and manual dispatches are excluded.
A one-shot passing drill is **not** 24-hour reliability. This is GitHub-local
observation, not independent verification or guarantee against platform outages.

Model training cadence is shorter, but **every trainer run still creates a
research candidate**, not an accepted descendant. Forward-only temperature
calibration retains its unmodified 64/64 data requirement. No automatic
promotions of working JANUS weights or open-ended launches are enabled.
Scheduled job delivery, budgets and limitations must be observed over time.

## Prospective shared neural-weight descendants

`sentinel-train-transformer.yml` still trains real PyTorch attention weights
every 30 minutes as research candidates. It now stages **at most one**
SHA-256-sealed `sentinel/model/pending-challenge.json` pointing to the
parent checkpoint and an immutable child candidate created in the same
trainer commit. Later candidates remain shadow while this challenge is live.

`sentinel-weight-prospective.yml` checks that challenge every 30 minutes,
without installing Torch until there are **128** genuinely new *post-Git-freeze*
completed, chronological `schedule`/`push` GitHub outcomes. Controlled
`workflow_dispatch` failures and PR checks are excluded. The first 64
unseen labels form prospective confirmation A; the next 64, untouched
confirmation B. Both must separately produce paired Brier gain >=0.001,
ECE <=0.20, non-degenerate failure labels, at least six workflow families,
and bounded inference time. No later outcomes can influence earlier inputs.

If and only if both gates pass, the exact model parent is archived, the
new weights are promoted to the **A/B research-only** checkpoint via a
non-force Git CAS and the result receipt is sealed. Otherwise the candidate
is retired once with a durable HOLD receipt; subsequent training may propose
a new candidate but cannot reuse the old forward evaluation to certify it.
All three guardians' hard dispatch policy is unchanged, C remains
Torch-independent, and **working JANUS model promotion remains blocked**.

An unsuccessful CAS race is an explicit `HOLD`, never fictitious
recoveries or promotions. Even a prospective internal PASS is
`SELF_VERIFIED`, not independent external scientific validation.
