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
