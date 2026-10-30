# JANUS DADDY_KEYMASTER — native-model calibration on short-lived cloud CPUs

The existing JANUS native transformer (`janus_model/model.py`) already has
a verified incumbent checkpoint (`janus_model/checkpoints/promoted.pt`),
an hourly native weight learning loop and protected promotion gates.
This organ **does not replace** or reset those mechanisms.

## Cloud trial

The `JANUS DADDY_KEYMASTER Native CPU Calibration` workflow schedules one
wave each day at **04:23 UTC** (plus PR/source-change checks and manual dispatch).
It uses only standard GitHub-hosted VMs in the owner's public repository:

1. **Corpus preparation:** build the same registry+Keymaster corpus as the
   canonical native learning loop, preserving source commit, source digest and
   frozen adaptive/anchor evaluation contract. Fail closed if sources missing.
2. **Two real native-model CPU workers:** one x64, one ARM64, each loading and
   **running inference on actual promoted JANUS weights**, then exploring one
   short training continuation from the same source-pinned incumbent (32 and
   48 steps; different fixed seeds). Workers never update main.
3. **Independent verifier:** load and re-score *only* hash-pinned candidate
   checkpoints; compare with incumbent using JANUS's **existing**
   `promotion_gate` on both holdouts. Require meaningful improvement with
   protected non-regression; if no candidate passes, report
   `INCUMBENT_RETAINED`. A promising result is
   `BEST_CANDIDATE_REVIEW_ONLY`, **not** an installation.
4. **Isolated durable archive:** hash-verified verdicts and source SHA written
   to `janus/daddy-keymaster-state/daddy_keymaster/state/native/`, not main.
   PR workflows remain read-only. Training payloads retained 3 days, audit
   receipt 14 days.

The previous `janus-native-model.yml` workflow remains the *only* author of
canonical `promoted.pt` under its own gates and concurrency. If a DADDY
challenger wins, it must still pass a separate integration/review gate and be
compared against the **latest** authoritative main checkpoint. No stale base
is allowed to overwrite newer main weights. Until integrated, the canonical
runtime continues loading its last properly promoted checkpoint.

## Limits

- At most two exploratory CPU VMs per wave; up to 17 minutes each including
  setup. No GPUs, paid runners, cloud account creation, self-requeue, quota
  evasion, arbitrary externally-provided Python or unbounded scaling.
- Strictly own Transformer weights; no Qwen, Copilot or external API used
  in native training/inference.
- The benchmark measures held-out token prediction loss. Lower loss is
  not by itself proof of general intelligence, useful downstream behavior
  or scientific insight.
- A successful workflow with `INCUMBENT_RETAINED` is **correct**: no
  degraded checkpoint is promoted.
- `BEST_CANDIDATE_REVIEW_ONLY` indicates an independently measured *proposal*,
  not that every JANUS service has adopted that model.
- Continual improvement is an empirical target; it is impossible to
  guarantee every iteration yields a better model.

See the already installed `janus_model/eval_contract.py` and
`janus_model/train_registry.py` for exact metric and gate rules.
