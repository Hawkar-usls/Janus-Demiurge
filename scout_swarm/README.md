# JANUS Demiurge Scout Swarm — 17 Agents

`Janus-Demiurge` is the control plane and the answering repository. Seventeen separate Scout agents are dispatched read-only into seventeen JANUS repositories. Each worker receives its own mission file under `.github/agents/`, its own ephemeral JANUS agent token, and returns a structured report to this repository.

## Runtime

`JANUS Demiurge Scout Swarm 17` runs as a GitHub Actions matrix on manual dispatch, on relevant control-plane changes, and every six hours. Target repositories are cloned read-only. No Scout writes to the repository it observes.

All individual results are aggregated back into:

- `scout_swarm/outbox/runs/<github_run_id>/`
- `scout_swarm/state/agents/<agent_id>.json`
- `scout_swarm/state/SCOUT_SWARM_STATUS-v1.json`

## Evidence law

A model summary is never independent confirmation. Repository observations are bound to repository/ref/commit and source paths. Oracle/symbolic material remains Oracle/symbolic material unless an external empirical evidence chain exists.

The dedicated `SCOUT_AURA_ORACLE_01` is assigned to `Hawkar-usls/aura-oracle-tg` and reports Aura Oracle state back to Demiurge without turning oracle output into physical fact.
