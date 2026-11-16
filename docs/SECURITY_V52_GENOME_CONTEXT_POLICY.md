# ESSENCE v5.2: contextual evidence is not identity lineage

The existing `SwarmGenomeLedger.register_spiral_turn` requires an approved, JANUS-owned lineage before a node can be used as an `extra_parent_id`. That is intentional and remains unchanged.

The original `swarm_genome_nervous_system.py` projected all peer messages, observations, handoffs and fact clusters as extra identity parents. This caused the valid provenance firewall to reject previously accepted visualization and scout self-tests.

The repair keeps only same-entity spiral ancestry in the canonical identity DAG. Peer/evidence relations are written to `typed_interaction_edges` and point to existing nodes, with no authorization to derive identity. The builder verifies linked nodes exist and denies self-referential contextual links. Tests assert that a shared source's two observations remain distinct and that both links are contextual, not independently replicated evidence or identity parents.

This is a *provenance correction*, not proof of neural efficiency or new science. Check the 17-Scout read-only CI and existing regressions before merging.
