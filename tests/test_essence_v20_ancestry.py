"""ESSENCE v2.0: chronological trust and cross-run lineage archive (research)."""
from __future__ import annotations
import copy
import datetime
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools import essence_v19_gradirnya as e
from tools import essence_v20_ancestry as v


class V20AncestryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name)
        src=cls.root/"dataset"
        src.mkdir()
        for day in range(44):
            dt=(datetime.date(2026,7,1)+datetime.timedelta(days=day)).isoformat()
            for j,tag in enumerate(("LINEAR","TRUMP","OSIRIS","CONNECTION","ECHO")):
                (src/f"JANUS-{tag}-{dt}-CELL{day}-{j}.json").write_text(
                    json.dumps({"schema":"trial","source":j,f"feature_{j}":True,"date":dt}))
        cls.manifest=e.prepare(src,"a"*40,cls.root/"split")
        cls.child=e.train(0,e.read_json(cls.root/"split"/"train.json"),
                          e.read_json(cls.root/"split"/"validation.json"),
                          cls.manifest,cls.root/"cell-0",steps=20)
        cls.weight=(cls.root/"cell-0"/"offspring.pt").read_bytes()
        cls.verdict=e.verify(0,e.read_json(cls.root/"split"/"holdout.json"),
                             cls.manifest,cls.child,cls.root/"cell-0"/"offspring.pt")

    def synthetic_positive(self):
        # This is an ADVERSARIAL CONTRACT FIXTURE, not external evidence.
        row=copy.deepcopy(self.verdict)
        row.update(gate="RESEARCH_HISTORICAL_DATE_HOLDOUT_GAIN",
                   diversity_gate=True,heldout_represented_classes=5,
                   heldout_majority_fraction=0.25,nll_gain_vs_prior=0.1,
                   accuracy_gain_vs_prior=0.08)
        row["receipt_sha256"]=e.seal({k:w for k,w in row.items() if k!="receipt_sha256"})
        return row

    def test_reject_current_failed_holdout_even_if_gradients_real(self):
        with self.assertRaisesRegex(ValueError,"NO_INDEPENDENT_RESEARCH_HOLDOUT_GAIN"):
            v.validate_verified_parent(self.manifest,self.child,self.verdict,self.weight,0)

    def test_fake_positive_contract_validates_hashes_but_is_not_scientific_proof(self):
        candidate=self.synthetic_positive()
        # A self-hashed local fixture tests consistency; github origin validation
        # and independent data custody MUST be verified separately.
        metadata=v.validate_verified_parent(self.manifest,self.child,candidate,self.weight,0)
        self.assertEqual(metadata["parent_weight_sha256"],self.child["final_weights_sha256"])
        self.assertFalse(metadata["production_authority"])
        self.assertTrue(metadata["research_only"])

    def test_modified_checkpoint_bytes_rejected(self):
        with self.assertRaisesRegex(ValueError,"PARENT_WEIGHTS_SHA_MISMATCH"):
            v.validate_verified_parent(self.manifest,self.child,self.synthetic_positive(),
                                       self.weight+b"corrupt",0)

    def test_bounded_ancestry(self):
        with self.assertRaisesRegex(ValueError,"ANCESTRY_DEPTH_EXHAUSTED"):
            v.validate_verified_parent(self.manifest,self.child,self.synthetic_positive(),
                                       self.weight,0,depth=v.MAX_ANCESTOR_DEPTH)

    def test_archive_has_explicit_hold_without_fake_parent(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)
            (base/"child"/"cell-0").mkdir(parents=True)
            (base/"verify").mkdir()
            (base/"child"/"cell-0"/"lineage.json").write_text(json.dumps(self.child))
            (base/"child"/"cell-0"/"offspring.pt").write_bytes(self.weight)
            (base/"verify"/"cell-0.json").write_text(json.dumps(self.verdict))
            idx=v.pack_run(self.root/"split"/"manifest.json",base/"child",base/"verify",
                           base/"archive",run_id=100,run_sha="c"*40)
            self.assertEqual(idx["status"],"HOLD_NO_ADMISSIBLE_PARENT")
            self.assertEqual(idx["accepted_cells"],[])
            self.assertEqual(len(idx["rejected_cells"]),6)
            self.assertEqual(list((base/"archive").glob("**/*.pt")),[])
            self.assertFalse(idx["automatic_promotion"])

    def test_only_trusted_main_successful_runs_selectable(self):
        def art(rid,aid):
            return {"id":aid,"name":f"essence-v20-reviewed-archive-{rid}",
                    "expired":False,"workflow_run":{"id":rid}}
        good={"status":"completed","conclusion":"success","head_branch":"main",
              "event":"schedule","path":"a/b/"+v.WORKFLOW,"head_sha":"d"*40}
        runs={101:good,102:dict(good,head_branch="research"),
              103:dict(good,conclusion="failure")}
        selected=v.select_archive([art(101,1),art(102,2),art(103,3)],runs,110)
        self.assertEqual(selected,[(101,1,"d"*40)])
        self.assertEqual(v.select_archive([art(101,1)],runs,101),[])
        with self.assertRaisesRegex(ValueError,"FOREIGN_PARENT_REPOSITORY_DENIED"):
            v.select_archive([],{},100,repository="some-other/repo")

    def test_zip_traversal_and_unlisted_files_denied(self):
        index={"schema":v.SCHEMA,"source_repository":v.OWNER_REPO,
               "origin_run_id":101,"origin_main_sha":"c"*40,
               "origin_workflow":v.WORKFLOW,"source_commit":"a"*40,
               "source_dataset_sha256":"b"*64,"accepted_cells":[],
               "rejected_cells":[],"parent_meta_sha256":{},"status":"HOLD_NO_ADMISSIBLE_PARENT",
               "external_blind_quality_proven":False,"target_device_proven":False,
               "real_service_rollback_proven":False,"production_authority":False,
               "automatic_promotion":False}
        index["receipt_sha256"]=e.seal(index)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,"w") as z:
            z.writestr("index.json",json.dumps(index))
        result,content=v.decode_archive(buffer.getvalue(),101,"c"*40)
        self.assertEqual(result["accepted_cells"],[])
        self.assertIn("index.json",content)
        invalid=io.BytesIO()
        with zipfile.ZipFile(invalid,"w") as z:
            z.writestr("index.json",json.dumps(index))
            z.writestr("../escape.pt",self.weight)
        with self.assertRaisesRegex(ValueError,"UNSAFE_PARENT_ARCHIVE_STRUCTURE"):
            v.decode_archive(invalid.getvalue(),101,"c"*40)

    def test_replay_and_same_source_cannot_inherit(self):
        meta=v.validate_verified_parent(self.manifest,self.child,
                                        self.synthetic_positive(),self.weight,0)
        with self.assertRaisesRegex(ValueError,"NO_NEW_INDEPENDENT_SOURCE_SNAPSHOT"):
            v.valid_for_new_history(meta,self.manifest)
        future=copy.deepcopy(self.manifest)
        future["source_commit"]="e"*40
        future["dataset_sha256"]="f"*64
        future["split_dates"]["holdout"]=["2026-09-01","2026-09-07"]
        future["receipt_sha256"]=e.seal({k:w for k,w in future.items() if k!="receipt_sha256"})
        self.assertTrue(v.valid_for_new_history(meta,future))
        stale=copy.deepcopy(future)
        stale["split_dates"]["holdout"][0]=meta["last_holdout_date"]
        stale["receipt_sha256"]=e.seal({k:w for k,w in stale.items() if k!="receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"FUTURE_ONLY_EVALUATION_REQUIRED"):
            v.valid_for_new_history(meta,stale)


if __name__=="__main__":unittest.main()
