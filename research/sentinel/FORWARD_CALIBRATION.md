# JANUS SENTINEL · prospective self-calibration of A/B risk Transformer

This adds a **real, bounded, GitHub-only self-calibration mechanism** to SENTINEL A/B. It is independent of the A/B/C failover drill.

**Current model:** Both A/B already load the same trained frozen Tiny Transformer from the data-only `sentinel-state/sentinel/model/checkpoint.json`. C does not use PyTorch. Their neural output is advisory and cannot grant GitHub workflow dispatch authority.

## How calibration works

Every 6 hours, an Actions workflow records the current data-only checkpoint's true Git **commit timestamp** and fetches authentic public completed GitHub Actions runs through a read-scoped token. The first 128 new eligible outcomes created AFTER the checkpoint seal (or last evaluation cursor) are fixed and divided chronologically:

- **64** for temperature selection from a frozen list `[0.25,0.5,0.75,1,1.25,1.5,2,2.5,3,4]`. No neural gradients or model-weight change.
- **64** untouched outcomes for prospective evaluation of the parent vs the selected temperature using Brier score and expected calibration error. There must be at least one real failure and one success in each cohort and at least 6 distinct workflow-family buckets overall.
- The input is eight previous run outcomes and the workflow ID of the target. The **future target label is never in its own context**.

The model scores both temperatures on the **same** future examples. Promotion happens only for a paired Brier improvement >=0.001 and ECE not exceeding 0.20 or worsening baseline ECE by >0.01. Loss and ECE criteria were frozen in code BEFORE new outcomes were read.

Every full cohort — positive **or negative** — advances a SHA-256 sealed **one-pass cursor**. Duplicate timestamps disambiguate by immutable run ID. If a runner misses too many runs to reconstruct the ordered future cohort, the gate stops rather than silently dropping tasks.

If positive, workflow saves the previous complete model checkpoint to `sentinel/model/parents/<old-sha256>.json` and updates only `temperature` and provenance metadata of the shared **research** A/B checkpoint. The exact complete neural weights remain byte-for-byte identical. C continues with deterministic code. Git non-force push of the cursor and weights is an atomic CAS: an intervening write results in an explicit failure with no retry-based blind overwrite.

The 12-hour separate trainer still produces **new neural weight candidates** but never automatically accepts them based on previously seen holdouts. This six-hour gate is exclusively forward-only temperature recalibration of the currently accepted research model.

## Constraints

- No permanent process, SLA or 24/7 service promise. GitHub cron is best effort, could be delayed or dropped, and GitHub-wide failures affect A/B/C.
- No auto-promotion of production JANUS or ESSENCE G4 weights, no arbitrary workflow dispatch, no cross-repo modifications.
- Prospective internal GitHub source evaluation is stronger than retrospective development checks, but **NOT externally independent science replication**.
- Small cohort statistics can fluctuate and a nominal Brier improvement is not proof of broad generalization; negative results remain immutable.

### Evidence and workflow

[GitHub workflow](https://github.com/Hawkar-usls/Janus-Demiurge/actions/workflows/sentinel-forward-calibration.yml)

Source: `tools/sentinel_forward_calibrate.py`; tests `tests/test_sentinel_forward_calibrate.py`. Evidence in `sentinel-state/sentinel/calibration/receipts`, calibration cursor, and Actions artifacts. Manual run via GitHub Actions is available; cron: `17 */6 * * *` UTC.

**Ready gates:** unit-test pass; real first-main readiness run; actual non-overlapping 128 future target source and one exact evaluation; verification of synchronized A/B checkpoint hash after temperature update. No claim until observed.
