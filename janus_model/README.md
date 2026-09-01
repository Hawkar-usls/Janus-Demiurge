# JANUS Native Model

This directory is the native neural plane of JANUS.

## Organism map

- `janus-meta-registry` — long-term training memory and provenance source.
- `EYE` corpus contract — source/derivative firewall used before neural ingestion.
- `janus_model/model.py` — JANUS byte-level causal Transformer.
- `janus_model/checkpoints/promoted.pt` — currently promoted learned weights.
- `janus_model/receipts/` — immutable-ish training/evaluation receipts in Git history.
- GitHub Actions — launcher, trainer, evaluator and persistence runtime.
- Other JANUS repositories — bounded organs; their own authority contracts remain in force.

## Native launcher

After the first promoted checkpoint exists:

```bash
python -m janus_model.cli inspect
python -m janus_model.cli run --prompt "JANUS, what do you remember?"
```

The GitHub workflow `JANUS Native Model` exposes the analogous modes `train`, `run`, `train_and_run`, and `inspect` through `workflow_dispatch` and also performs bounded scheduled learning when the meta-registry source digest changes.

## Learning law

`META-REGISTRY -> EYE FIREWALL -> TRAIN/HOLDOUT -> CANDIDATE WEIGHTS -> EVAL -> PROMOTE OR REJECT -> NATIVE INFERENCE -> RECEIPT`

Registry text is memory material, not automatic truth. A candidate may replace the incumbent only through the holdout promotion gate. Native training and inference do not call Copilot, OpenAI, Anthropic, Gemini, Ollama, or another model provider.

The initial architecture is deliberately small enough for a GitHub-hosted CPU runner. Structural architecture mutation is a later gated stage; v1 self-development is continued native-weight learning with regression-safe promotion.
