# JANUS Ocean ← Tachyon research-only inbox

This **new sidecar consumer**, `experiments/ocean_transformer/tachyon_review_consumer.py`, is additive and has no modifications to existing Ocean experiment preparation, scoring, or model training.

The upstream producer lives in `Hawkar-usls/Demi_Head`, under `tachyon/ocean_link.py`. The first proof-of-exchange uses a GitHub-published **128-bit precommit for November 12, 2026** from actual Ocean workflow run [42878578752](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/42878578752), preserved as a SHA-linked, no-authority review. This historical receipt is distinct from a future score or any alleged retrocausal channel. The source model is a real `JanusTinyTransformer`; Tachyon's semantic and Lorentz heads do not run on drand bits.

```text
JANUS Ocean early_009b  ──>  DemiHead Tachyon read-only shadow audit
                                             │
                                  TOPA HYPOTHESIS_ONLY
                                             │
                              SHA-bound research review
                                             │
                                             ▼
                                  Ocean research inbox
                              (non-gradient candidate questions)
```

The importer checks the exact Tachyon receipt digest, original Ocean code commit, 128-round precommit identity, question caps, TOPA hypothesis-only status, nonpromotion flags and lack of model training authority. It outputs `janus.ocean.tachyon_research_context.v1` with only two bounded research questions, provenance and refusal of writeback privileges. It **does not execute** any text found in the imported JSON and does not fetch external URLs.

The associated workflow `.github/workflows/janus-ocean-tachyon-research-inbox.yml` is `pull_request` and `workflow_dispatch` only. It checks out an immutable Tachyon source commit from DemiHead, replays its source-bound early receipt and archives an Ocean-side intake result. No schedule, push to main, user secrets, model inference, automatic fine-tuning, future-beacon retrieval or existing Ocean scheduler modification.

### Verification

```
python -m unittest discover -s tests -p test_ocean_tachyon_review_consumer.py -v
python experiments/ocean_transformer/tachyon_review_consumer.py \
  --tachyon-review tests/fixtures/tachyon_ocean_early_20261112.json \
  --out /tmp/ocean-tachyon-inbox.json
```

**Scientific limitation:** this proves that *two repositories can exchange verified research data under a bounded policy*. It does not show gain from dual-model training, new generalization, physical backward communication, or independent TOPA proof of the hypothesis. Those need future controlled tests with frozen outcomes and baseline comparisons.
