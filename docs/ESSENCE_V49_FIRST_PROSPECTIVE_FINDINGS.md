# ESSENCE v4.9 — first prospective continual-learning readout

**Run:** [GitHub Actions #43755360999](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43755360999)
**Source PR:** [#650](https://github.com/Hawkar-usls/Janus-Demiurge/pull/650)
**Outcome:** `HOLD_REPLAY_DID_NOT_CLEAR_PREDECLARED_GATES`.
This report records the first run **without changing any frozen threshold** or
running an adapted candidate on that same known examination.

## Evidence freeze before gradients

- Exact frozen contract in
  `research/essence/peer_v49/FROZEN_PROSPECTIVE_LOCK.json`.
- Separate exam-commitment job finished before baseline/replay training.
- Full exam payload SHA-256:
  `f1f0192dadc2cddec4db8d97f25993aaa7ddaf675e88e553f7c6c41e14a4c241`.
- Commitment receipt SHA-256:
  `d46e26002d28b9a92f44db1832b814f83350d053162f375699fcf2bf143eb081`.
- The training jobs read **only** Janus Lapis at the pinned source commit and
  verified factual memories; Cosmos and fresh route payloads were only
  downloaded into the subsequent read-only exam job.
- GitHub repository access means this was *operationally isolated*, **not**
  external custodianship or an independently secret dataset.

## Three model evaluation: exact correct answers

| Newly tested cohort | G2 parent | Naive (40 steps) | Replay+KL (40 steps) |
|---|---:|---:|---:|
| 16 freshly generated K/L routing identifiers | 15/16 | 8/16 | **16/16** |
| 6 new Cosmos repository fields | 0/6 | 0/6 | **1/6** |
| 6 paraphrased Lapis training properties | 0/6 | 0/6 | 0/6 |
| 8 paraphrased older verified facts | 0/8 | 0/8 | 0/8 |

## Per-token mean NLL (lower is better)

| Cohort | G2 | Naive | Replay+KL |
|---|---:|---:|---:|
| Fresh K/L tasks | 0.1574 | 0.4369 | **0.0474** |
| Cosmos | 6.2143 | 7.1852 | **6.2055** |
| Lapis paraphrases | 4.6708 | **1.9525** | 2.7333 |
| Older memory paraphrases | 4.8142 | 3.4087 | **3.2016** |

Old-skill retention has meaningfully improved for the specific original
synthetic route task: replay preserved 16/16 versus naive 8/16 and G2
15/16. But **new-source exact answers remained 0/6 for Lapis**, so the
predeclared functional-gain requirement was **not met**. That is why the
correct decision is `HOLD`, despite lower loss and one correct Cosmos fact.

Actual reported training wall time: naive **41.831 s**, replay+KL
**46.3808 s**, with different teacher computation and only equal numbers
of optimizer steps. Examination wall time was **83.7226 s**; installation,
queue delays and source checkout are additional resource costs.

## Scientific and security boundaries

This single internal experimental cohort demonstrates a promising technique
for retention, **not** multi-generation adoption or broad reasoning gain.
Replay and teacher KL were combined, so the result cannot distinguish their
individual contributions without a separately precommitted ablation.
Naive saw twice as many new-source gradient steps, creating a
stability/plasticity tradeoff in both training exposure and compute.

The prior G3 failures and this new holdout are now **seen development data**.
They cannot serve as clean independent evidence for later methods.
A next version requires a different previously unseen prospective test,
ideally administered by an external custodian and evaluated with cost-
matched, predeclared replay-only / KL-only / combined controls.

The original G2 in the isolated `essence-peer-shadow-state` branch,
native JANUS weights, Terminal Qwen 1.5B, all production services and
Sentinel A/B/C remain unchanged. No model admission was attempted.

Machine-readable receipt:
`research/essence/peer_v49/FIRST_PROSPECTIVE_READOUT.json`.
Full artifacts:
[exam receipt](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43755360999/artifacts/14178550146),
[replay adapter](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43755360999/artifacts/14178410253),
[naive adapter](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43755360999/artifacts/14177049345).
