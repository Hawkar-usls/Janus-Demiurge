"""ESSENCE v2.9 CORE -> Beetle: no synthetic claim can become evidence."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import essence_beetle_core_bridge as core
from tools import demiurge_beetle_director as director


class CoreBeetleResearchBridge(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.evidence=[]
        for role,repo,ref,path,schema in core.SOURCES:
            o=self.source(role,schema)
            raw=core.canon(o)
            self.evidence.append(core.validate_source(
                role,repo,ref,path,schema,"a"*40,core.git_blob(raw),raw))
        self.receipt=core.build(self.evidence)
        self.path=self.folder/"core.json"
        self.path.write_text(json.dumps(self.receipt,sort_keys=True))
        self.allowed={target for q in core.QUESTIONS for target in q["target_repositories"]}

    def source(self,role,schema):
        if role=="genesis":
            return {"schema":schema,"repository":"Hawkar-usls/Janus_Genesis",
                    "research_generation":1,"research_status":"HOLD_NO_NEW_INDEPENDENT_GAIN",
                    "production_authority":False}
        if role=="demiurge":
            return {"schema":schema,
                    "candidate_module":"rex_lifecycle_heartbeat_ledger_health",
                    "new_functional_capability_proven":True,
                    "production_authority":False}
        if role in ("swarm","demi_head"):
            repo="Hawkar-usls/janus-distributed-ai-swarm" if role=="swarm" else "Hawkar-usls/Demi_Head"
            return {"schema":schema,"peers":[{"repository":repo}],"production_authority":False}
        if role=="neural":
            body={"schema":schema,"generation":0,"parent":None,
                  "pending":{"sealed_before":"2026-11-14T17:08:09Z"},
                  "history":[],"research_only":True,"production_authority":False}
            body["state_sha256"]=core.sha(body)
            return body
        return {"directions":[{"id":"formal_proof_verification"}]}

    def test_six_source_provenance_and_bounded_discovery_topics(self):
        p=self.receipt
        self.assertEqual(p["status"],"CORE_LINKED_SEARCH_STEERING_ONLY")
        self.assertEqual(p["source_count"],6)
        self.assertEqual(len(p["search_questions"]),2)
        self.assertEqual(p["authority_delta"],0)
        self.assertFalse(p["automatic_production_promotion"])
        self.assertEqual(p["receipt_sha256"],
                         core.sha({k:v for k,v in p.items() if k!="receipt_sha256"}))
        self.assertEqual(set(r["role"] for r in p["sources"]),set(x[0] for x in core.SOURCES))
        self.assertTrue(all(r["scientific_evidence"] is False for r in p["sources"]))

    def test_validate_each_source_against_exact_git_blob(self):
        role,repo,ref,path,schema=core.SOURCES[0]
        raw=core.canon(self.source(role,schema))
        with self.assertRaisesRegex(ValueError,"CORE_GIT_BLOB_MISMATCH"):
            core.validate_source(role,repo,ref,path,schema,"a"*40,"f"*40,raw)
        with self.assertRaisesRegex(ValueError,"CORE_SCHEMA_MISMATCH"):
            core.validate_source(role,repo,ref,path,schema,"a"*40,
                core.git_blob(b'{"schema":"fake"}'),b'{"schema":"fake"}')

    def test_no_raw_model_weights_enter_beetle(self):
        fields=json.dumps(self.receipt)
        self.assertNotIn("model_state",fields)
        self.assertNotIn("challenger_sha256",fields)
        self.assertNotIn("tensor",fields)
        self.assertNotIn("created_at",fields)

    def test_missing_core_blocks_all_search_proposals(self):
        p=core.build(self.evidence[:-1])
        self.assertEqual(p["status"],"HOLD_INCOMPLETE_CORE_SOURCES")
        self.assertFalse(p["search_questions"])
        q,receipt=director.verified_core_bridge(None,self.allowed)
        self.assertEqual(q,[])
        self.assertIsNone(receipt)

    def test_beetle_director_accepts_sealed_immutable_questions(self):
        q,seal=director.verified_core_bridge(str(self.path),self.allowed)
        self.assertEqual(q,list(core.QUESTIONS))
        self.assertEqual(seal,self.receipt["receipt_sha256"])
        routed=director.clean_adhoc(q,self.allowed,"ESSENCE_CORE_BRIDGE")
        self.assertEqual(len(routed),2)
        self.assertTrue(all(x["source"]=="ESSENCE_CORE_BRIDGE" for x in routed))
        self.assertTrue(all(set(x["target_repositories"]).issubset(self.allowed)
                            for x in routed))

    def test_core_claim_escalation_and_digest_tampering_rejected(self):
        for field,value in (
            ("science_claim","MODEL_IMPROVEMENT_PROVEN"),
            ("authority_delta",1),
            ("automatic_production_promotion",True),
            ("producer_can_modify_model_weights",True)):
            p=copy.deepcopy(self.receipt)
            p[field]=value
            p["receipt_sha256"]=core.sha({k:v for k,v in p.items()
                                          if k!="receipt_sha256"})
            self.path.write_text(json.dumps(p))
            q,hash_=director.verified_core_bridge(str(self.path),self.allowed)
            self.assertEqual(q,[],field)
            self.assertIsNone(hash_)
        p=copy.deepcopy(self.receipt)
        p["search_questions"][0]["keywords"].append("arbitrary attacker term")
        self.path.write_text(json.dumps(p))
        self.assertEqual(director.verified_core_bridge(str(self.path),self.allowed)[0],[])

    def test_neural_future_remains_unverified(self):
        neural=next(x for x in self.evidence if x["role"]=="neural")
        self.assertEqual(neural["summary"]["accepted_generations"],0)
        self.assertTrue(neural["summary"]["pending_future_exam"])
        self.assertEqual(neural["summary"]["status"],"PROSPECTIVE_PROOF_PENDING")

    def test_demiurge_director_real_cli_preserves_search_only_firewall(self):
        self.path.write_text(json.dumps(self.receipt))
        out=self.folder/"priorities.json"
        subprocess.run(
            [sys.executable,str(ROOT/"tools/demiurge_beetle_director.py"),
             "--directives",str(ROOT/"beetle/DEMIURGE_BEETLE_DIRECTIVES.json"),
             "--status",str(ROOT/"scout_swarm/state/SCOUT_SWARM_STATUS-v1.json"),
             "--desires",str(ROOT/"beetle/JANUS_DESIRES.json"),
             "--core-bridge",str(self.path),"--out",str(out)],
            cwd=ROOT,check=True,capture_output=True,text=True,timeout=15)
        doc=json.loads(out.read_text())
        self.assertTrue(doc["essence_core_bridge_ingested"])
        self.assertEqual(doc["essence_core_bridge_receipt_sha256"],
                         self.receipt["receipt_sha256"])
        self.assertTrue(doc["essence_core_bridge_ad_hoc_directions"])
        self.assertEqual(doc["claim_ceiling"],
                         "SEARCH_STEERING_ONLY__ZERO_EVIDENCE_AUTHORITY")
        self.assertIs(doc["core_bridge_scientific_authority"],False)
        self.assertTrue(all(q["source"]=="ESSENCE_CORE_BRIDGE"
            for q in doc["ad_hoc_directions"]))


if __name__=="__main__":
    unittest.main()
