# ESSENCE v4.7: first inherited Qwen repo-learning experiment

Source: [Actions run #43746247031](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43746247031).
This is an audit of **the original first run**; no benchmark retuning or extra
re-execution is performed by this documentation change.

## Confirmed implementation

- Loaded the real G1 Qwen 0.5B LoRA descendant from v4.6 (not reinitialized).
- Qwen selected the field `modular_organism.autonomous_merge` without a human
  specifying which property it should ask about.
- Initial answer: `unknown`. SmolLM repeated the question and did not
  offer a useful independent correction. Qwen subsequently returned the
  correct source-backed `false`, because the original JSON was supplied
  alongside the peer response. **No causal peer-review benefit is proven.**
- Generated and trained **24 actual optimizer steps**, saving a new LoRA
  tensor file: SHA256
  `1ec5b21689ee5af6eec5345e0f5b91fc0870ffa520a56ef8778ce914ac28f3bc`.
  Original G1 LoRA SHA256
  `ff2ee0257ef90d2ed7a19ba6de76456f8526709d7e9b76de06858d35bc2838db`.
- Model teacher targets derived only from 12 verified JSON properties, not
  from untrusted model replies.

## Real paired results

| Test | G1 exact | G2 exact | G1 token NLL | G2 token NLL |
|---|---:|---:|---:|---:|
| Reworded known JANUS properties | 0/12 | 2/12 | 6.2467600 | 3.3043101 |
| Different JANUS fields | 0/6 | 1/6 | 7.0234943 | 2.1597623 |
| Previous G1 synthetic task retention | 8/8 | 8/8 | 0.0044825 | 0.1342460 |

The one-shot run returned `PASS_INTERNAL_REPO_PEER_SHADOW_GAIN` according to
the **predeclared internal NLL/nonregression criterion**. It was a genuine
research success at weight inheritance and lower likelihood loss, **not**
a proof of useful general-purpose factual question answering: G2 still
missed 10/12 reworded values and 5/6 untrained fields.

## Corrected evidence caveat

The first code release records `holdout_seen_during_training: false`,
meaning no *holdout target answers* were supplied as optimizer targets.
However, training code re-ran the `freeze()` check, which parsed the
**entire public manifest**, including the heldout keys, to compare the
hash commitments. Thus holdout bytes *were accessible to the process*,
although not used in gradient training. The exam was a separate job but
was **not an independently secret or truly blind heldout examination**.

This caveat is recorded explicitly instead of retroactively changing
the frozen first experiment. Future versions must physically isolate
new exam labels from the training job, commit them with an external
custodian and use an evaluation cohort not visible to the candidate.

## Boundary

The resulting weights are not a replacement for Terminal Qwen 1.5B, the
native JANUS byte-transformer, or Sentinel A/B/C. No service switch, rollback,
external replication, or prospective production promotion took place. The
correct status is `SELF_VERIFIED_DEV_REPO_LEARNING / FUNCTIONAL_HOLD`.

Machine-readable summary: `research/essence/peer_v47/FIRST_RUN_EVIDENCE.json`.
