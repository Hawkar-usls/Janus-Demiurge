"""Ocean R3.1 snapshot/metrics admission regression tests: no PyTorch required."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from experiments.ocean_transformer.ocean_r31_admission import (
    audit_snapshot,evaluate,sha_bytes,digest,
)

def fixture(root):
    root=Path(root)
    events=[]
    for i in range(240):
        events.append({
            "commit":f"{i+1:040x}",
            "timestamp":"2026-01-01T00:00:00+00:00",
            "first_path":f"data/experiment_{i:04d}.json",
            "representative_label":"data/experiment"
        })
    seq=[i%3 for i in range(len(events))]
    snap={
        "schema":"janus.meta_next.snapshot.v1",
        "source_repository":"Hawkar-usls/janus-meta-registry",
        "source_head":"a"*40,
        "events":events,"events_count":len(events),
        "train_cutoff_idx":int(len(events)*.70),
        "sequence":seq,
        "labels":["catA","catB","OTHER"]
    }
    sp=root/"snapshot.json"
    sp.write_text(json.dumps(snap))
    ck=root/"weights.pt"
    ck.write_bytes(b"frozen-synthetic-weight-bytes-test-only")
    train=int(len(events)*.7)-16
    test=len(events)-(int(len(events)*.85)+16)
    rep={
        "schema":"janus.meta_next.train_result.v1",
        "production_promotion":False,
        "source_snapshot_sha256":sha_bytes(sp.read_bytes()),
        "candidate_weights_sha256":sha_bytes(ck.read_bytes()),
        "meta_head":snap["source_head"],
        "events_count":len(events),
        "test_event_indices":test,
        "train_event_indices":train,
        "test_model":{"n":test,"accuracy":0.73},
        "test_baselines":{"majority_accuracy":0.76,
                          "markov_accuracy":0.77}
    }
    rp=root/"report.json";rp.write_text(json.dumps(rep))
    return sp,rp,ck

class R31Ocean(unittest.TestCase):
    def test_actual_hashes_and_baselines_produce_hold(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            pack,out=evaluate(s,r,c)
            self.assertEqual(len(pack["train_events"]),152)
            self.assertEqual(pack["test_target_count"],20)
            self.assertEqual(out["status"],"NO_REPRODUCIBLE_BASELINE_GAIN")
            self.assertAlmostEqual(out["absolute_accuracy_gain_over_strongest_baseline"],-.04)
            self.assertFalse(out["production_model_promotion"])
            self.assertFalse(out["paired_significance_estimated"])
            self.assertEqual(out["scientific_admission"],"HOLD")
            self.assertEqual(out["receipt_sha256"],
                digest({k:v for k,v in out.items() if k!="receipt_sha256"}))

    def test_snapshot_source_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            obj=json.loads(s.read_text())
            obj["source_head"]="b"*40;s.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"SNAPSHOT_SHA_MISMATCH"):
                evaluate(s,r,c)

    def test_candidate_weight_file_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td);c.write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError,"CHECKPOINT_SHA_MISMATCH"):
                evaluate(s,r,c)

    def test_quarantine_event_rejected_even_when_reports_match(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            obj=json.loads(s.read_text())
            obj["events"][0]["first_path"]=(
                "data/observations/public_source_quality/JANUS-R3-QUALITY.json")
            s.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"QUARANTINE_IN_TRAINING_CHRONOLOGY"):
                audit_snapshot(s)

    def test_training_holdout_cutoff_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            obj=json.loads(s.read_text())
            obj["train_cutoff_idx"]=235;s.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,"TRAIN_CUTOFF"):
                audit_snapshot(s)

    def test_better_public_score_still_not_scientific_admission(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            j=json.loads(r.read_text())
            j["test_model"]["accuracy"]=.85;r.write_text(json.dumps(j))
            pack,out=evaluate(s,r,c)
            self.assertEqual(out["status"],
                "DEVELOPMENT_GAIN_REQUIRES_NEW_PROSPECTIVE_TEST")
            self.assertFalse(out["production_model_promotion"])
            self.assertFalse(out["independent_external_blind_evaluation"])

    def test_wrong_test_denominator_blocks_claim(self):
        with tempfile.TemporaryDirectory() as td:
            s,r,c=fixture(td)
            j=json.loads(r.read_text())
            j["test_model"]["n"]=15;r.write_text(json.dumps(j))
            with self.assertRaisesRegex(ValueError,"METRIC_DENOMINATOR"):
                evaluate(s,r,c)

if __name__=="__main__":
    unittest.main()
