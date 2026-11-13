"""Offline adversarial checks for dated, held-out ESSENCE R1 learning."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from tools import janus_essence_real_history_r1 as r1


def histories(n=140):
    start=datetime(2026,8,1,tzinfo=timezone.utc)
    return {
        name:[{"run_id":100000*i+j,
               "timestamp":(start+timedelta(hours=j)).isoformat(),
               "label":int(j%7==0 or j%19==0)}
              for j in range(n)]
        for i,name in enumerate(r1.REPOS,1)
    }


class RealHistoryR1Tests(unittest.TestCase):
    def test_chronological_lookbacks_and_embargo(self):
        groups,info=r1.split_history(histories())
        self.assertEqual(len(groups),3)
        self.assertEqual(info["embargo"],8)
        self.assertTrue(info["holdout_not_given_to_trainer"])
        by_id=[{(r["repo"],r["run_id"]) for r in s["rows"]} for s in groups.values()]
        self.assertFalse(by_id[0]&by_id[1] or by_id[0]&by_id[2] or by_id[1]&by_id[2])
        self.assertGreater(len(groups["holdout"]["rows"]),30)
        self.assertEqual(groups["train"]["provenance_sha256"],groups["holdout"]["provenance_sha256"])
        for name in r1.REPOS:
            tr=[x for x in groups["train"]["rows"] if x["repo"]==name]
            va=[x for x in groups["validation"]["rows"] if x["repo"]==name]
            ho=[x for x in groups["holdout"]["rows"] if x["repo"]==name]
            self.assertLess(tr[-1]["timestamp"],va[0]["timestamp"])
            self.assertLess(va[-1]["timestamp"],ho[0]["timestamp"])

    def test_synthetic_fixture_is_not_misrepresented_as_real_fetch(self):
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_REPO"):
            r1.fetch_history("attacker/foreign",pages=1)
        too_few=histories(30)
        with self.assertRaisesRegex(ValueError,"TOO_FEW_REAL_RUNS"):
            r1.split_history(too_few)
        bad=histories()
        bad[r1.REPOS[0]][10]["timestamp"]="2050-01-01T00:00:00+00:00"
        with self.assertRaisesRegex(ValueError,"INVALID_REAL_CHRONOLOGY"):
            r1.split_history(bad)

    def test_training_updates_weights_but_holdout_is_separate(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            splits,_=r1.split_history(histories())
            for k,obj in splits.items():
                r1.write(path/(k+".json"),obj)
            r1.train(path/"train.json",path/"validation.json",path/"weights",steps=20)
            t=r1.read(path/"weights/train_receipt.json")
            self.assertFalse(t["heldout_seen_by_trainer"])
            self.assertFalse(t["weights_production_authority"])
            self.assertEqual(set(t["variants"]),{"baseline_no_replay","yaksa_bounded_replay"})
            r1.verify(path/"holdout.json",path/"weights/train_receipt.json",
                      path/"weights",path/"verifier.json")
            v=r1.read(path/"verifier.json")
            self.assertEqual(v["history_scope"],"LATEST_THREE_REPOS_NOT_WHOLE_META_REGISTRY")
            self.assertFalse(v["production_promotion"])
            self.assertGreater(v["heldout_rows"],30)

    def test_holdout_tamper_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp)
            splits,_=r1.split_history(histories())
            for key,obj in splits.items():r1.write(d/(key+".json"),obj)
            tampered=r1.read(d/"holdout.json")
            tampered["provenance_sha256"]="f"*64
            r1.write(d/"holdout.json",tampered)
            with self.assertRaisesRegex(ValueError,"SPLIT_SOURCE_MISMATCH"):
                r1.load_split(d/"holdout.json","holdout",splits["train"]["provenance_sha256"])

    def test_causal_input_uses_only_prior_observed_outcomes(self):
        h=histories()
        groups,_=r1.split_history(h)
        lookup={r["run_id"]:j for name in r1.REPOS for j,r in enumerate(h[name])}
        for split in groups.values():
            for row in split["rows"]:
                j=lookup[row["run_id"]]
                prior=h[row["repo"]][j-8:j]
                self.assertEqual(row["x"][1:],[z["label"] for z in prior])
                self.assertEqual(row["y"],h[row["repo"]][j]["label"])


if __name__=="__main__":
    unittest.main()
