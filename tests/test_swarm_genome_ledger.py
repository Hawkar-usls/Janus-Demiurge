from __future__ import annotations

import unittest

from spiral_evolution import SpiralLedger
from swarm_genome_ledger import GENOME_LAWS, SwarmGenomeLedger


class SwarmGenomeLedgerTests(unittest.TestCase):
    def _turn(self, ledger: SpiralLedger, state, *, promoted=True, lesson=None):
        return ledger.ascend(
            state_before=ledger.turns[-1].active_state_after if ledger.turns else None,
            candidate_state=state,
            active_state_after=state if promoted or not ledger.turns else ledger.turns[-1].active_state_after,
            lessons=[lesson] if lesson else [],
            promoted=promoted,
        )

    def test_same_entity_turns_form_primary_genealogy(self):
        spiral = SpiralLedger("anchor")
        genome = SwarmGenomeLedger()
        n0 = genome.register_spiral_turn(self._turn(spiral, {"status": "FRESH"}))
        n1 = genome.register_spiral_turn(self._turn(spiral, {"status": "RECOVERED"}))

        self.assertEqual(n1.primary_parent_id, n0.genome_id)
        self.assertEqual([n.genome_id for n in genome.ancestors(n1.genome_id)], [n0.genome_id])
        self.assertEqual([n.genome_id for n in genome.descendants(n0.genome_id)], [n1.genome_id])
        genome.validate()

    def test_failure_remains_on_evidence_strand_without_replacing_identity(self):
        spiral = SpiralLedger("gladius")
        genome = SwarmGenomeLedger()
        first = self._turn(spiral, {"status": "FRESH", "score": 5})
        n0 = genome.register_spiral_turn(first)
        failed = spiral.ascend(
            state_before=first.active_state_after,
            candidate_state={"status": "BAD_CANDIDATE", "score": -3},
            active_state_after=first.active_state_after,
            lessons=["candidate harmed radio health"],
            promoted=False,
            outcome="INTEGRATED_LESSON",
        )
        n1 = genome.register_spiral_turn(failed)

        self.assertEqual(n1.identity_strand, n0.identity_strand)
        self.assertEqual(n1.evidence_strand["outcome"], "INTEGRATED_LESSON")
        self.assertIn("candidate harmed radio health", n1.evidence_strand["lessons"])
        genome.validate()

    def test_cross_entity_child_can_name_explicit_parent(self):
        parent_spiral = SpiralLedger("scout-template")
        child_spiral = SpiralLedger("scout-cosmos")
        genome = SwarmGenomeLedger()
        parent = genome.register_spiral_turn(self._turn(parent_spiral, {"role": "SCOUT_TEMPLATE"}))
        child_turn = self._turn(child_spiral, {"role": "COSMOS_SCOUT"})
        child = genome.register_spiral_turn(
            child_turn,
            extra_parent_ids=[parent.genome_id],
            relation="DERIVED_FROM",
        )

        self.assertIn(parent.genome_id, child.parent_ids)
        self.assertIn(child.genome_id, [n.genome_id for n in genome.descendants(parent.genome_id)])
        self.assertEqual(genome.trace_to_origins(child.genome_id), [[parent.genome_id, child.genome_id]])
        genome.validate()

    def test_multiple_parents_create_multiple_origin_paths(self):
        a = SpiralLedger("a")
        b = SpiralLedger("b")
        c = SpiralLedger("c")
        genome = SwarmGenomeLedger()
        na = genome.register_spiral_turn(self._turn(a, {"x": 1}))
        nb = genome.register_spiral_turn(self._turn(b, {"x": 2}))
        nc = genome.register_spiral_turn(
            self._turn(c, {"x": 3}),
            extra_parent_ids=[na.genome_id, nb.genome_id],
            relation="SYNTHESIZED_FROM",
        )
        paths = genome.trace_to_origins(nc.genome_id)
        self.assertEqual(len(paths), 2)
        self.assertIn([na.genome_id, nc.genome_id], paths)
        self.assertIn([nb.genome_id, nc.genome_id], paths)
        genome.validate()

    def test_no_delete_api_and_laws_are_present(self):
        genome = SwarmGenomeLedger()
        self.assertFalse(hasattr(genome, "delete_node"))
        self.assertFalse(hasattr(genome, "remove_node"))
        self.assertFalse(hasattr(genome, "purge_node"))
        self.assertIn("ANCESTRY_IS_APPEND_ONLY", GENOME_LAWS)
        self.assertIn("FAILURE_REMAINS_IN_LINEAGE", GENOME_LAWS)


if __name__ == "__main__":
    unittest.main()
