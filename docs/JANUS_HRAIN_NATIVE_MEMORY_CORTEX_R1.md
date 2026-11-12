# JANUS Memory Cortex R1 — HRain graph retrieval into real JSON content

Status: **DEVELOPMENT-ONLY / READ-ONLY / NOT NATIVE MODEL V2**.

## Purpose

The original 446,208-parameter JANUS byte Transformer has an immutable v1
128-byte context. The existing v2 native memory path can pass a short source
marker into that window, but not full research content.

This R1 sidecar reuses the **existing** HRain graph ranking and source
hydration, then independently replays each selected JSON against the pinned
Meta Registry Git commit. The output is a useful, bounded source-text packet
for a future long-context model, with immutable source and SHA references.
It makes no change to the existing model, checkpoint or promotion rules.

## Actual path

1. HRain **tools/hrain_conversation_context.py** retrieves the public graph
   projection and ranks relevant paths and graph neighbors.
2. HRain hydrates exact JSON source bytes from the Meta Registry; its result
   includes path, SHA-256, source commit, excerpt and proof envelope.
3. **janus_model/hrain_memory_cortex.py** verifies the HRain envelope hash,
   read-only authority, exact registry HEAD, path containment, source SHA-256,
   raw byte counts, excerpt equality and valid JSON.
4. The adapter emits a bounded UTF-8 text packet (defaults to 4,096 bytes)
   with explicitly untrusted JSON source envelopes and a machine-readable
   source/receipt ledger.
5. No input files are changed. Nothing is injected into the v1 Transformer
   and there is no automatic retraining or promotion.

### Why two checks?

A matching HRain metadata index is not proof of any scientific claim.
Source bytes are checked again *after graph selection* against a checked-out
immutable source commit. This prevents a stale index, forged context excerpt,
modified local file or untrusted graph edge from silently becoming model data.
A SHA validates byte identity, not factual truth.

## Local synthetic/offline check

~~~bash
python -m unittest discover -s tests -p 'test_janus_hrain_memory_cortex.py' -v
~~~

The separate GitHub Actions job also obtains a live public HRain projection,
pins the Meta Registry at its declared commit, runs HRain's query/hydration
on **ROWAN** (max 2 results), and passes that result to the independent
adapter (4,096-byte cap). Only the non-sensitive receipt is uploaded.

## Boundaries and next gates

- **R1:** Prove graph-selected real JSON can be read, replayed, compacted and
  cited without modifying the authoritative registry, trained v1 brain or
  frozen scientific holdouts.
- **R2:** Independently evaluate retrieval quality on new query/source pairs:
  exact-source recall, precision, refusal/no-result behavior, rank versus
  relevant-answer quality, provenance quality and bytes/latency cost.
- **R3:** Train a **separate** native Transformer candidate with longer context
  and appropriate position/tokenization changes. Never alter the v1
  checkpoint in place or report a 4,096-byte sidecar as a 4,096-token model.
- **R4:** Hold out new problems and compare v1, v1 with bounded memory and
  experimental v2 with same retrieved evidence. Retain negative results,
  independent science/evaluation datasets and current promotion gates.

The R1 code is a non-executable read-only memory **data adapter**, not
an instruction channel. Never turn a retrieved JSON field into a command,
a scientific proof, a modification grant, or an automatic model promotion.
No private-repository data is included. No frozen TACHYON R3.9 sources are
read, trained on or graded here.

Canonical source code: janus_model/hrain_memory_cortex.py
