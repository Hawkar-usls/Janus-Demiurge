# JANUS Fresco Forge v3 — Full JSON Visual Projection

## Contract

`JANUS-FRESCO-FORGE-v3.0-full-json-visual-projection` keeps the existing content-addressed discovery/dedupe/ledger loop and replaces the render stage with a semantic compiler.

Pipeline:

```text
canonical JSON
  -> scalar trace
  -> technical vs semantic separation
  -> semantic classification
  -> visual metaphor expansion
  -> narrative fresco prompt
  -> bounded multi-chunk CLIP encoding
  -> Stable Diffusion
  -> PNG + v3 receipt + ledger
```

### Coverage rule

Every JSON scalar is present in `visual_projection.source_trace`.

Every non-technical scalar is present in `visual_projection.semantic_facts` and is eligible to feed the model prompt. Pure provenance/transport values such as hashes, URLs, timestamps, receipt paths, dimensions and generator metadata are retained in the trace but are not treated as visual subjects.

The receipt records `semantic_coverage_ratio`. Normal modes target `1.0`. If a record is too large even for the bounded long-prompt context, the fallback admits the exact lower coverage instead of pretending the entire semantic source reached the model.

## Long prompt handling

Stable Diffusion 1.5 CLIP text encoding normally truncates a prompt to one short context window. v3 tokenizes the fitted prompt into up to `FRESCO_MAX_PROMPT_CHUNKS` chunks (default `6`), encodes each chunk independently, and concatenates the embeddings along the cross-attention sequence dimension.

This makes multiple semantic sections visible to the U-Net rather than silently discarding everything after the first context window.

## Narrative bias

The projector favors:

- figures and agents;
- visible actions;
- symbols and ritual objects;
- emotions;
- environment only as narrative support;
- multiple simultaneous micro-scenes;
- cracked plaster, mineral pigments and weathered wall-painting texture.

The negative prompt explicitly rejects empty halls, architecture-only scenes, decorative-banner-only output, minimalist compositions and UI/text imagery.

## Epistemic rule

Uncertainty is preserved. `candidate`, `pending`, `blocked`, `false`, `NOT_YET_CONFIRMED`, negative evidence and partial outcomes are translated into unresolved or blocked visual motifs. They must not be transformed into a triumphal claim of confirmation.

## Receipts

v3 receipts include:

- source SHA-256;
- full visual projection;
- complete scalar trace;
- semantic fact stream;
- fitted prompt text;
- full-prompt preview;
- negative prompt;
- prompt mode and token budget;
- number of CLIP chunks;
- semantic coverage ratio;
- model, scheduler, guidance scale, seed and elapsed time;
- final PNG SHA-256.

The output remains a visualization lane only. A generated fresco is not evidence for, or proof of, claims in the source JSON.
