"""JANUS v5.0 bounded agency and TOPA structural witness, offline contract tests."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import janus_v50_ai_agency as a


def inspection(path,raw):
    obj=json.loads(raw)
    sem=hashlib.sha256(a.dump(obj)+b"\n").hexdigest()
    return {
        "schema":a.JSON_RAIL_SCHEMA,"path":str(path),
        "format":{"kind":"json","compression":None},
        "records":1,"malformed_records":0,
        "type_counts":{"object":1},
        "raw_sha256":hashlib.sha256(raw).hexdigest(),
        "semantic_record_stream_sha256":sem,
    }


class AgencyTests(unittest.TestCase):
    def setUp(self):
        self.source=Path(a.SOURCE)
        self.raw=self.source.read_bytes()
        self.desires=a.read("beetle/JANUS_DESIRES.json")
        self.directives=a.read("beetle/DEMIURGE_BEETLE_DIRECTIVES.json")
        self.native=a.read("janus_model/state/JANUS_LATEST_DECISION.json")

    def test_intent_is_user_requested_and_in_canonical_beetle_allowlist(self):
        a.validate_desire(self.desires,self.directives)
        self.assertEqual(a.native_status(self.native)["selected_action"],"NO_ACTION")
        self.assertFalse(a.native_status(self.native)["native_proposed_this_user_task"])
        self.assertEqual(a.REPOS,tuple(self.desires["ad_hoc"][0]["target_repositories"]))

    def test_readout_remains_hold_with_real_negative_results(self):
        source=a.validate_readout(json.loads(self.raw))
        self.assertEqual(source["status"],"HOLD_REPLAY_DID_NOT_CLEAR_PREDECLARED_GATES")
        self.assertEqual(source["results"]["lapis_paraphrased_source"]["replay_exact"],0)
        self.assertFalse(source["deployment"]["production_admission"])

    def test_topa_accepts_exact_sha_and_refuses_garbled_json(self):
        obj=inspection(self.source,self.raw)
        a.topa_inspection(obj,self.raw,str(self.source))
        altered=copy.deepcopy(obj)
        altered["raw_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"TOPA_SOURCE"):
            a.topa_inspection(altered,self.raw,str(self.source))
        altered=copy.deepcopy(obj)
        altered["malformed_records"]=1
        with self.assertRaisesRegex(ValueError,"TOPA_SOURCE"):
            a.topa_inspection(altered,self.raw,str(self.source))

    def test_packet_integrity_native_abstention_and_zero_exec(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"inspection.json"
            file.write_text(json.dumps(inspection(self.source,self.raw)))
            pkt=a.build(".",file,"a"*40)
            a.check(pkt)
            self.assertEqual(pkt["native_model"]["selected_action"],"NO_ACTION")
            self.assertEqual(pkt["beetle_task_id"],"janus_json_registry_provenance_audit")
            self.assertFalse(pkt["external_scientific_validation"])
            self.assertFalse(pkt["remote_execution_observed"])
            self.assertFalse(pkt["production_write_authority"])
            self.assertFalse(pkt["sentinel_dispatch"])
            self.assertEqual(pkt["source_fact_json"]["research_verdict"],
                             "HOLD_REPLAY_DID_NOT_CLEAR_PREDECLARED_GATES")
            self.assertFalse(pkt["source_fact_json"]["epistemic_boundary"][
                "used_as_direct_neural_supervision"])
            tampered=copy.deepcopy(pkt)
            tampered["source_fact_json"]["research_verdict"]="PASS"
            with self.assertRaises(ValueError):
                a.check(tampered)

    def test_model_cannot_enable_unapproved_tasks_or_repos(self):
        o=copy.deepcopy(self.desires)
        o["ad_hoc"][0]["target_repositories"].append("Hawkar-usls/TOPA")
        with self.assertRaisesRegex(ValueError,"SCOPE"):
            a.validate_desire(o,self.directives)
        o=copy.deepcopy(self.desires)
        o["focus"][0]["priority_delta"]=500
        with self.assertRaisesRegex(ValueError,"DIRECTION"):
            a.validate_desire(o,self.directives)
        o=copy.deepcopy(self.desires)
        o["producer"]["current_writer"]="FAKE_NATIVE_MODEL"
        with self.assertRaisesRegex(ValueError,"NO_EXPLICIT"):
            a.validate_desire(o,self.directives)
        o=copy.deepcopy(self.native)
        o["authority"]["direct_repository_mutation"]=True
        with self.assertRaisesRegex(ValueError,"AUTHORITY"):
            a.native_status(o)

    def test_wrong_commit_never_produces_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"inspection.json"
            file.write_text(json.dumps(inspection(self.source,self.raw)))
            with self.assertRaisesRegex(ValueError,"MISSING_SOURCE_COMMIT"):
                a.build(".",file,"untrusted")
            altered=inspection(self.source,self.raw)
            altered["path"]="../wrong.json"
            file.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,"TOPA_SOURCE"):
                a.build(".",file,"a"*40)


if __name__=="__main__":
    unittest.main()
