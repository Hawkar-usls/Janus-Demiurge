# JANUS SENTINEL · A/B/C redundant GitHub Actions guardians

**Intent:** special small, genuinely trained Transformer for GH Actions monitoring and bounded self-calibration; two interchangeable guardian roles A/B, third C repairs one of them; A/B monitor C. The source `tools/sentinel_core.py` is identical for all roles. C is intentionally deterministic and independent of Torch.

## Roles and cadence (UTC, GitHub best effort)

| Workflow | Role | Cron | Watches and may safely dispatch |
| --- | --- | --- | --- |
| `sentinel-node-a.yml` | A / Alpha | :07, :37 each hour | B, C, ESSENCE v4.4 worker |
| `sentinel-node-b.yml` | B / Beta | :22, :52 each hour | A, C, ESSENCE v4.4 worker |
| `sentinel-node-c.yml` | C / Custodian | :12, :42 each hour | A or B |
| `sentinel-train-transformer.yml` | shared A/B trainer | :49 every 12h | Trains only; **no dispatch** |

Each wrapper uses `sentinel-shared-guardian.yml`, but has its own workflow identity, cron and concurrency. Resuming a fallen node is an explicit, restricted `workflow_dispatch` with `recovery_only=true`; the recovered workflow can only observe, never trigger another recovery chain.

## Genuine neural subsystem

`tools/sentinel_transformer.py` trains **all parameters** of a 1-layer 2-head causal self-attention Transformer (16-d hidden), PyTorch CPU. Supervision: actual dated GitHub Actions completed run success/failure labels; input: eight PREVIOUS workflow outcome/duration/event tokens and the NEXT known workflow ID bucket, never the future outcome. Chronological train/calibration/test splits (65%, 17%, 18%); AdamW 30 steps and selected temperature (0.5–4.0) minimizing calibration Brier. Final chronological test compares Brier and ECE with a Laplace-smoothed constant-prior baseline. Failures and negatives remain visible.

The first verified real checkpoint is persisted in **`sentinel-state/sentinel/model/checkpoint.json`**. Both A/B load EXACTLY the same weights and temperature for LIVE research failure-risk inference on latest GitHub run history. No weights training in A/B guardian runs. Follow-up half-day trainer writes bounded **candidate** weights; it DOES NOT automatically replace the shared checkpoint on already-read benchmarks. Real neural forecasts may prioritize human inspection but never authorize/forbid a dispatch, overwrite code, change model-served production weights, or bypass deterministic recovery rules.

## Recovery invariants

- Exact same-repo allowlist: `sentinel-node-a.yml`, `sentinel-node-b.yml`, `sentinel-node-c.yml`, and `essence-v44-github-async.yml` (pulse only).
- A/B truly interchangeable **controller source**. Either can observe the peer or rescue C. C does not depend on the trained neural weights and can dispatch one failed A/B node per run.
- No recovery on never-seen workflow, missing GitHub API data, pending/in-progress jobs or after transient failure under 10 minutes. Stale after 65 minutes of missed runs, or completed failure beyond 10 minutes with prior success. A failed GitHub cron alone is not proof of an outage; this is a bounded heuristic.
- Global per-target cooldown 90 minutes. Every permitted dispatch requires an **atomic, non-force Git push** of `sentinel-state/sentinel/recovery.json` with expected epoch; if simultaneous A/B/C claims race, loser fails closed and never dispatches.
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
