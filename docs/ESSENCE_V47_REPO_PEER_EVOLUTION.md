# ESSENCE v4.7 — JANUS learns from its repository and a peer

This stage extends the real ESSENCE v4.6 Qwen 0.5B LoRA **child** into a
second-generation research model. Unlike the toy relay task, the supervision
comes from the actual JANUS repository model manifest. It is not a new
foundation model, not the separate active Qwen 1.5B Terminal endpoint, and not
an update of the native JANUS byte-transformer.

## Concrete mechanism

1. A reviewed, exact-file source contract in
   `janus_model/JANUS_MODEL_MANIFEST-v1.json` fixes the byte SHA256 of the
   repository and 12 permitted training properties, plus 6 never-trained
   fields and rephrased-question probes. All keys are allowlisted, never
   dynamically assembled from a model's arbitrary path request.
2. Load the **actual** 0.5B Qwen LoRA descendant from run
   [43744199834](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43744199834),
   parent lineage `6033aebc919988b782874fb59ac24a97679010640e9992c9a25f681709353184`.
3. The parent is prompted to **choose a field it needs to clarify**, then
   attempts an answer. SmolLM2-360M receives its answer plus read-only
   repository evidence and offers a concrete critique. Qwen revises. Store
   the complete, text-only dialogue in a signed, research-only artifact.
4. The validator accepts the **actual JSON field** as teaching ground truth;
   it compares both model answers with source but NEVER blindly uses a peer's
   opinion, Qwen's revised text or a model vote as a training target.
5. Starting from **the same inherited G1 LoRA tensors**, train 24 bounded
   steps on the 12 source-backed Q/A facts. Store changed G2 safetensors,
   training cost, source SHA, model parent hash and dialogue hash.
6. A different Actions job independently loads G1 and G2 (same base weights)
   and compares **rephrased questions**, **unseen repository properties**, and
   **retention on the previous G1 toy task**. A positive development label
   requires no large regressions on unseen facts or previous-task retention;
   a failing exam stays failed, with no post-hoc retuning of its threshold.

This is a first proof-of-mechanics and a very small repository knowledge
experiment. The rephrased questions ask about previously trained values, and
the unseen properties are in the same public JSON source. This is not an
externally blind evaluation of broad coding or reasoning capability.

## Authority boundaries

- All workflow jobs use read-only GitHub permissions plus `actions:read`
  to download the existing inherited checkpoint.
- No cross-repository writes, Issue/PR edits, model-authored commands,
  deployment, new service route, Sentinel instruction or production promotion.
- Source/path allowlists, source and checkpoint SHA256, bounded prompts, text
  length limits, no model tool calls and no untrusted self-training.
- The native JANUS checkpoint, existing Terminal Qwen 1.5B and Sentinel A/B/C
  are never altered.
- The public dialogue archive's [ESSENCE v4.5 admission gate](../research/essence/peer_v45/shadow_lock.json)
  **still blocks** using unverified Qwen↔SmolLM dialogues as training truth.
- No independent external custodian has approved source labels, and the public
  JSON cohort is not a hidden human examination.

If and only if the experiment actually produces a valid adapter and a paired
report, label it `PASS_INTERNAL_REPO_PEER_SHADOW_GAIN` or
`NO_GAIN_OR_REGRESSION`. Do not claim general learning, recursive self
improvement, or future independent replication from a successful GitHub
workflow alone.
