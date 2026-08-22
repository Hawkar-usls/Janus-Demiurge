<div align="center">

# Janus Demiurge
### JANUS Spiral Agent Control Plane

![Status](https://img.shields.io/badge/status-live%20spiral-2ea043)
![Agents](https://img.shields.io/badge/scouts-17-1f6feb)
![Model](https://img.shields.io/badge/evolution-spiral-8957e5)

</div>

## What Demiurge is now

`Janus-Demiurge` is the GitHub-native creator, dispatcher and receiving control plane for JANUS agents. It currently runs a 17-agent Scout Swarm across the JANUS repository constellation and returns all reconnaissance to this repository.

The old evolutionary sandbox is not thrown away. It is the ancestry from which the active control plane grew.

## Canonical evolution law

Demiurge no longer models learning as a closed ring where the weak version disappears and the winner replaces it.

```text
A0 -> B0 -> C0 -> ASCEND
                  |
                  v
A1 -> B1 -> C1 -> ASCEND
                  |
                  v
A2 ...
```

For every learning identity:

```text
ENTITY_n + EXPERIENCE_n + FAILED_ATTEMPTS_n + CONSTRAINTS_n
                         |
                         v
                      INTEGRATE
                         |
                         v
                     ENTITY_n+1
```

A failed mutation is a lesson. A weak species is coached into another turn. A low-ranked solution may leave the active frontier, but its lineage is retained. A Scout revisiting the same repository is the same Scout at a higher turn, not a reset copy.

Canonical contract: [`protocol/DEMIURGE_SPIRAL_EVOLUTION-v1.json`](protocol/DEMIURGE_SPIRAL_EVOLUTION-v1.json)

## 17-agent Scout Swarm

The active swarm lives under `.github/agents/` and is orchestrated by `.github/workflows/janus-demiurge-scout-swarm.yml`.

Each Scout has:

- a persistent JANUS identity;
- a dedicated repository/ref mission;
- an ephemeral per-run JANUS token whose raw value is never persisted;
- a monotonic `spiral.turn`;
- inherited lessons/constraints from its previous turn;
- current repository evidence bound to a concrete commit;
- a strict rule that previous model output is memory, not independent confirmation.

One dedicated Scout is assigned to Aura Oracle. Aura guidance remains symbolic/oracle guidance unless independently evidenced.

## Spiral outcomes

`ASCENDED` means the active state advanced while ancestry was retained. `INTEGRATED_LESSON` means the candidate was not promoted but its failure was converted into knowledge. `NO_ASCENT` means the pass added no new evidence, lesson or constraint.

This allows physical worker slots to wrap for scheduling while logical state never becomes a ring.

## Preserved ancestry

Historical modules for adaptive optimization, architecture mutation, species, memory, world simulation, culture and game-like Genesis experiments remain in the repository. They are not deleted just because a newer active model exists.

Core migration surfaces now include:

- `spiral_evolution.py` — canonical lineage primitives;
- `auto_evolution.py` — failed candidates become lessons;
- `architect_ai.py` — architecture genomes carry parent fingerprints/generations;
- `species_engine.py` — extinction/culling becomes recovery and coached ascent;
- `swarm_optimizer.py` — physical round-robin, logical monotonic spiral;
- `janus_core/convergence_engine.py` — bounded frontier plus preserved archive;
- `janus_genesis/demiurge.py` — the meta-controller itself records spiral turns;
- `tools/demiurge_scout_swarm.py` — the live 17-agent swarm accumulates state across runs.

Repository-wide migration map: [`migration/DEMIURGE_SPIRAL_MIGRATION_MAP-v1.json`](migration/DEMIURGE_SPIRAL_MIGRATION_MAP-v1.json)

## Truth boundary

```text
MODEL OUTPUT != INDEPENDENT CONFIRMATION
ORACLE GUIDANCE != EMPIRICAL PROOF
REPOSITORY TEXT != WORLD TRUTH
SCOUT REPORT != WRITE AUTHORITY OVER TARGET
```

The spiral preserves uncertainty as well as success. An unresolved claim may survive into the next turn as a question; it does not become true merely by surviving.

## Scope of “no deletion”

The protection applies to learning identities, evidence, attempted solutions, provenance and lessons. Temporary runtime/game objects may still transition: a sold item may change owner, a temporary buff may expire, and a market listing may close. Those are state transitions rather than deletion of a learning identity.

## Status

Machine-readable state: [`PROJECT_STATUS.json`](PROJECT_STATUS.json)

**Current class:** `ACTIVE_CONTROL_PLANE`  
**Iteration:** `LIVE_SPIRAL_ITERATION`  
**Scout count:** `17`

## License

MIT.
