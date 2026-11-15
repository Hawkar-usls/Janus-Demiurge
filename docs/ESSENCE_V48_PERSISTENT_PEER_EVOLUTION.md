# ESSENCE v4.8 — recurring GitHub-only model evolution (research shadow)

**Goal:** close a *bounded experimental* loop around the actual G2 Qwen 0.5B
LoRA adapter produced by ESSENCE v4.7, without replacing the native JANUS
byte-transformer, Terminal's active Qwen 1.5B, or Sentinel A/B/C.

Workflow: [.github/workflows/essence-v48-recurrent-peer.yml](../.github/workflows/essence-v48-recurrent-peer.yml).
State: branch [`essence-peer-shadow-state`](https://github.com/Hawkar-usls/Janus-Demiurge/tree/essence-peer-shadow-state)
under `research/essence/peer_v48_state/ledger.json` plus `models/genXXXX/`.
These sources and thresholds were fixed **before the first live v4.8 run**
in `research/essence/peer_v48/CYCLE_LOCK.json`.

## Cycle each six hours (best-effort GitHub Actions schedule)

1. **Planner:** GitHub fetches *read-only public JSON* from Terminal,
   HRain, and Genesis at concrete git commit SHA; only explicitly approved
   scalar keys can enter the task. Compare each canonical factual cohort hash
   to an append-only attempt ledger. If no genuinely new source values
   are available, skip model inference and training; no repeated cold starts.
2. **Memory:** the planner validates the SHA-chained ancestry, parent tensor
   SHA, and previously verified source-grounded question/answer memories.
   A fresh candidate continues the **last internally accepted research**
   adapter, not the original weights. If the previous attempt failed, retain
   that same incumbent for the next distinct factual cohort.
3. **Source-bounded curiosity:** the current Qwen proposes a field it wants
   to clarify (an unrecognized answer becomes a logged fallback).
   SmolLM critiques with the **actual read-only JSON fact**. Qwen attempts
   an answer with/without the peer; peer contribution is measured, never
   presumed. Raw peer text never becomes a training truth label.
4. **Train:** a frozen 20-step, rank-preserving LoRA candidate is trained
   from source facts plus prior verified replay-memory. Parent weights and
   previous generations remain unchanged.
5. **Distinct exam job:** *after* the candidate checkpoint has been saved,
   another Actions job retrieves a different source repository, checks the
   commit promised before training, and scores parent vs child on a fixed
   reworded sample, other-repo questions, and the previous relay-task
   proficiency plus replay memories. This is still an **internal**, public
   evaluation. It is not a cryptographically hidden independent examination.
6. **Research-only shadow admission:** require NLL + exact correctness
   improvement on the current source, no regression beyond frozen limits
   on another source, and no previous-skill regression. Accept candidate
   **only** into the isolated shadow-state branch if *all* gates pass.
   Otherwise, preserve a failed-attempt receipt but keep the same parent.
   Never choose a better seed/threshold retrospectively on this exam.
7. **Persistence:** checkpoint safetensors, parent chain SHA, individual
   source SHA, positive source-backed factual memory and negative receipts
   are preserved in GitHub. Independently checkable source facts remain in
   the factual replay memory **even when a neural candidate is rejected**.
   Old attempts can be re-verified against their original public file SHA;
   facts from the next heldout repository are explicitly excluded from
   the training memory to avoid leakage. GitHub Actions runners may disappear;
   GitHub remains a common global failure point.

## Security and science boundaries

- No agent-generated code execution, no arbitrary repo/path inspection,
  no secrets, no privileged GitHub credential passed to Qwen or SmolLM.
- No tensor updates to native JANUS, Terminal Qwen, or production services.
- No Sentinel A/B/C dispatch, no service traffic shift, no silent prod
  promotion. GitHub write permission exists **only in the final persistence
  job** to the dedicated shadow-state branch.
- The first G2 seed is SHA-bound to actual v4.7 run
  [43746247031](https://github.com/Hawkar-usls/Janus-Demiurge/actions/runs/43746247031).
  Later accepted shadow children become genuine neural parents; rejection
  leaves lineage unchanged.
- Candidate test questions from another public repo and internal no-peer
  ablations **do not** establish independent replication. New closed tasks
  administered by an actual outside custodian, quality gains on unseen
  families, and a tested deployment/rollback gateway are **separate HOLD**
  prerequisites for changing any production model.
- Scheduled workflows are *not* 24/7 running processes and may be delayed
  by GitHub. The model does not continuously run or edit code between wakes.
- Stops after 8 accepted generations or 32 attempted cohorts until a new
  independently reviewed contract is provided; no unbounded self-training.
- The independent human-reviewed conversation-corpus gate from v4.5 remains
  unchanged. This v4.8 lane trains on programmatically checked **repository
  facts**, never unverified Qwen/SmolLM conversation claims.

## Validation labels

`SELF_VERIFIED_DATA_LINEAGE` = GitHub Actions and SHA checks;
`PASS_INTERNAL_SHADOW_RETAINED` = experiment's paired nonregression
criteria passed; `INDEPENDENTLY_REPLICATED` and
`EXTERNALLY_VALIDATED` are **not available** until external evidence
exists. Only research weights can pass the internal shadow gate.

For a new source, new accepted memory is a *fact observed in the repository*,
not proof that the language model correctly explains the entire repository.
