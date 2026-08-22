# JANUS Scout Swarm Orchestrator

The orchestrator protects Scout identity while coordinating evidence collection.

Core rule:

`FACTS MAY CLUSTER; SCOUTS MUST NOT.`

A shared fact fingerprint may contain many observations, but every observation keeps its Scout ID, round, source URLs and report lineage. Source/fact deduplication is used only for epistemic accounting and never deletes, merges or replaces a Scout.

## Communication model

The workflow has two collection rounds. Round 1 remains independent. The orchestrator then creates an append-only blackboard, explicit work claims and one inbox per Scout. Scouts share source pointers, unresolved checks and conflicts. Round 2 consumes only messages addressed to that Scout and can use them as routing context for additional public-source collection; a peer message is never evidence by itself.

`Round 1 -> Blackboard -> Per-Scout inbox -> Round 2 -> Final lineage`

Every round, inbox and response is preserved. Exact-source repetition does not count as independent scientific replication.

## Coordination versus deduplication

When two Scouts happen to receive the same exact query, the orchestrator may label one the deterministic lead and the others witnesses. Witnesses remain active and addressable; the label is a work-coordination hint, not identity suppression.

The final result stores 17 identity lineages separately, plus fact/source clusters and the complete communication log.

## SWARM_GENOME_LEDGER nervous-system binding

`swarm_genome_nervous_system.py` projects each completed orchestrated run into the canonical `SwarmGenomeLedger` without changing or weakening its append-only genealogy rules.

The binding creates genome nodes for:

- every Scout round anchor;
- every individual observation, even when several observations belong to one fact cluster;
- every orchestrator/peer message and peer-round response;
- every synthesized fact cluster.

Typed interaction edges preserve the communication semantics beside the canonical parent DAG. Examples include `SENT_BY_SCOUT`, `CARRIES_OBSERVATION`, `PEER_CONTEXT_FOR`, `REPLIES_TO`, `REPORTS_NEW_OBSERVATION`, `SUPPORTS_FACT_CLUSTER`, `CHALLENGES_FACT_CLUSTER` and `QUALIFIES_FACT_CLUSTER`.

A round-2 fact that did not exist for the same Scout in round 1 gets an `interaction_birth_record`. That record names the Scout, the new fact observations, the inbound peer-message set and the peer response that reported the result. It is deliberately marked `CONTEXTUAL_ASSOCIATION_ONLY__EXACT_TRIGGER_NOT_PROVEN`: the nervous system remembers the interaction context without inventing causal certainty.

The resulting artifact is written next to the orchestrator result as `GENOME_NERVOUS_SYSTEM.json`. Peer messages remain routing context rather than empirical evidence, duplicate source observations remain non-independent, conflicts/refutations remain in lineage, and Scout identities are never deduplicated.
