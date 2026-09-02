import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from janus_model.attribution import (
    build_variant_specs,
    classify_signal,
    load_verified_packs,
    shuffle_records,
)


class JanusAttributionTests(unittest.TestCase):
    def _manifest(self):
        rows = []
        for i in range(8):
            rows.append({
                "id": f"C{i}",
                "repository": f"Hawkar-usls/R{i}",
                "head_sha": f"{i + 1:040x}",
                "cohort": "CORE_5" if i < 5 else "EXTENDED_3",
                "contributed_bytes": 10,
                "training_pack_sha256": "0" * 64,
            })
        return {
            "schema": "janus.keymaster.learning_contribution_manifest.v2",
            "status": "READY_8_OF_8",
            "contributor_count": 8,
            "contributors": rows,
        }

    def test_variant_matrix_has_exact_full_core_loo_extended_and_shuffle_controls(self):
        specs = build_variant_specs(self._manifest())
        ids = {row["variant_id"] for row in specs}
        self.assertEqual(len(specs), 17)
        self.assertIn("FULL_8_OF_8", ids)
        self.assertIn("CORE_5_OF_5", ids)
        self.assertIn("EXTENDED_3_OF_3", ids)
        self.assertIn("FULL_8_SHUFFLED_RECORD_ORDER_CONTROL", ids)
        self.assertEqual(sum(row["kind"] == "FULL_LEAVE_ONE_OUT" for row in specs), 8)
        self.assertEqual(sum(row["kind"] == "CORE_LEAVE_ONE_OUT" for row in specs), 5)
        self.assertTrue(all(len(row["included_ids"]) == 7 for row in specs if row["kind"] == "FULL_LEAVE_ONE_OUT"))
        self.assertTrue(all(len(row["included_ids"]) == 4 for row in specs if row["kind"] == "CORE_LEAVE_ONE_OUT"))

    def test_signal_classification_is_bounded_and_directional(self):
        self.assertEqual(classify_signal(0.01, 0.02), "SUPPORTIVE_SIGNAL")
        self.assertEqual(classify_signal(-0.01, -0.02), "ADVERSE_SIGNAL")
        self.assertEqual(classify_signal(0.01, -0.02), "MIXED_SIGNAL")
        self.assertEqual(classify_signal(0.0001, -0.0001), "INDETERMINATE_SIGNAL")

    def test_shuffle_changes_order_without_dropping_records(self):
        text = "".join(
            f"\n<JANUS_KEYMASTER_RECORD contributor=\"C{i}\">payload{i}</JANUS_KEYMASTER_RECORD>\n"
            for i in range(12)
        )
        shuffled = shuffle_records(text, 7)
        self.assertNotEqual(text, shuffled)
        for i in range(12):
            self.assertIn(f"payload{i}", shuffled)
        self.assertEqual(shuffled.count("</JANUS_KEYMASTER_RECORD>"), 12)

    def test_verified_packs_require_exact_hash_and_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packs = root / "packs"
            packs.mkdir()
            manifest = self._manifest()
            for row in manifest["contributors"]:
                raw = (row["id"] * 10).encode("utf-8")[:10]
                path = packs / f"{row['id']}.txt"
                path.write_bytes(raw)
                row["contributed_bytes"] = len(raw)
                row["training_pack_sha256"] = hashlib.sha256(raw).hexdigest()
            loaded = load_verified_packs(root, manifest)
            self.assertEqual(set(loaded), {f"C{i}" for i in range(8)})
            bad = json.loads(json.dumps(manifest))
            bad["contributors"][0]["training_pack_sha256"] = "f" * 64
            with self.assertRaisesRegex(RuntimeError, "PACK_HASH_MISMATCH"):
                load_verified_packs(root, bad)


if __name__ == "__main__":
    unittest.main()
