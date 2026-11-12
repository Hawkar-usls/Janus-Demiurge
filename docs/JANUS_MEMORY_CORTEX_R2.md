# JANUS Memory Cortex R2 — real retrieval smoke and longer-context shadow

**Status: DEVELOPMENT_ONLY. These are not new promoted weights or validated
scientific model improvements.**

## Current launch

R1 (merged PR #531) proves that the HRain graph can select exact Meta Registry
JSON and re-check raw file hashes on pinned Git commits. R1 creates *external*
working memory, not a new native Transformer attention window.

R2 adds two **independent workstreams**:

1. **Development retrieval benchmark**: frozen post-index smoke cases for
   ROWAN, EYE, Cousteau, and no-match abstention. Compare the unchanged
   existing HRain selector to a deterministic **filename-only lexical**
   control. Score source recall@3, source precision on positive cases,
   abstentions and wall-clock cost on identical public metadata.
2. **Native context candidates**: copies of the verified 128-byte v1
   Transformer with expanded position embeddings for **256 and 512 bytes**,
   held only in the GitHub runner's volatile RAM. Existing 128 rows and all
   other weights remain unchanged; new positional rows are **untrained**.
   The code makes a finite forward pass on a prompt containing actual SHA-
   verified R1 JSON content. No samples are promoted, checkpoints saved,
   secrets used, or deployment affected.

## Fixed snapshots

The development fixture is saved BEFORE benchmark implementation (separate
Git commit) in
\`janus_model/eval/JANUS_HRAIN_R2_DEVELOPMENT_SMOKE-v1.json\`.

- HRain source at commit \`e4ae91372babf8206b2dfed07ff8f1d85d2626d4\`
- Meta Registry projection snapshot at commit
  \`6c9259c43d89569b11351bf8579a3775025fa2f0\`
- Source bytes for real R1 context at projection's pinned
  \`1800e8c9d35b13a6cf5be18156ddc0cd58e46ec8\`
- Public curated projection has **210 nodes**, not the whole 23,734-record
  broader atlas. This snapshot scope is reported exactly.

**Warning: this smoke set was assembled after viewing the index.** It is
neither randomized, statistically independent, nor a claim that graph
retrieval generalizes better than lexical search. A future truly independent
question set needs a sealed custodian and new source families.

## What exactly is expanded?

The original **physical Transformer window is 128 bytes**, with a byte-level
tokenizer; Unicode characters may use more than one byte. The candidates
support **256 or 512 input bytes**, including BOS and the user prompt.
This is not equivalent to 256/512 *natural-language tokens* and is not an
effective 4096-byte end-to-end generative answer.

For a given verified R1 packet the candidate creates:

\`\`\`text
Q:<short user intent>
UNTRUSTED_MEMORY_JSON:<bounded original JSON excerpt>
A:
\`\`\`

The exact source commit and SHA remain in the R1 receipt; they are not
declared automatically factual. Any executable-looking content inside JSON
remains data; **do not assume an untrained model resists prompt injection**.
The shadow path performs a single finite forward computation, not a
demonstration of a useful answer. The main v1 checkpoint remains untouched.

## Verification gates

- R2 unit tests: source drift, no-match honesty, corpus/authority boundaries,
  exact source path labels, neural-query retention and SHA tampering.
- R2 CI: retrieve *fixed* Git snapshots, produce metadata-only benchmark
  receipt, verify zero change to source worktree.
- CPU shadow: pin and rehydrate real source, run 256- and 512-byte candidates
  with SHA-bound R1 packet, prove increased source excerpt fits, finite logits
  and no model/checkpoint promotion.
- If any job fails, preserve the failure. No weakening of the existing
  scientific/holdout gates.

## What still blocks production R2/v2?

1. New **independently authored** and sealed retrieval QA examples, not the
   visible development smoke fixture.
2. Demonstrated correct answers, citations and abstention (not just source
   delivery), across equal-evidence-budget comparator models.
3. Independent training, evaluation, position-extension regression checks,
   cost/latency measurements and non-regression on frozen unrelated tests.
4. Admission of candidate weights only through a dedicated bounded gate,
   never by silently overwriting v1 or training on blind R3.9 datasets.

No files are written to HRain or Meta Registry. No TACHYON R3.9 external
held-out measurements, private access, broad agent rights, or source code
from retrieved JSON are used.
