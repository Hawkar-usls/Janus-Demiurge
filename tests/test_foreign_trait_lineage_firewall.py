import unittest

from spiral_evolution import SpiralLedger
from swarm_genome_ledger import SwarmGenomeLedger


def turn(entity, state, ledger=None):
    ledger = ledger or SpiralLedger(entity)
    return ledger, ledger.ascend(
        state_before=state,
        candidate_state=state,
        active_state_after=state,
        promoted=True,
    )


class TraitLineageFirewallTests(unittest.TestCase):
    def test_legacy_extra_parent_is_denied(self):
        genome = SwarmGenomeLedger()
        a, a0 = turn("A", {"trait": "foreign"})
        parent = genome.register_spiral_turn(a0)
        b, b0 = turn("B", {"trait": "janus"})
        with self.assertRaisesRegex(ValueError, "FOREIGN_OR_UNTRUSTED_IDENTITY_PARENT"):
            genome.register_spiral_turn(b0, extra_parent_ids=[parent.genome_id])

    def test_approved_janus_extra_parent_is_allowed(self):
        genome = SwarmGenomeLedger()
        a, a0 = turn("A", {"trait": "janus"})
        parent = genome.register_spiral_turn(
            a0,
            source_class="JANUS_OWNED",
            lineage_id="JANUS:DEMIURGE:A",
            approved_for_identity_derivation=True,
        )
        b, b0 = turn("B", {"trait": "child"})
        child = genome.register_spiral_turn(
            b0,
            extra_parent_ids=[parent.genome_id],
            source_class="JANUS_OWNED",
            lineage_id="JANUS:DEMIURGE:B",
            approved_for_identity_derivation=True,
        )
        self.assertIn(parent.genome_id, child.parent_ids)

    def test_false_approval_without_janus_lineage_is_denied(self):
        genome = SwarmGenomeLedger()
        a, a0 = turn("A", {})
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRES_JANUS_OWNED_LINEAGE"):
            genome.register_spiral_turn(
                a0,
                source_class="MODEL_GENERATED_FOREIGN",
                lineage_id="FOREIGN:TEACHER",
                approved_for_identity_derivation=True,
            )

    def test_same_entity_legacy_chain_remains_backward_compatible(self):
        genome = SwarmGenomeLedger()
        spiral = SpiralLedger("A")
        t0 = spiral.ascend(state_before=0, candidate_state=1, active_state_after=1, promoted=True)
        n0 = genome.register_spiral_turn(t0)
        t1 = spiral.ascend(state_before=1, candidate_state=2, active_state_after=2, promoted=True)
        n1 = genome.register_spiral_turn(t1)
        self.assertEqual(n1.primary_parent_id, n0.genome_id)
        genome.validate()

    def test_explicit_janus_node_is_future_parent_eligible(self):
        genome = SwarmGenomeLedger()
        a, a0 = turn("A", {})
        node = genome.register_spiral_turn(
            a0,
            source_class="JANUS_OWNED",
            lineage_id="JANUS:CORE:A",
            approved_for_identity_derivation=True,
        )
        self.assertTrue(node.trusted_as_cross_entity_parent)


if __name__ == "__main__":
    unittest.main()
