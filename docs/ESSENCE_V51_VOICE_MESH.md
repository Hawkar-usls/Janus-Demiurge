# ESSENCE v5.1 — shared speaker link, peer tasks, verified replies

This is a **real two-way inter-repository GitHub Actions communication pilot** for
the existing six-microkernel ESSENCE manifests in **Janus-Demiurge** and
**Janus_Genesis**. It extends the original static ESSENCE v1.3 research peer
inbox but does **not** enable the previously disabled root ESSENCE execution
permissions or automatically promote any unverified model.

## Transport and spoken-model binding

Each kernel has a data-only model link in
`.janus/essence/VOICE_MODEL_LINK.json` to the exact, **real** inherited
Qwen2.5-0.5B-Instruct G2 inference receipt on the shared Demiurge
`janus-v50-agency-state` branch. The original model output was `HOLD`.
A worker fetches and rechecks the exact receipt before sending messages.

**Limit:** v5.1 reuses a verified *model link*, not a fresh neural generation
for every message. The questions and replies are intentionally fixed,
source-checked research protocols. Neither of the six logical microkernels
gets its own newly trained or deployed dialogue model. Claims otherwise
would be false.

Each repository retains its own public `essence-voice-state` branch.
There is **no** token with write access to another repository.
Workflows wake on relevant trusted main changes, manually or by best-effort
cron; schedules are not uninterrupted 24/7 compute.

## Actual evidence from first two repositories

1. Demiurge [run #43831271682](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43831271682)
   **SUCCESS**: wrote a bounded verification assignment to Genesis
   [source message](https://github.com/Hawkar-usls/Janus-Demiurge/blob/essence-voice-state/research/essence/voice_v51/messages/8c51044464c6687973d996e2.json).
2. Genesis [run #43831450381](https://github.com/Hawkar-usls/Janus_Genesis/actions/runs/43831450381)
   **SUCCESS**: checked the pinned source bytes and issued a reply
   [checked peer response](https://github.com/Hawkar-usls/Janus_Genesis/blob/essence-voice-state/research/essence/voice_v51/replies/8c51044464c6687973d996e2.json)
   with the real negative result `16/16 old route`, `0/6 Lapis`, `HOLD`.
   The Genesis kernel also requested a reciprocal test:
   [Genesis → Demiurge](https://github.com/Hawkar-usls/Janus_Genesis/blob/essence-voice-state/research/essence/voice_v51/messages/60bde5c2c3e346c86501af9a.json).
3. Demiurge's **second** worker poll must verify the Genesis request and
   reply; the next Genesis poll must acknowledge it. Do not count these as
   complete until the actual `replies/` and `heard/` JSON files appear in
   each repository's own state branch.

## Contract for delegation

- Only `VERIFY_V49_HOLD` and `VERIFY_GENESIS_ESSENCE` are enabled. A
  delegated task triggers source verification and a human-readable
  research response, **never arbitrary shell/code/workflow execution**.
- Sender, recipient, task identifier, SHA-256, the exact source Git commit,
  source JSON path, fixed task type, source-backed result and replay receipt
  are all checked independently by the receiving kernel.
- Responses carry source-backed negative results, not claims that remote
  neural replies constitute independent scientific validation.
- `NO_ACTION` and `HOLD` retain their meanings. No root kernel permission
  change, cross-repository write, automatic code/model promotion, Sentinel
  dispatch, or access to production model services.
- A future genuinely model-generated conversational layer can propose
  natural-language questions, but a separate verified planner must map
  them to the same strict allowlist, and external scientific claims must
  remain independently testable.
