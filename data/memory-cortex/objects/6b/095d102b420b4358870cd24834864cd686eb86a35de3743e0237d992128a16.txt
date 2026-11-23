# JANUS Linear A research pipeline

This directory is the executable layer of the JANUS Linear A program. Persistent scientific state lives in `data/`; executable methodology lives here in `research/linear_a/`; GitHub Actions under `.github/workflows/` provide actual execution receipts.

## Current canonical state

Current recovery/source-of-truth node:

- `data/JANUS-LINEAR-A-RESEARCH-STATE-2026-08-14-v2.4.json`

Parent canonical state:

- `data/JANUS-LINEAR-A-RESEARCH-STATE-2026-08-14-v2.3.json`

Current typed representation baseline:

- `data/JANUS-LINEAR-A-TYPED-TOKEN-CORRECTIVE-REPLAY-RESULT-2026-08-14-v0.6.2.json`

Current v0.7 reconciliation:

- `data/JANUS-LINEAR-A-V0.7-DUAL-IMPLEMENTATION-RECONCILIATION-2026-08-14-v1.0.json`

Canonical v0.8 result:

- `data/JANUS-LINEAR-A-HIGHER-ORDER-NEIGHBORHOOD-RESULT-2026-08-14-v0.8.json`

Supplementary v0.8 reconciliation:

- `data/JANUS-LINEAR-A-V0.8-MULTI-IMPLEMENTATION-RECONCILIATION-2026-08-14-v1.0.json`

Historical states and receipts are never deleted. New canonical states supersede them only for current inference.

## Repository layout

- `research/linear_a/` — parsers, token-typing policies, null operators, statistical runners, corrective replay code, and independent/supplementary implementations.
- `data/` — frozen execution specs, immutable result summaries, failure audits, reconciliations, canonical state, Connection candidates, and roadmaps.
- `.github/workflows/` — actual executions; Actions artifacts are receipts, not the permanent scientific registry.

## Frozen same-corpus baseline

Primary same-corpus work currently freezes:

- repository: `mwenge/lineara.xyz`
- commit: `43fe7cf1abc8e6bb1ea3228c3a1bd5938709620a`
- `LinearAInscriptions.js` blob: `ef41c58802a3135f295072ba60fc0df39450a10c`
- numeric inventory: `items_analysis/numbers.txt`
- numeric inventory blob: `a17b8922297795a90ea6761f32f6ea020b733a6d`

No result may silently switch source versions.

## Historical v0.1–v0.6 stages

- `janus_linear_a_full_corpus.py` — blind full-corpus structural analysis.
- `janus_linear_a_candidate_holdout.py` — train-only candidate discovery followed by true held-out replication.
- `janus_linear_a_survivor_decomposition.py` — post-reveal known-structure decomposition.
- `janus_linear_a_vir_subtype.py` — A100-102/VIR quantitative subtype audit.
- `janus_linear_a_known_subtracted.py` — known-family-subtracted numeric cross-region search.
- `janus_linear_a_record_role.py` — record-boundary / formula-slot cross-region search.

These runners remain preserved even where later representation corrections supersede their old inferential receipts.

## Representation correction v0.6.1 — punctuation boundary

Files:

- `janus_linear_a_parser_policy_v0_6_1.py`
- `janus_linear_a_corrective_replay_v0_6_1.py`

A strong pre-filter `*900` structural survivor was revealed to be Aegean word-separator punctuation, not a semantic Linear A token. The corrected policy removes `*900`, `*901`, `*902`, and `*903` before semantic hashing, scoring, null generation, numeric adjacency, and row geometry.

Permanent audit:

- `data/JANUS-LINEAR-A-PARSER-BOUNDARY-CANARY-AUDIT-2026-08-14-v1.0.json`

## Representation correction v0.6.2 — typed candidate universe

Files:

- `janus_linear_a_token_typing_policy_v0_6_2.py`
- `janus_linear_a_corrective_replay_v0_6_2.py`

Typed classes:

- `PUNCTUATION`
- `NUMERIC_EXACT`
- `NUMERIC_APPROX_OR_UNCERTAIN`
- `SEMANTIC_CANDIDATE`

Only `SEMANTIC_CANDIDATE` may receive semantic word/suffix identity hashes. The corrective scan found 121 numeric-literal occurrences that the historical hard-coded fraction parser had missed: `¹⁄₅`, `¹⁄₃`, `≈¹⁄₆`, and `≈¹⁄₄`.

