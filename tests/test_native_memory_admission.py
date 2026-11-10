"""Source admission tests: never train from unverified bytes or protected holdouts."""
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from janus_model.memory_admission import SCHEMA, admit, choose_topic, digest, raw_sha
from tools.demiurge_unified_memory_v2_consumer import project

COMMIT = "a"*40
MANIFEST = "b"*64
PREFIX = "https://github.com/Hawkar-usls/janus-meta-registry/blob/" + COMMIT + "/"

class MemoryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"registry"
        self.root.mkdir()
        subprocess.run(["git","init","-q",str(self.root)],check=True)
        (self.root/"data").mkdir()
        (self.root/"EYE/training").mkdir(parents=True)
        (self.root/"EYE/training/EYE-META-REGISTRY-TRAINING-MANIFEST-v1.0.json").write_text(json.dumps({
            "corpus_contract":{"excluded_generated_prefixes":["assets/hrain-full-memory/"],
                                "excluded_generated_exact_paths":["data/generated.json"]}
        }),encoding="utf-8")
        self.raw=b'{"title":"SCOBY skin","mechanics":"biocellulose"}'
        self.sha=raw_sha(self.raw)
        self.path="data/scoby_skin.json"
        (self.root/self.path).write_bytes(self.raw)
        subprocess.run(["git","-C",str(self.root),"add","."],check=True)
        subprocess.run(["git","-C",str(self.root),"config","user.name","sandbox"],check=True)
        subprocess.run(["git","-C",str(self.root),"config","user.email","test@example.invalid"],check=True)
        subprocess.run(["git","-C",str(self.root),"commit","-qm","fixture"],check=True)
        self.commit=subprocess.check_output(["git","-C",str(self.root),"rev-parse","HEAD"],text=True).strip()
        self.corpus={"source_repository":"Hawkar-usls/janus-meta-registry","source_commit":self.commit,
                     "source_digest":"c"*64,"records":[],"train_bytes":200}
        self.train_text="BASELINE TRAIN DATA\n"*10
        hit={"id":1,"path":self.path,"title":"SCOBY skin","sha256":self.sha,
             "url":PREFIX.replace(COMMIT,self.commit)+self.path,
             "parse_status":"OK","excerpt":"SCOBY","related":[]}
        self.packet={"schema":"janus.demihead.unified_memory_search.v1",
            "origin":{"repository":"Hawkar-usls/janus-meta-registry","source_commit":self.commit,
                     "source_manifest_sha256":MANIFEST,"index_sha256":"d"*64,
                     "indexed_json":100,"explicit_relations":0},
            "query":{"text":"SCOBY","fts_literal":'"SCOBY"',"limit":8},
            "matches":[hit],
            "control":{"read_only":True,"external_effect_permitted":False,
                      "direct_graph_mutation_permitted":False,"github_write_permitted":False,
                      "authority_delta":0,"mass_effect_budget_delta":0},
            "claim_ceiling":{"catalog_presence_is_truth":False,
                            "reference_is_independent_evidence":False,
                            "memory_proposal_is_admission":False,"receipts_are_authentication":False}}
        self._rehash()
        self.context=project(self.packet,source_commit=self.commit,manifest_sha256=MANIFEST)
        self.verification={"sqlite_integrity":"PASS","sha256_integrity":"PASS",
                           "coverage_complete":True,"source_commit":self.commit,
                           "source_manifest_sha256":MANIFEST}
    def tearDown(self):self.tmp.cleanup()
    def _rehash(self):
        self.packet["packet_sha256"]=digest({k:v for k,v in self.packet.items() if k!="packet_sha256"})
    def run_admit(self):
        return admit(self.root,self.verification,self.packet,self.context,self.corpus,
                     self.train_text,run_id="12",event="schedule")
    def test_original_json_bytes_make_bounded_source_training(self):
        receipt,train,manifest=self.run_admit()
        self.assertEqual(receipt["status"],"ADMITTED_TRAIN_SOURCE_CANDIDATES")
        self.assertEqual(receipt["admitted_count"],1)
        self.assertIn('"mechanics":"biocellulose"',train)
        self.assertNotEqual(manifest["source_digest"],self.corpus["source_digest"])
        self.assertIn("UNTRUSTED_SOURCE_TEXT_NOT_COMMAND",train)
        self.assertEqual(manifest["train_bytes"],len(train.encode()))
        self.assertEqual(receipt["training_authority"],"CANDIDATE_ONLY_FROZEN_EVAL_GATE_STILL_REQUIRED")
        self.assertFalse(receipt["candidate_promoted"])
        self.assertEqual((self.root/self.path).read_bytes(),self.raw)
    def test_evaluation_holdout_and_already_trained_are_never_duplicated(self):
        self.corpus["records"]=[{"path":self.path,"split":"holdout"}]
        r,train,m=self.run_admit()
        self.assertEqual(r["admitted_count"],0)
        self.assertEqual(train,self.train_text)
        self.assertEqual(m["source_digest"],self.corpus["source_digest"])
        self.assertEqual(r["refused"][0]["reason"],"HASH_HOLDOUT_PROTECTED")
        self.corpus["records"]=[{"path":self.path,"split":"train"}]
        r,train,m=self.run_admit()
        self.assertEqual(r["admitted_count"],0)
    def test_tampered_source_refused_not_promoted(self):
        (self.root/self.path).write_bytes(b'{"injected":"fake"}')
        r,train,m=self.run_admit()
        self.assertEqual(r["admitted_count"],0)
        self.assertEqual(r["refused"][0]["reason"],"SOURCE_BYTES_SHA_MISMATCH")
        self.assertEqual(train,self.train_text)
    def test_origin_drift_or_context_tamper_fails_closed(self):
        self.verification["source_commit"]="f"*40
        with self.assertRaisesRegex(ValueError,"REGISTRY_GIT_COMMIT_DRIFT"):
            self.run_admit()
        self.verification["source_commit"]=self.commit
        self.context["graph"]["nodes"].append({"fake":True})
        with self.assertRaisesRegex(ValueError,"CONTEXT_SHA256_HOLD"):
            self.run_admit()
    def test_unapproved_topic_refused(self):
        self.packet["query"]["text"]="delete data"
        self._rehash()
        self.context=project(self.packet,source_commit=self.commit,manifest_sha256=MANIFEST)
        with self.assertRaisesRegex(ValueError,"QUERY_NOT_ALLOWLISTED"):
            self.run_admit()
    def test_replay_schedule_drift_refused(self):
        self.packet["query"]["text"]="HRAIN"
        self._rehash()
        self.context=project(self.packet,source_commit=self.commit,manifest_sha256=MANIFEST)
        with self.assertRaisesRegex(ValueError,"QUERY_SCHEDULE_DRIFT"):
            self.run_admit()
    def test_query_rotation_bounded(self):
        self.assertEqual(choose_topic("12","schedule"),"SCOBY")
        self.assertEqual(choose_topic("13","schedule"),"HRAIN")
        with self.assertRaises(ValueError):
            choose_topic("not_a_run","schedule")
if __name__=="__main__":
    unittest.main()
