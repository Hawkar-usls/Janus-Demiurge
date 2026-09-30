# JANUS Habitat — Demiurge bounded proposal face v1

This layer connects the preserved `Janus-Demiurge` legacy sandbox to JANUS Habitat without promoting the legacy runtime into an autonomous authority.

## Why this exists

The repository already carries `.janus/HABITAT_LINK.json`, but that link is intentionally `REFERENCE_AND_HANDOFF_ONLY`. The v1 face contract adds a typed, executable **proposal surface** while leaving the historical sandbox unchanged.

The adapter extracts three reusable ideas from the legacy lineage:

- `architect_ai.py`: discrete architecture-genome variation;
- `auto_evolution.py`: bounded mutation ranges;
- `bayes_optimizer.py`: separation between proposing a candidate and feeding back an externally measured score.

The adapter does **not** import those modules. This prevents their historical file-writing, optional dependency, training, simulation, or heuristic behavior from becoming Habitat effects by inheritance.

## Cycle position

```text
OBSERVE / MEMORY
      |
      v
DEMIURGE PROPOSE
      |
      v
NEXUS / VERIFIER / POWER TEST
      |
      v
EXTERNAL MEASUREMENTS
      |
      v
DEMIURGE RANK
      |
      v
RECOMMENDATION RECEIPT
      |
      X
NO EXECUTION AUTHORITY
```

The intended wider loop is:

```text
OBSERVE -> RECALL -> PROPOSE -> SIMULATE/TEST -> CHALLENGE -> SELECT -> RECORD -> REPEAT
```

but selection remains a recommendation until a separate effect-admission layer authorizes any external action.

## Laws

```text
LEGACY_SANDBOX != ACTIVE_AUTHORITY
PROPOSED != TESTED
TESTED != SELECTED
SELECTED != AUTHORIZED
RANKING != TRUTH
SIMULATION_OUTPUT != FUTURE_FACT
CI_GREEN != MERGE_PERMISSION
```

## v1 surface

`HabitatDemiurgeFace.propose()` supports two bounded local proposal classes:

- `ARCHITECTURE_VARIATION`
- `CORE_PARAMETER_VARIATION`

The request is closed-schema, deterministic under an explicit integer seed, and limited to at most 16 candidates.

`HabitatDemiurgeFace.rank_evaluated()` ranks only **complete externally supplied finite measurements** for a proposal set. It performs no evaluation itself and marks the winner `authorized=false`.

## Effect boundary

The v1 adapter is stdlib-only and exposes no:

- network client;
- subprocess/process spawn;
- file write;
- model training;
- source mutation;
- command execution;
- cloud/GPU/distributed executor registration;
- self-modification or self-merge primitive.

A future runtime bridge must be a separate Habitat/Armor admission and preserve the same distinction between recommendation and permission.
