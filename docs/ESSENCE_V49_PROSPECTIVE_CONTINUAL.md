# ESSENCE v4.9 — frozen prospective continual-learning exam

**Scientific classification:** `INTERNAL_PROSPECTIVE_SEPARATE_JOB`, **NOT**
`INDEPENDENTLY_REPLICATED` or `EXTERNALLY_VALIDATED`.
No native JANUS, active Terminal Qwen 1.5B, Sentinel, or production changes.

## Why this experiment

Three previous v4.8 G2→G3 trials correctly **failed** to preserve old exact
skills, even while the new-source language-model loss fell. The seen source
exams and their outcomes are **not** re-used as independent evidence or tuned
after the fact. The prior SHAs remain in the separate shadow-state ledger.

The new `peer_v49/FROZEN_PROSPECTIVE_LOCK.json` fixes these choices
*before the first v4.9 candidate trains*:

- Frozen G2 neural parent: real Qwen2.5-0.5B LoRA checkpoint
  `1ec5b21689ee5af6eec5345e0f5b91fc0870ffa520a56ef8778ce914ac28f3bc`.
- New learning source: public **janus-lapis** `PROJECT_STATUS.json`
  at Git commit `1d0ac3433b45296fa4d1636bf31ed25725663174` (six
  explicitly allowlisted scalar properties).
- New source for examination only: **Janus-Cosmos** `PROJECT_STATUS.json`
  at Git commit `1582ba6f4d818d434ef65743dc6992e8b3645fab`
  (six different approved properties).
- A fresh 16-example synthetic legacy-oracle retention cohort, with
  independently random suffixes excluded from the v4.6 training and holdout.
- Eight previously verified facts from HRain/Genesis as factual replay,
  plus eight old exact-oracle training examples from the original G1 lesson.

## Experiment protocol

1. **Pre-commit**: before either candidate trains, a separate Actions job
   reads *both* pinned source snapshots, generates sixteen new legacy
   identifiers, and saves `exam_payload.json` behind a SHA-256 commitment.
   The training jobs have read-only repo access, **no Actions-read
   permission**, and never download the exam artifact. This is practical
   isolation, **not** confidentiality from someone who controls GitHub and
   not an external independent custodian.
2. **Control (naive)**: exactly **40 AdamW LoRA optimizer steps**, all on
   the six fresh Lapis source-backed Q/A examples.
3. **Continual replay**: same 40-step starting checkpoint, seed and
   learning rate; scheduled 20 new facts / 10 old synthetic examples /
   10 verified memory examples. For the old synthetic examples the
   learner minimizes supervised loss **plus KL divergence from frozen
   pre-training parent logits** at fixed temperature 2 and coefficient
   0.4, to discourage overwriting the known K/L rule.
4. **Examination**: *after both model checkpoints are saved*, a separate
   read-only runner loads the previously committed payload, matches its
   SHA-256 and source commits, and compares G2 vs naive vs replay on
   never-used route suffixes, novel Cosmos facts, Lapis paraphrases
   and prior HRain/Genesis memory paraphrases.
5. **Predeclared research verdict**: replay must retain nearly all of
   the parent's fresh-route answers (drop no more than one), outperform
   the naive control by at least one correct fresh-route answer, obtain
   at least one additional exact correct Lapis paraphrase relative to
   G2, and not reduce exact correctness on Cosmos or memory. Failing
   any item means `HOLD`.
6. Report raw exact-count, NLL, cryptographic receipts, complete parent
   and both LoRA adapter hashes, and **actual** train + inference cost.

**Fairness qualification:** the two models use identical numbers of gradient
steps, **not identical compute**. Replay performs additional no-gradient
teacher forwards for KL supervision, so total wall-clock and normalized
compute cost must be compared. A better replay score does not imply
greater compute efficiency.

## What this does NOT do

- No re-tuning or multiple candidates selected after seeing the same
  future-exam set. Further runs are development, not first prospective proof.
- No claim that static public Cosmos is independently hidden, prospective
  tasks are external, or agreement of Qwen/SmolLM proves correctness.
- No changes to the existing v4.8 recurring production-independent
  shadow mechanism, checkpoints or admission thresholds.
- No automatic acceptance of any v4.9 results, even into the shadow
  lineage: independent external science verification remains HOLD,
  and real service rollout/rollback has not been performed.
- No model-generated code execution; the training objective only uses
  explicit allowlisted repository values and the verified old oracle.

Workflow: [v4.9 first prospective trial](https://github.com/Hawkar-usls/Janus-Demiurge/actions/workflows/essence-v49-prospective-continual.yml).

Source and result labels: `SELF_VERIFIED` or `INTERNAL_PROSPECTIVE`
are not `INDEPENDENTLY_REPLICATED` or `EXTERNALLY_VALIDATED`.
