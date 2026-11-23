# JANUS Fresco Forge

`JANUS Fresco Forge` is a content-addressed `JSON -> fresco` visualization pipeline for the JANUS meta-registry.

## Current renderer: v4.4 Semantic Focus Router

v4.4 treats the older scene archetype as an advisory layer for technical records. The final visual focus is selected from path-weighted semantic evidence before any image prompt is built.

```text
canonical JSON
    -> full scalar trace
    -> semantic projection
    -> field-role / entity audit
    -> advisory scene archetype
    -> v4.1.1 semantic + physical-gate firewalls
    -> v4.4 path-weighted Semantic Focus Router
    -> ancient visual translation
    -> continuous mural composition lock
    -> prompt budget fitter (no silent truncation)
    -> Stable Diffusion
```

## Firewalls

The following invariants remain mandatory:

- internal/system names do not become people or gods by name alone;
- workflow/control `gate` is not physical architecture without actual airlock/hatch/chamber/threshold/decompression/vacuum evidence;
- incidental words such as `node`, `peer`, `archive`, or `memory` do not control the scene without dominant path-weighted evidence;
- technical records may override an erroneous `OBJECT_RITUAL` classification when record/provenance semantics dominate;
- unresolved or user-reported claims remain visually non-triumphal;
- images are visualization artifacts only, never evidence or proof.

## Semantic focus classes

v4.4 currently includes:

- `MEMORY_ARCHIVE` — memory/storage/retention/deletion/archive policy;
- `DISTRIBUTED_SWARM` — distributed/swarm/collective topology;
- `RECORD_PROVENANCE` — JSON/record/hash/provenance/append/correction/manifest/integrity flows;
- `GENERIC_SYSTEM` — technical process without a stronger specialized focus;
- `ARCHITECTURAL_EVENT`, `HUMAN_NARRATIVE`, `MYTHIC_NARRATIVE`, `OBJECT_RITUAL` — retained when their evidence survives the firewalls.

### RECORD_PROVENANCE visual grammar

Record/provenance systems become one continuous ancient painted chain of linked record marks and sealed bundles. New marks are appended at the growing end; corrections appear beside older marks instead of erasing them; provenance is a continuous painted thread; archive transfer gains a small durable receipt seal. Hash/integrity continuity is kept visually distinct from whether the original observation itself was true. Literal JSON/code/text is forbidden.

### MEMORY_ARCHIVE visual grammar

Memory policy becomes a continuous record-river crossing recent ring, witness stream, bright pinned rare events and archive. Ordinary traces fade only after useful information moves onward, while anomalies and important episodes remain visible.

### DISTRIBUTED_SWARM visual grammar

A distributed swarm becomes unequal peer beacons scattered through one shared mural landscape with irregular signal ribbons, no throne/monarch, and no icon grid.

## Continuous mural + ancient visual locks

- one continuous asymmetric wall painting;
- full-frame cracked lime plaster;
- mineral pigment, abrasion, stains, irregular cracks and imperfect brushwork;
- no grid, tiled layout, contact sheet, icon sheet, specimen board, repeated medallions or equal cells;
- no 3D/product/CAD render, diagram, flowchart, infographic, UI or glossy machine;
- technical/system scenes use landscape `640x448` canvas;
- guidance scale `7.5`.

## Prompt budget

The full semantic trace stays in the receipt. The image prompt uses only dominant visual anchors. v4.4 tries `FULL`, `COMPACT`, then `MINIMAL` prompt variants. If none fit the real multi-CLIP budget, Forge fails with `PROMPT_BUDGET_VIOLATION` instead of silently truncating and producing a misleading image.

Observed calibration failures remain explicit negative controls:

```text
FAIL__3D_MACHINE_COLLAPSE
FAIL__DIAGRAM_GEOMETRY_COLLAPSE
FAIL__TILED_ICON_GRID_COLLAPSE
FAIL__INCIDENTAL_TERM_SCENE_HIJACK
FAIL__TECHNICAL_PROTOCOL_OBJECTIFICATION
FAIL__SILENT_PROMPT_TRUNCATION
```

## Contract

- Source corpus: `registry/**/*.json` by default.
- JSON identity: `SHA-256(canonical_json)`.
- Equivalent content is rendered at most once regardless of filename/key order.
- Full scalar trace and semantic projection remain auditable in the receipt.
- `semantic_coverage_ratio = 1.0` means nontechnical source semantics are traced/interpreted, not pasted literally into the prompt.
- `false_personification_guard = true`.
- `physical_gate_firewall = true`.
- `scene_focus_firewall = true`.
- `semantic_focus_router = true`.
- `ancient_visual_grammar_lock = true`.
- `no_modern_visual_grammar = true`.
- `full_frame_plaster_surface = true`.
- `continuous_mural_lock = true`.
- `anti_grid_icon_collapse = true`.
- Default model: `dreamlike-art/dreamlike-photoreal-2.0` through local Hugging Face Diffusers; no hosted-inference `HF_TOKEN` is required.

## Outputs

```text
artifacts/janus-fresco-forge/images/
artifacts/janus-fresco-forge/receipts/
artifacts/janus-fresco-forge/ledger.jsonl
```

## Runtime defaults

```text
model               = dreamlike-art/dreamlike-photoreal-2.0
steps               = 20
human canvas        = 512x512
technical canvas    = 640x448
guidance_scale      = 7.5
max_prompt_chunks   = 6
workflow render cap = 1 image/run
```
