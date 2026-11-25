# JANUS Trinity Parental CPU School · R0

This is an **opt-in experimental training and evaluation lane** for the real native JANUS
byte-level Transformer. It does **not** modify the main native model workflow,
existing promoted.pt, ESSENCE G9 LoRA promotion, or production routing.

## Historical source and exact role mapping

From JANUS Trinity / Triune Lineage (originally mapped on Jan 1, 2026):

- **Father / Strategist:** Qwen2.5-0.5B-Instruct from Hugging Face Hub
  pinned to 7ae557604adf67be50417f59c2c2f167def9a775; proposes arithmetic examples.
- **Son / Seer:** JANUS Native (2-layer, 128-byte-context Transformer);
  inherits the actual promoted.pt checkpoint and learns only in a disposable
  shadow copy, never in main.
- **Spirit / Executor / Critic:** HuggingFaceTB/SmolLM2-135M-Instruct pinned
  to 12fd25f77366fa6b3b4b768ec3050bf629380bac; reviews the teacher's
  answer and may veto, but never certifies a fact.
- **Sovereign / Critic gate:** deterministic symbolic arithmetic oracle and
  independent later source-bound examiner. Neither an AI vote nor three-model
  agreement counts as independent scientific validation.

Hugging Face is a hub/library, not one model. Qwen and SmolLM2 are TWO separate
models from that hub; the third model is JANUS itself. Their weights are
downloaded onto GitHub-hosted CPU runners. No paid hosted LLM API is used.

The names **Trinity** and Father/Son/Spirit refer to a computational historic
role mapping only, not literal family, theology, Trinity Site, or empirically
proven autonomy. Never transfer authority between unrelated Trinity namespaces.

## Three-stage experiment

1. **TEACH:** Qwen generates answers to 24 predeclared training-only
   arithmetic tasks. A deterministic arithmetic oracle rejects incorrect
   or non-exact Qwen answers. SmolLM2 can veto additional examples.
   The two model source revisions are pinned. No unseen Genesis exam is
   checked out or read in this job.
2. **TRAIN:** Restore a hash-checked existing native JANUS checkpoint from
   main and take at most 36 low-rate bounded CPU optimization steps using
   accepted examples. Save *only* an Actions artifact with a candidate
   checkpoint and SHA256 identity. The main promoted.pt is untouched.
   A missing/insufficient safe dataset yields HOLD, not unsafe training.
3. **EXAM:** A new Actions job downloads sealed teacher and child artifacts,
   checks out **only here** the Git-blob-frozen Genesis 16+48 task suite,
   and executes *real* Qwen, SmolLM, untrained native incumbent and trained
   native child on the **same 64 questions** using fixed greedy decoding.
   All 64 cases are scored, even if small JANUS cannot fit a question into
   its 128-byte context (it counts as incorrect, never truncated secretly).

## Becoming independent

The child is not eligible for *human review* unless it:
- strictly beats BOTH Qwen and SmolLM parents **and** its own prior incumbent;
- solves at least **two** questions none of those three previously solved;
- loses **zero** questions that any of the three solved;
- maintains source/weight integrity and a completely separate examination
  from training.

Even success means `ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PRODUCTION`.
There is no autonomous model promotion, no self-training switch, no claim
of AGI or confirmed intelligence beyond the teachers. The independent
Genesis G9 LoRA rule remains its own untouched research lane.

**Important methodological limit:** A public, same-owner Genesis benchmark
is not a genuinely independent external blind exam. The teacher and judge
may also be correlated through shared pretraining. The deterministic
oracle prevents incorrect supervision for this *small arithmetic lesson*
but does not constitute an outside evaluator of broader intelligence.
You would need fresh independently custodied tests and statistical
replication for real self-sufficiency.

GitHub Actions scheduled triggers are best effort and may be delayed; a
passing job is not a 24/7 guarantee. GitHub CPU-memory and minutes quotas
depend on repository visibility and plan. This workflow is manual/research
branch only until independent review and staged rollout.

## Local dry runs (contracts only)

    python -m unittest discover -s tests -p 'test_trinity_parental_school.py' -v

## Real GitHub CPU pilot

    python -m tools.trinity_parental_cpu teach --out runtime/trinity/teacher.json
    python -m tools.trinity_parental_cpu train --teacher runtime/trinity/teacher.json --out runtime/trinity/child.pt --receipt runtime/trinity/train.json
    python -m tools.trinity_parental_cpu exam --teacher runtime/trinity/teacher.json --train-receipt runtime/trinity/train.json --student runtime/trinity/child.pt --genesis runtime/independent-genesis --out runtime/trinity/exam.json

Note: the exam must run in a separate runner with immutable source
fingerprints; no inference tokens, training examples, model-generated code,
training data or arbitrary external inputs are executed as code.
