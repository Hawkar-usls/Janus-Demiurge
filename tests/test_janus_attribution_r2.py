import unittest

from janus_model import attribution_r2 as r2


IDS = [
    ("TOPA", "CORE_5"),
    ("TRANCEPTION", "CORE_5"),
    ("LAPIS", "CORE_5"),
    ("IO_PUBLIC", "CORE_5"),
    ("FAST_CAT_SHAITAN", "CORE_5"),
    ("FUNDAMENTUM", "EXTENDED_3"),
    ("DEMI_HEAD", "EXTENDED_3"),
    ("AURA_ORACLE", "EXTENDED_3"),
]


def ledger(seed, checkpoint="a" * 64, full="SUPPORTIVE_SIGNAL", core="SUPPORTIVE_SIGNAL"):
    attribution = []
    for cid, cohort in IDS:
        row = {
            "id": cid,
            "repository": f"Hawkar-usls/{cid}",
            "head_sha": "b" * 40,
            "cohort": cohort,
            "full_8_marginal_adaptive_loss": 0.01,
            "full_8_marginal_anchor_loss": 0.02,
            "full_8_signal": full,
        }
        if cohort == "CORE_5":
            row.update({
                "core_5_marginal_adaptive_loss": 0.01,
                "core_5_marginal_anchor_loss": 0.02,
                "core_5_signal": core,
            })
        attribution.append(row)
    return {
        "schema": r2.SINGLE_SCHEMA,
        "status": "COMPLETE_SINGLE_SEED_DIAGNOSTIC",
        "variant_count": 17,
        "checkpoint_sha256": checkpoint,
        "source_digest": "c" * 64,
        "keymaster_contribution_sha256": "d" * 64,
        "keymaster_training_pack_sha256": "e" * 64,
        "steps_per_variant": 80,
        "batch_size": 12,
        "learning_rate": 0.0003,
        "seed": seed,
        "attribution": attribution,
        "claim_ceiling": {"single_seed_establishes_causality": False},
    }


def checkpoint(seq, cpchar, full="SUPPORTIVE_SIGNAL", core="SUPPORTIVE_SIGNAL"):
    ledgers = [ledger(seed, checkpoint=cpchar * 64, full=full, core=core) for seed in (7331, 9157, 12011)]
    return r2.build_checkpoint_evidence(ledgers, sequence_run_id=seq)


class AttributionR2Tests(unittest.TestCase):
    def test_one_checkpoint_remains_unresolved_even_with_three_agreeing_seeds(self):
        current = checkpoint(100, "a")
        summary = r2.build_r2_summary(current, [], min_checkpoints=3)
        self.assertEqual(summary["status"], "ACCUMULATING_SUCCESSIVE_CHECKPOINTS")
        self.assertTrue(all(row["class"] == "UNRESOLVED" for row in summary["attribution"]))

    def test_three_successive_supportive_checkpoints_become_stable_supportive(self):
        c1 = checkpoint(100, "a")
        c2 = checkpoint(200, "b")
        c3 = checkpoint(300, "c")
        summary = r2.build_r2_summary(c3, [c1, c2], min_checkpoints=3)
        self.assertEqual(summary["status"], "REPLICATED_EVIDENCE_READY")
        self.assertTrue(all(row["class"] == "STABLE_SUPPORTIVE" for row in summary["attribution"]))

    def test_reproducible_full_core_disagreement_is_context_dependent(self):
        c1 = checkpoint(100, "a", full="SUPPORTIVE_SIGNAL", core="ADVERSE_SIGNAL")
        c2 = checkpoint(200, "b", full="SUPPORTIVE_SIGNAL", core="ADVERSE_SIGNAL")
        c3 = checkpoint(300, "c", full="SUPPORTIVE_SIGNAL", core="ADVERSE_SIGNAL")
        summary = r2.build_r2_summary(c3, [c1, c2], min_checkpoints=3)
        classes = {row["id"]: row["class"] for row in summary["attribution"]}
        self.assertEqual(classes["TOPA"], "CONTEXT_DEPENDENT")
        self.assertEqual(classes["FUNDAMENTUM"], "STABLE_SUPPORTIVE")

    def test_seed_disagreement_prevents_stable_class(self):
        ledgers = [
            ledger(7331, checkpoint="f" * 64, full="SUPPORTIVE_SIGNAL"),
            ledger(9157, checkpoint="f" * 64, full="ADVERSE_SIGNAL"),
            ledger(12011, checkpoint="f" * 64, full="SUPPORTIVE_SIGNAL"),
        ]
        current = r2.build_checkpoint_evidence(ledgers, sequence_run_id=400)
        self.assertTrue(all(row["full_8_consensus"] == "MIXED_SIGNAL" for row in current["contributors"]))


if __name__ == "__main__":
    unittest.main()