Permanent audit:

- `data/JANUS-LINEAR-A-NUMERIC-LITERAL-TYPE-LEAK-AUDIT-2026-08-14-v1.0.json`

Authoritative typed replay:

- run `31788159539`
- artifact digest `sha256:24b42bedf2caa82d5fe0475d9268be2e6a54711181d0c53c8aabcd447f18a506`

Typed replay preserves known accounting/personnel controls but yields no novel numeric or record-role cross-region survivor.

## v0.7 — dual local-relation implementations

Two materially different implementations were preserved and reconciled instead of silently choosing one.

### Implementation A — screen/confirm + MASK geometry

Runner:

- `janus_linear_a_formula_transition_v0_7.py`

Method:

- local `TT` and `T-N-T` motifs;
- deterministic `HT_SCREEN → HT_CONFIRM → NON_HT`;
- `CONTROL_INCLUDED` and `NOVELTY_MASKED` channels;
- known controls remain fixed `MASK` positions in the novelty channel so deletion cannot fabricate adjacency;
- within-document semantic-identity shuffle;
- Bonferroni on confirmation/replication.

Execution:

- run `31789138925`
- artifact digest `sha256:d6587a682f561cd42d4badc7b54899a2c144ebc4759b14e8f3b353eefb0a4ef2`

Outcome:

- known-control `SA·RA₂ → GRA` confirms across disjoint HT partitions;
- it is not evaluable in non-HT under frozen support minima;
- novelty-masked local TT/TNT channel has no screen-eligible novel motif.

### Implementation B — word-only triple-null max-T

Runner:

- `janus_linear_a_formula_transition.py`

Frozen spec:

- `data/JANUS-LINEAR-A-FORMULA-TRANSITION-EXECUTION-SPEC-2026-08-14-v0.7.json`

Method:

- `WORD_ONLY` semantic representation;
- six directed relation templates;
- HT discovery;
- three destructive nulls: within-row identity shuffle, within-document identity shuffle, and endpoint rewire;
- max-T family-wise error control under all three nulls;
- non-HT consulted only after locked HT selection.

Execution:

- run `31789134447`
- artifact digest `sha256:106ce6f79633504e3c4913fea98497191a04465dc865ca39991a422fbbcad92f`

Outcome:

- 27 HT-eligible semantic endpoints;
- 79 scored nonzero hypotheses;
- 0 pass all three max-T nulls;
- 0 enter non-HT replication.

Reconciliation node:

- `data/JANUS-LINEAR-A-V0.7-DUAL-IMPLEMENTATION-RECONCILIATION-2026-08-14-v1.0.json`

Reconciled claim ceiling:

- intermediate candidates differ, as expected from different methods;
- both converge on `NO_NOVEL_V0_7_CROSS_REGION_SURVIVOR`;
- this is implementation-level convergence, not external corpus replication.

## v0.8 — canonical higher-order typed neighborhoods / specialization

Frozen spec:

- `data/JANUS-LINEAR-A-HIGHER-ORDER-NEIGHBORHOOD-EXECUTION-SPEC-2026-08-14-v0.8.json`

Runner:

- `janus_linear_a_higher_order_neighborhood_v0_8.py`

Workflow:

- `.github/workflows/janus-linear-a-higher-order-v0.8.yml`

Design inherited the strongest safeguards from both v0.7 implementations:

- disjoint `HT_SCREEN → HT_CONFIRM → NON_HT`;
- `WORD_ONLY` semantic representation;
- known controls as fixed `MASK` geometry in novelty analysis;
- six frozen hypothesis families: TTT trigrams, T-N(bucket)-T, row-prefix/suffix TTT, IN and OUT neighborhood specialization;
- three complementary nulls: row shuffle, document shuffle, template/endpoint rewire;
- screen max-T within family plus Bonferroni across six families;
- locked confirmation and replication;
- explicit `NOT_EVALUABLE` semantics;
- post-score semantic reveal.

Execution:

- run `31790304755`
- head `422e2e14ee987a3c00a5c4149c94cb9871a97e2e`
- artifact digest `sha256:3fe29f22073eeed57508e26260315110e11b8e9cbd4fd092278c3c3d4b356cea`

