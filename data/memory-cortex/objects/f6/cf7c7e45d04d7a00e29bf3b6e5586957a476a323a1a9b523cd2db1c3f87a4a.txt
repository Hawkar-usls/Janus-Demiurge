# JANUS Working Map v1.1

**Status:** `FIVE_STEP_ROADMAP_COMPLETED_AND_PROMOTED`  
**Machine authority:** `data/JANUS-WORKING-MAP-REPOSITORY-ANATOMY-AND-INTEGRATION-ROADMAP-2026-08-19-v1.1.json`  
**Current DemiHead anchor:** `599a730f5db11f7a141209c84e728d10f7a8d379`  
**Current additive Nexus layer:** `v2.4`

This document is a human-readable projection. The versioned JSON working map, frozen contracts, CI artifacts and promotion receipts carry the exact machine lineage.

## Three graphs

### Habitat

Answers **what exists and where it belongs**.

```text
repository link != command authority
write-back default = DENY
```

### Nexus

Answers **which typed object may move from which head to which other head**.

```text
type compatibility != admitted route
route receipt != delivery
connection does not create authority
```

### Epistemic / proof graph

Answers **which bounded provider, witness, observer or evaluator may handle which class of claim or evidence**.

```text
provider PASS != world truth
evidence candidate != evidence admission
measurement != inference
```

## Promoted five-step spine

### v2 — Cosmos proof provider

```text
PROOF_BROKER -> COSMOS : COSMOS_PROOF_REQUEST
COSMOS -> PROOF_BROKER : COSMOS_PROOF_RECEIPT
```

GoldPrompt intent, provider SHA, input/result hashes and zero authority/effect deltas remain bound. `P_VS_NP = OPEN`.

### v2.1 — SkinGPT physical shell

```text
SKINGPT -> OBSERVER : TELEMETRY_SAMPLE
```

Raw sensor frame is normalized before routing. Raw device/boot identity and source IP are not forwarded. Rule confidence and severity remain heuristic, not calibrated probability.

### v2.2 — Swarm peripheral nervous system

```text
SWARM_EDGE -> OBSERVER : TELEMETRY_SAMPLE
```

`FRESH / STALE / ABSENT / RECOVERING / DEGRADED` remain visible. Missing sensors are not fabricated. Memory/prediction cannot become current presence. Observer-only submit pressure remains zero.

### v2.3 — AIFC witness protocol

```text
AIFC_WITNESS -> FUNDAMENTUM : EVIDENCE_CANDIDATE
```

AIFC Grades 0–6 are preserved under their own bounded meanings. Grade 3 is not retrocausality proof. Replicated incompatibility is not a physical-mechanism proof. Nexus does not perform Fundamentum admission.

### v2.4 — I0 Proof-of-Observation measurement membrane

```text
I0_MEASUREMENT -> MEASUREMENT_BROKER : MEASUREMENT_RECEIPT
MEASUREMENT_BROKER -> FUNDAMENTUM : EVIDENCE_CANDIDATE
```

Facts, derived metrics and claims remain separate. `UNKNOWN != 0`; `STALE != CURRENT`; contaminated measurements cannot support `CONFIRMED`; overlapping views do not become independent replication. Hash-chain integrity is not source truth.

## Current information paths

```text
USER INTENT
   |
   +-> HRain / iNaiHR context
   |        |
   |        v
   |     DemiHead
   |        |
   |        +-> PROOF_BROKER -> COSMOS -> proof receipt
   |
SKINGPT ----+-> OBSERVER -> bounded observation path
SWARM_EDGE -+

AIFC_WITNESS -----------------------> FUNDAMENTUM
I0_MEASUREMENT -> MEASUREMENT_BROKER -> FUNDAMENTUM

bounded results / holds / receipts -> Registry lineage
```

## Cross-layer constitution

```text
CONNECTION_PRESERVES_PROVENANCE
CONNECTION_DOES_NOT_CREATE_AUTHORITY
REPRESENTATION != IDENTITY
RAW_SENSOR_FRAME != OBSERVATION_SIGNAL
TELEMETRY_SAMPLE != TRUTH
STALE_SOURCE != CURRENT_SOURCE
EVIDENCE_GRADE != WORLD_TRUTH
MEASUREMENT_RECEIPT != EVIDENCE_ADMISSION
INTEGRITY != TRUTH
MISSING != ZERO
ROUTE_RECEIPT != DELIVERY
NEW_PASS != ERASURE_OF_OLD_FAIL
```

## Global firewalls

```text
AUTHORITY_DELTA_DEFAULT = 0
MASS_EFFECT_BUDGET_DELTA_DEFAULT = 0
WRITE_BACK_DEFAULT = DENY
AUTOMATIC_EXTERNAL_EFFECTS = false
P_VS_NP = OPEN
P_EQUALS_NP = NOT_ESTABLISHED
P_NOT_EQUALS_NP = NOT_ESTABLISHED
```

## Next phase

`READY_FOR_POST_ROADMAP_ARCHITECTURE_AUDIT_AND_NEXT_PREREGISTERED_WORKING_MAP`

This readiness state is **not automatic authorization to add more cross-repository authority or routes**. The next expansion should begin with a new source-first audit and a new frozen working map/contract, preserving v1.1 unchanged.
