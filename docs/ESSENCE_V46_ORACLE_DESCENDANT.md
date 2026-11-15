# ESSENCE v4.6 — first real Qwen descendant (synthetic-oracle development lane)

**Scope:** Validate actual neural weight inheritance, changed LoRA adapter tensors,
a sealed train/holdout split, and an isolated paired parent-vs-child examination.
**Not scope:** Learning from the unreviewed Qwen/SmolLM dialogue archive, independent
scientific validation, or automatic production promotion.

## Parent

- `Qwen/Qwen2.5-0.5B-Instruct` (Apache-2.0)
- Frozen revision `7ae557604adf67be50417f59c2c2f167def9a775`,
  recorded by JANUS Qwen real inference on Terminal run
  [#43734382594](https://github.com/Hawkar-usls/-Terminal-for-Janus/actions/runs/43734382594).
- Base weights are frozen. Trainable tensors are LoRA query/value adapters only.
- CPU FP32, seed 4601, 20 steps, AdamW at 0.0015, rank 4.
- The adapter is saved in `safetensors` along with hashes and training cost.

## Why this fixture exists

The actual [JANUS dialogue archive](https://github.com/Hawkar-usls/-Terminal-for-Janus/tree/janus/open-llm-corpus)
contains **four** source-verified dialogues and **no** independently approved
training labels as of the initial freeze. Training on their unverified answers
would make the system worse while reporting spurious success.

Instead this lane uses a **synthetic** exact-checkable toy task where the
first character of a new arbitrary code determines one of two response tokens.
It does not teach JANUS science, solve real customer tasks, or validate peer
model learning. It is a minimal *neural lineage + exact paired-exam* smoke test.

## Reproducibility and leakage control

```
main code & lock (fixed seed, 32 train, 16 unseen holdout)
   ↓
freeze-oracle-cohort (two programmatic checkers agree; SHA-256 receipt)
   ↓
train-real-lora (train split only, no test bytes; hash frozen child tensors)
   ↓  upload artifact
independent-job-paired-exam (new runner; holdout generated only now)
   ↓
parent-vs-child token NLL + deterministic exact-output score, by family K/L
```

Thresholds frozen before the initial run: heldout token NLL improvement at
least 0.02; neither family allowed to regress more than 0.035; exact answer
accuracy must not decrease. A test failure is kept as a failure, not retuned
after seeing heldout samples. Report parent and child NLL, accuracy, SHA
lineage and total wall clock training + test costs. An independent **job**
does not constitute an independent **human examiner**.

The independent prospective examiner, private task holdout, permissioned
staged deployment, full rollback, and G4/G5 evidence remain **HOLD**.

## Hard boundary

This workflow has **contents:read only**; it cannot edit repos, trigger
Sentinel A/B/C, change native JANUS weights, or deploy models. It creates
research-only Actions artifacts; no resulting adapter is automatically
admitted. The proper [v4.5 peer dialogue training gate](../research/essence/peer_v45/shadow_lock.json)
remains unchanged, blocked without at least 32 reviewed pairs from 8 distinct
issues plus a genuinely external pre-committed examination.

First execution: [ESSENCE v4.6 workflow](https://github.com/Hawkar-usls/Janus-Demiurge/actions/workflows/essence-v46-oracle-descendant.yml).