### Canonical v0.8 result

#### CONTROL_INCLUDED

- 22 eligible semantic IDs;
- 19 tested specialization hypotheses;
- 0 screen-selected;
- 0 HT-confirmed;
- 0 non-HT replicated.

#### NOVELTY_MASKED

- 19 eligible semantic IDs;
- 15 tested specialization hypotheses;
- 1 screen-selected: `SA·RA₂`, OUT-neighborhood specialization;
- screen corrected p under each of the three null families: approximately `0.003997`;
- disjoint HT_CONFIRM support: 7 occurrences in 7 documents;
- frozen specialization minimum: 8 occurrences in 5 documents;
- state: `NOT_EVALUABLE`, not failed confirmation;
- therefore 0 HT-confirmed and NON_HT was never entered.

Post-score context matters: `SA·RA₂` was already the left endpoint of the v0.7 known-control motif `SA·RA₂→GRA`. Since GRA becomes a fixed MASK slot in the v0.8 novelty channel while `SA·RA₂` remains semantic, the specialization screen hit is consistent with a shadow of preserved known-control geometry. This contextual interpretation does not modify the frozen statistical outcome: the candidate is already `NOT_EVALUABLE` under the predeclared 8-occurrence HT_CONFIRM minimum.

Permanent result:

- `data/JANUS-LINEAR-A-HIGHER-ORDER-NEIGHBORHOOD-RESULT-2026-08-14-v0.8.json`

Canonical v0.8 claim ceiling:

- novel higher-order cross-region survivors: 0;
- `NEW_ANCHOR_ESTABLISHED = false`;
- `DECIPHERMENT_ESTABLISHED = false`;
- `EXTERNAL_REPLICATION_ESTABLISHED = false`.

The 8-occurrence confirmation minimum was not lowered to 7, and non-HT was not used to rescue the screen hit.

## v0.8 supplementary implementations and reconciliation

Canonical v0.8 above remains the claim-bearing R2 execution. Two additional implementations are preserved as supplementary same-corpus evidence.

### Supplementary A — sequence TTT/T-N(bucket)-T

Runner:

- `janus_linear_a_long_formula_v0_8.py`

Execution:

- run `31789704519`
- artifact digest `sha256:00f0e8938bc49b3786c7511d8da8bfb7f8354939df83afde6e83ffb1d509145e`

Permanent result:

- `data/JANUS-LINEAR-A-LONG-FORMULA-NEIGHBORHOOD-RESULT-2026-08-14-v0.8.json`

Classification guard:

- `data/JANUS-LINEAR-A-V0.8-IMPLEMENTATION-A-CLASSIFICATION-2026-08-14-v1.0.json`

Outcome:

- novelty-masked TTT/TBT screen eligibility: 0;
- known-control `GRA → 10PLUS → *304` reaches screen but is not evaluable in independent HT_CONFIRM;
- no novel survivor.

This is valid for its declared question but is not a replacement for the canonical R2 triple-null execution.

### Supplementary B — row-aware HHI + triple-null studentized max-T

Frozen spec:

- `data/JANUS-LINEAR-A-V0.8-IMPLEMENTATION-B-EXECUTION-SPEC-2026-08-14-v1.0.json`

Runner:

- `janus_linear_a_higher_order_v0_8_b.py`

Workflow:

- `.github/workflows/janus-linear-a-v0-8-implementation-b.yml`

Execution:

- run `31790567289`
- artifact ID `9215284223`
- artifact digest `sha256:493b2b734e0dbfc7a0cff4ef726ba03b89fd5e1541aac643d3c66d1004b9a39b`

Permanent result:

- `data/JANUS-LINEAR-A-V0.8-IMPLEMENTATION-B-RESULT-2026-08-14-v1.0.json`

Outcome:

- 20 eligible semantic endpoints;
- 33 blind hypotheses;
- 2 hypotheses meet raw support minima;
- 0 survive all three studentized max-T nulls;
- 0 enter HT_CONFIRM;
- 0 enter NON_HT.

The most informative near-misses are reciprocal `SA·RA₂ ↔ CYP` specialization. Endpoint-rewire p_FWER is approximately `0.001`, but row/document p_FWER is approximately `0.99–1.0`. This means the endpoint coupling looks exceptional if endpoint marginals alone are preserved, but becomes ordinary once row/document composition is preserved. Complementary nulls therefore localize the structural source of an apparent relation rather than merely making the test stricter.

