import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import reverse_narrative_transform as rnt
import reverse_narrative_runner as runner


class TrumpReverseNarrativeTransformTests(unittest.TestCase):
    def test_reverse_is_exact_reordering_only(self):
        seq = [{"x": 1}, {"x": 2}, {"x": 3}]
        out = rnt.schedule(seq, "REVERSE")
        self.assertEqual(out, list(reversed(seq)))
        self.assertEqual(
            sorted(rnt._item_digests(seq)),
            sorted(rnt._item_digests(out)),
        )

    def test_bidirectional_is_deterministic(self):
        seq = list(range(6))
        self.assertEqual(rnt.schedule(seq, "BIDIRECTIONAL"), [0, 5, 1, 4, 2, 3])

    def test_mutation_is_rejected(self):
        seq = [{"x": 1}, {"x": 2}]
        with self.assertRaisesRegex(rnt.ReverseNarrativeError, "CONTENT_CHANGED"):
            rnt.verify_reordering(seq, [{"x": 2}, {"x": 99}], "REVERSE")

    def test_receipt_never_promotes_theorem_authority(self):
        receipt = rnt.transform_receipt([1, 2, 3], "REVERSE")
        self.assertFalse(receipt["semantics_changed"])
        self.assertFalse(receipt["witness_changed"])
        self.assertFalse(receipt["verifier_changed"])
        self.assertFalse(receipt["theorem_face_changed"])
        self.assertFalse(receipt["authority"]["proof_authority"])
        self.assertEqual(receipt["scientific_boundary"]["P_VS_NP"], "OPEN")

    def test_frozen_contract_is_fixed_before_live_run(self):
        self.assertEqual(runner.BUDGET_PROFILES, 2)
        self.assertEqual(len(runner.FROZEN_WITNESSES), 3)
        self.assertEqual(
            [w["id"] for w in runner.FROZEN_WITNESSES],
            ["UNIT_UNSAT", "FOUR_CLAUSE_2SAT_UNSAT", "SMALL_3CNF_SAT"],
        )


if __name__ == "__main__":
    unittest.main()
