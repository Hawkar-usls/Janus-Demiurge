"""Adversarial offline contracts for ESSENCE R2 job-duration research."""
import datetime as dt
import math
import tempfile
from pathlib import Path
import unittest
from tools import janus_essence_duration_r2 as r2

def make_jobs(n=105, overlap=False):
    rows=[]
    base=dt.datetime(2026,10,1,tzinfo=dt.timezone.utc)
    for rid,repo in enumerate(r2.REPOS):
        for i in range(n):
            start=base+dt.timedelta(days=rid*25,minutes=i*(1 if overlap else 5))
            duration=90 if overlap and i==0 else 10+(i%8)*4+rid*3
            rows.append({
                "repo":repo,"job_id":10_000_000+rid*1000+i,
                "run_id":10_000+rid*1000+i, "workflow":"benchmark",
                "job":"predict-duration",
                "started_at":r2.iso(start),
                "completed_at":r2.iso(start+dt.timedelta(seconds=duration)),
                "duration_s":duration})
    return rows

class Contracts(unittest.TestCase):
    def test_api_path_cannot_escape_allowlist(self):
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_API_PATH"):
            r2.api("/users/someone", "")

    def test_timestamp_requires_zone(self):
        with self.assertRaisesRegex(ValueError,"NAIVE_TIMESTAMP"):
            r2.stamp("2026-01-01T00:00:00")

    def test_target_is_execution_not_queue_time(self):
        j=make_jobs(1)[0]
        row=r2.features([j])[0]
        self.assertEqual(row["y_s"],j["duration_s"])

    def test_overlapping_jobs_cannot_see_future_completion(self):
        jobs=make_jobs(2,overlap=True)
        rows=r2.features(jobs)
        self.assertEqual(rows[0]["prior_repo_count"],0)
        self.assertEqual(rows[1]["prior_repo_count"],0)

    def test_later_label_mutation_cannot_change_earlier_features(self):
        jobs=make_jobs(4)
        original=r2.features(jobs)
        jobs[-1]["duration_s"]=999
        jobs[-1]["completed_at"]=r2.iso(r2.stamp(jobs[-1]["started_at"])+dt.timedelta(seconds=999))
        changed=r2.features(jobs)
        self.assertEqual(original[0]["x"],changed[0]["x"])

    def test_bad_duration_must_fail(self):
        jobs=make_jobs(1)
        jobs[0]["duration_s"]=-10
        with self.assertRaisesRegex(ValueError,"JOB_DURATION_INTEGRITY"):
            r2.features(jobs)

    def test_duplicate_id_must_fail(self):
        jobs=make_jobs(2)
        jobs[1]["job_id"]=jobs[0]["job_id"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_JOB_ID"):
            r2.features(jobs)

    def test_split_with_embargo_is_disjoint(self):
        parts,_=r2.split(r2.features(make_jobs()))
        ids=[x["job_id"] for values in parts.values() for x in values]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertGreaterEqual(len(parts["holdout"]),20)
        for repo in r2.REPOS:
            tr=[v for v in parts["train"] if v["repo"]==repo]
            val=[v for v in parts["validation"] if v["repo"]==repo]
            hol=[v for v in parts["holdout"] if v["repo"]==repo]
            self.assertLess(tr[-1]["started_at"],val[0]["started_at"])
            self.assertLess(val[-1]["started_at"],hol[0]["started_at"])

    def test_embargo_purges_late_finished_labels_across_splits(self):
        jobs=make_jobs()
        for repo in r2.REPOS:
            seq=[j for j in jobs if j["repo"]==repo]
            for i in (int(len(seq)*.62)-1, int(len(seq)*.82)-1):
                start=r2.stamp(seq[i]["started_at"])
                seq[i]["duration_s"]=3600.0
                seq[i]["completed_at"]=r2.iso(start+dt.timedelta(hours=1))
        parts,summaries=r2.split(r2.features(jobs))
        for record in summaries:
            self.assertEqual(record["purged_late_finishes"],
                             {"train":1,"validation":1})
        for repo in r2.REPOS:
            a=[r for r in parts["train"] if r["repo"]==repo]
            b=[r for r in parts["validation"] if r["repo"]==repo]
            c=[r for r in parts["holdout"] if r["repo"]==repo]
            self.assertLess(max(r["completed_at"] for r in a),
                            min(r["started_at"] for r in b))
            self.assertLess(max(r["completed_at"] for r in b),
                            min(r["started_at"] for r in c))

    def test_train_and_independent_holdout_hard_hold(self):
        parts,_=r2.split(r2.features(make_jobs()))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,rows in parts.items():
                r2.save(root/(name+".json"),{
                    "schema":r2.SCHEMA,"split":name,
                    "provenance_sha256":"a"*64,"rows":rows})
            r2.train(root/"train.json",root/"validation.json",root/"ck")
            checkpoint=r2.load(root/"ck/duration_microcores.json")
            self.assertFalse(checkpoint["holdout_seen_by_trainer"])
            self.assertFalse(checkpoint["production_authority"])
            r2.verify(root/"holdout.json",root/"ck/duration_microcores.json",root/"result.json")
            report=r2.load(root/"result.json")
            self.assertEqual(report["production_gate"],
                             "HOLD_REQUIRES_EXTERNAL_PROSPECTIVE_REPLICATION")
            self.assertTrue(report["no_automatic_offspring"])
            self.assertTrue(math.isfinite(report["models"]["temporal_gene"]["mae_s"]))

    def test_frozen_future_gate_never_trains_on_future_jobs(self):
        historical=make_jobs()
        # Historical model and labels predate a fixed prospective cutoff.
        for j in historical:
            start=r2.stamp(j["started_at"])-dt.timedelta(days=110)
            j["started_at"]=r2.iso(start)
            j["completed_at"]=r2.iso(start+dt.timedelta(seconds=j["duration_s"]))
        previous,_=r2.split(r2.features(historical))
        future=make_jobs()
        base=dt.datetime(2026,11,5,tzinfo=dt.timezone.utc)
        for j in future:
            source_index=(j["job_id"]-10_000_000)//1000
            seq_index=(j["job_id"]-10_000_000)%1000
            start=base+dt.timedelta(days=source_index,minutes=seq_index*5)
            j["job_id"]+=1_000_000
            j["started_at"]=r2.iso(start)
            j["completed_at"]=r2.iso(start+dt.timedelta(seconds=j["duration_s"]))
        new_parts,_=r2.split(r2.features(future))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,rs in previous.items():
                r2.save(root/(name+".json"),{
                    "schema":r2.SCHEMA,"split":name,"provenance_sha256":"a"*64,"rows":rs})
            r2.train(root/"train.json",root/"validation.json",root/"ck")
            for name,rs in new_parts.items():
                r2.save(root/(name+"-new.json"),{
                    "schema":r2.SCHEMA,"split":name,"provenance_sha256":"b"*64,"rows":rs})
            paths=[root/(name+"-new.json") for name in ("train","validation","holdout")]
            report=r2.verify_future(root/"ck/duration_microcores.json",
                      "2026-11-01T00:00:00+00:00",paths,root/"future.json")
            self.assertGreaterEqual(report["future_job_count"],r2.GATE_MIN_ROWS)
            self.assertFalse(report["weights_updated"])
            self.assertEqual(report["production_gate"],
                             "HOLD_REQUIRES_EXTERNAL_PROSPECTIVE_REPLICATION")
            self.assertEqual(set(report["models"]),
                             {"frozen_train_median","frozen_repo_median","no_gene","temporal_gene"})
            self.assertEqual(report["method"],"FROZEN_PRIOR_RUN_PROSPECTIVE")

    def test_future_verifier_rejects_postdated_training(self):
        past,_=r2.split(r2.features(make_jobs()))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,rs in past.items():
                r2.save(root/(name+".json"),{
                    "schema":r2.SCHEMA,"split":name,"provenance_sha256":"c"*64,"rows":rs})
            r2.train(root/"train.json",root/"validation.json",root/"ck")
            with self.assertRaisesRegex(ValueError,"FROZEN_MODEL_TRAINED_AFTER_FUTURE_CUTOFF"):
                r2.verify_future(root/"ck/duration_microcores.json",
                    "2026-10-01T00:00:00+00:00",
                    [root/"train.json",root/"validation.json",root/"holdout.json"],
                    root/"bad_future.json")

    def test_tampered_holdout_provenance_fails(self):
        parts,_=r2.split(r2.features(make_jobs()))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,rows in parts.items():
                r2.save(root/(name+".json"),{
                    "schema":r2.SCHEMA,"split":name,
                    "provenance_sha256":"b"*64 if name=="holdout" else "a"*64,
                    "rows":rows})
            r2.train(root/"train.json",root/"validation.json",root/"ck")
            with self.assertRaisesRegex(ValueError,"PROVENANCE_MISMATCH"):
                r2.verify(root/"holdout.json",root/"ck/duration_microcores.json",root/"result.json")

if __name__=="__main__":
    unittest.main()