### Multi-implementation reconciliation

Current reconciliation:

- `data/JANUS-LINEAR-A-V0.8-MULTI-IMPLEMENTATION-RECONCILIATION-2026-08-14-v1.0.json`

Reconciled state:

- canonical v0.8: one `SA·RA₂` novelty screen hit, then `NOT_EVALUABLE` in HT_CONFIRM;
- supplementary A: no novelty screen-eligible sequence motif;
- supplementary B: no triple-null screen selection;
- all implementations: 0 HT-confirmed novel v0.8 survivor;
- same-corpus implementation convergence is **not** external replication.

`SA·RA₂` recurs as a structurally unusual identity across different observables, but recurrence at screen/near-miss level is not replication. It remains non-promotable.

A historical A/B-only reconciliation was created before the already-existing canonical v0.8/v2.3 lineage was noticed:

- `data/JANUS-LINEAR-A-V0.8-DUAL-IMPLEMENTATION-RECONCILIATION-2026-08-14-v1.0.json`

It is intentionally preserved as noncanonical supplementary history. The governance correction is recorded in the multi-implementation reconciliation and canonical v2.4 rather than deleting the earlier artifact.

## Current promotion gate

A genuinely new Linear A anchor requires:

`TYPED CANDIDATE UNIVERSE → BLIND CANDIDATE/RELATION → RELATION-DESTROYING NULL SEPARATION → INDEPENDENT INTERNAL CONFIRMATION → CROSS-PARTITION REPLICATION → FRESH INDEPENDENT TRANSCRIPTION/PARSER → BEHAVIORAL CONSTRAINT → MORPHOLOGICAL/LEXICAL CONSISTENCY → INDEPENDENT IMPLEMENTATION`

A green CI job proves computation and programmed claim-ceiling compliance only.

## Persistent evidence discipline

Every substantial experiment should have:

1. executable code in `research/linear_a/`;
2. a frozen execution spec in `data/` before claim-bearing execution when feasible;
3. an actual CI run and artifact digest;
4. an immutable result JSON in `data/`;
5. explicit PASS / FAIL / NOT_EVALUABLE / KNOWN_CONTROL / REPRESENTATION_FAILURE / NO_PROMOTION semantics;
6. a canonical-state update only after result verification;
7. a predeclared roadmap branch independent of the observed semantic label whenever possible.

Negative results, representation failures, and governance/lineage corrections are scientific state, not cleanup noise.

## Roadmap from canonical v2.4

Canonical roadmap:

- `data/JANUS-LINEAR-A-RESEARCH-STATE-2026-08-14-v2.4.json`

Current sequence:

1. **R0 — DONE:** typed candidate ontology v0.6.2.
2. **R1 — DONE / RECONCILED NEGATIVE:** dual v0.7 local relation implementations.
3. **R2 — DONE NEGATIVE + SUPPLEMENTARY CONVERGENCE:** canonical v0.8 higher-order execution plus supplementary A/B; no HT-confirmed novel survivor.
4. **R3 — ACTIVE NEXT / HIGH PRIORITY:** fresh independent transcription/parser source audit.
5. **R4 — BLOCKED UNTIL R3:** source-specific normalizer/parser under `research/linear_a/`.
6. **R5 — BLOCKED UNTIL R3/R4:** frozen external-replication spec using locked transforms, not re-discovery.
7. **R6 — REQUIRED FOR ANY FUTURE POSITIVE SURVIVOR:** independent implementation replay.
8. **R7 — BLOCKED:** behavioral/morphological/lexical competition until an externally replicated structural survivor exists.
9. **R8 — BLOCKED:** decipherment claim.

### Fresh-source independence rule

A different website, file format, wrapper, or mirror is not enough. A source can count toward external replication only after provenance audit establishes meaningful independence in transcription/editorial decisions and a source-specific parser/normalizer is implemented without passing the data through `mwenge/lineara.xyz` assumptions.

Required R3 audit fields include:

- maintainer/editor provenance;
- primary transcription sources;
- relationship to GORILA and other editions;
- machine-readable availability;
- sign-ID scheme;
- numeric and punctuation conventions;
- license/access conditions;
- evidence of independence from `mwenge/lineara.xyz` transformations.
