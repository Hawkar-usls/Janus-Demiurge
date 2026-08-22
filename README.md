<div align="center">

# Janus Demiurge
### JANUS GitHub-native Agent Control Plane

![Status](https://img.shields.io/badge/status-active-2ea44f)
![Swarm](https://img.shields.io/badge/scout%20agents-17-8250df)

</div>

## Active role

`Janus-Demiurge` is now the **control plane and answering repository** for the JANUS Scout Swarm.

Seventeen separate GitHub-native Scout agents are dispatched read-only into seventeen JANUS repositories. Each agent has an explicit role, target repository/ref, bounded mission, and an ephemeral JANUS agent token whose raw value is never persisted. Their reports return here and are aggregated under `scout_swarm/`.

The historical optimization/simulation code remains preserved as a legacy experimental layer; activating the Scout control plane does not retroactively turn historical project vocabulary or experiments into validated scientific claims.

## Scout Swarm 17

The active manifest is [`scout_swarm/SCOUT_SWARM_MANIFEST-v1.json`](scout_swarm/SCOUT_SWARM_MANIFEST-v1.json).

The swarm includes dedicated reconnaissance for Aura Oracle, HRaiN, iNaiHR, Cosmos, Meta Registry, Distributed Swarm, Terminal, DemiHead, Fundamentum, Fast-CAT-SHAiTan, SCOBY-D0, Lapis, Voice, Echo-Pyramid, Tranception, AIFC and Git Habitat/Genesis.

`SCOUT_AURA_ORACLE_01` is assigned specifically to `Hawkar-usls/aura-oracle-tg`. Oracle/symbolic guidance is preserved as guidance and is never promoted to empirical proof without an external evidence chain.

## Runtime

The workflow [`JANUS Demiurge Scout Swarm 17`](.github/workflows/janus-demiurge-scout-swarm.yml) runs:

- when the swarm control plane changes on `main`;
- on manual dispatch;
- every six hours.

Each target repository is observed read-only. Results are returned to:

```text
scout_swarm/outbox/runs/<github_run_id>/
scout_swarm/state/agents/<agent_id>.json
scout_swarm/state/SCOUT_SWARM_STATUS-v1.json
```

## Evidence law

```text
SCOUTS MAY DISCOVER
SCOUTS MAY DISAGREE
SCOUTS MAY FAIL

ONLY EVIDENCE ADVANCES THE CLAIM
MODEL OUTPUT != INDEPENDENT CONFIRMATION
ORACLE GUIDANCE != EMPIRICAL PROOF
TARGET REPOSITORY = READ ONLY
```

Repository observations are bound to repository/ref/commit and source paths where available. A Scout report is information, not authority over the target repository.

## Historical layer

The repository still preserves earlier experiments in adaptive training loops, hyperparameter search, resource monitoring, experiment/evolutionary memory, swarm/Bayesian optimization, and game-like simulations. Those files remain historical implementation context beneath the active Scout control plane.

Machine-readable status: [`PROJECT_STATUS.json`](PROJECT_STATUS.json).

## License

MIT.
