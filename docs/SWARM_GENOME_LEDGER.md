# SWARM_GENOME_LEDGER

`SWARM_GENOME_LEDGER` joins all per-entity `SpiralLedger` histories into one append-only JANUS genealogy.

The model has two architectural strands:

- identity/state: what an entity currently is;
- evidence/provenance: why it became that state, including failed attempts and lessons.

Every admitted spiral turn becomes one immutable genome node. Same-entity turns link to their previous turn automatically. New specialized or synthesized entities may name explicit cross-entity parents.

Supported traversal is bidirectional:

- ancestor -> descendants via the child index;
- current node -> all origins via parent links.

Selection changes the active frontier only. It never deletes ancestry. Failure remains evidence. Recovery is another descendant turn, not a reset.

The words DNA/genome are an architecture metaphor for lineage and paired state/provenance strands; this code makes no biological claim.
