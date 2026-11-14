"""ESSENCE v2.5 tests: three real executable module generations, Git-only state.

The test corpus is a controlled fixture; production checks on GitHub main
must use records committed AFTER the actual health parent's birth commit.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from tools import rex_module_fitness_v24 as v24
from tools import rex_module_fitness_v25 as v25


def command(cwd,*args):
    r=subprocess.run([*map(str,args)],cwd=cwd,text=True,
                     capture_output=True,timeout=20)
    if r.returncode:
        raise AssertionError(f"COMMAND_FAILED {args}: {r.stderr[:2000]}")
    return r.stdout.strip()


class ProspectiveLineage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.family=self.root/"rex/lifecycle_runs/rex_probe"
        self.family.mkdir(parents=True)
        self.summary="rex_probe_ledger_summary"
        self.health="rex_probe_ledger_health"
        self.trend="rex_probe_ledger_trend"
        self.add_rows(0,4)
        self.summary_spec=self.spec(self.summary,"ledger_summary",4)
        self.summary_dir=self.build(self.summary_spec)
        self.add_rows(4,44)
        self.health_spec=self.spec(self.health,"ledger_health",44)
        self.health_dir=self.build(self.health_spec)
        report=v24.evaluate(self.root,self.health_dir,self.health_spec,
                            self.summary_dir,self.summary_spec)
        self.assertEqual(report["status"],"RESEARCH_FUNCTIONAL_GAIN")
        (self.health_dir/"fitness.json").write_text(json.dumps(report))
        source_hash=report["candidate_source_sha256"]
        admission=self.root/"rex/admissions"/f"{self.health}.json"
        admission.parent.mkdir(parents=True,exist_ok=True)
        admission.write_text(json.dumps(
            {"state":"ADMITTED_EXACT_SHA","source_sha256":source_hash}))
        lifecycle=self.root/"rex/lifecycle"/f"{self.health}.json"
        lifecycle.parent.mkdir(parents=True,exist_ok=True)
        lifecycle.write_text(json.dumps(
            {"state":"LIFECYCLE_ADMITTED_EXACT_SHA","source_sha256":source_hash}))
        command(self.root,"git","init","-q")
        command(self.root,"git","config","user.name","Rex CI Witness")
        command(self.root,"git","config","user.email","rex-ci@example.invalid")
        self.commit("health-parent-born")

    def add_rows(self,first,limit):
        for i in range(first,limit):
            record={"schema":"janus.rex.lifecycle_run_receipt.v1",
                    "module_id":"rex_probe","state":"EXECUTED_EXACT_SHA",
                    "result_status":("ALIVE" if i%3==0 else
                                     "RECOVERED" if i%3==1 else "ERROR"),
                    "source_sha256":f"{i+1:064x}","authority_delta":0}
            (self.family/f"{i:05d}.json").write_text(
                json.dumps(record,sort_keys=True)+"\n")

    def commit(self,message):
        command(self.root,"git","add","-A")
        command(self.root,"git","commit","-qm",message)

    def spec(self,mid,template,count,extra=None):
        target=self.root/"rex/specs/generated"/f"{mid}.json"
        target.parent.mkdir(parents=True,exist_ok=True)
        payload={"observed_path":"rex/lifecycle_runs/rex_probe",
                 "observed_record_count":count}
        payload.update(extra or {})
        target.write_text(json.dumps({
            "schema":"janus.rex.module_spec.v1","module_id":mid,
            "purpose":"Bounded multi-generation ledger microcore test",
            "version":"1.0.0","template":template,"config":{},
            "nexus":{"request_autorun":True,"input":payload}
        },sort_keys=True))
        return target

    def build(self,spec):
        mid=json.loads(spec.read_text())["module_id"]
        folder=self.root/"rex/candidates"/mid
        command(REPO,sys.executable,REPO/"tools/demiurge_rex.py","build",
                "--policy",REPO/"rex/policy.json",
                "--spec",spec,"--out-root",self.root/"rex/candidates")
        audit=json.loads(command(REPO,sys.executable,
                  REPO/"tools/demiurge_rex.py","audit",
                  "--candidate-dir",folder))
        self.assertEqual(audit["status"],"PASS")
        return folder

    def discover(self):
        return json.loads(command(REPO,sys.executable,
             REPO/"tools/demiurge_rex_need_discovery.py",
             "--policy",REPO/"rex/need_discovery_policy.json",
             "--repo-root",self.root))

    def build_trend(self):
        result=self.discover()
        self.assertEqual(result["proposal_count"],1)
        proposals=list((self.root/"rex/need_proposals/generated").glob("*.json"))
        self.assertEqual(len(proposals),1)
        proposal=json.loads(proposals[0].read_text())
        self.assertEqual(proposal["need_kind"],"LEDGER_TREND_GAP")
        self.assertEqual(proposal["suggested_desire"]["template"],"ledger_trend")
        ctx=proposal["suggested_desire"]["nexus"]["input"]
        self.assertEqual(ctx["verified_parent_module"],self.health)
        self.assertEqual(len(ctx["verified_parent_source_sha256"]),64)
        spec=self.spec(self.trend,"ledger_trend",ctx["observed_record_count"],ctx)
        candidate=self.build(spec)
        return candidate,spec

    def test_no_unearned_next_generation(self):
        result=self.discover()
        self.assertEqual(result["proposal_count"],0)
        self.assertTrue(any(row.get("reason")==
            "HOLD_NEXT_GENERATION_REQUIRES_NEW_RECORDS"
            for row in result["skipped"]))

    def test_full_three_generation_inheritance_postbirth_git_cohort(self):
        self.add_rows(44,68)
        self.commit("genuinely-postbirth-ledger-data")
        candidate,spec=self.build_trend()
        proof=v25.evaluate(self.root,candidate,spec,
                           self.health_dir,self.health_spec)
        self.assertEqual(proof["status"],"GIT_POSTBIRTH_FUNCTIONAL_GAIN")
        self.assertEqual(proof["generation_depth"],2)
        self.assertEqual(proof["used_postbirth_rows"],24)
        self.assertTrue(proof["functional_gain_verified"])
        self.assertEqual(len(proof["reviews"]),2)
        self.assertTrue(all(x["inherited_health_abi_preserved"]
                            and x["new_status_trend_correct"]
                            for x in proof["reviews"]))
        self.assertFalse(proof["independently_proven_neural_weight_gain"])
        self.assertFalse(proof["production_model_promotion"])
        self.assertEqual(proof["receipt_sha256"],
                         v25.digest({k:v for k,v in proof.items()
                                     if k!="receipt_sha256"}))

    def test_parent_receipt_tampering_prevents_birth(self):
        self.add_rows(44,68)
        self.commit("new-data")
        path=self.health_dir/"fitness.json"
        obj=json.loads(path.read_text())
        obj["status"]="RESEARCH_FUNCTIONAL_GAIN_BUT_FAKE"
        path.write_text(json.dumps(obj))
        result=self.discover()
        self.assertEqual(result["proposal_count"],0)
        self.assertTrue(any(x.get("reason")=="HOLD_UNVERIFIED_HEALTH_PARENT"
            for x in result["skipped"]))

    def test_prior_ledger_mutation_refused_by_git_provenance(self):
        self.add_rows(44,68)
        self.commit("new-data")
        candidate,spec=self.build_trend()
        old=self.family/"00000.json"
        record=json.loads(old.read_text())
        record["result_status"]="FORGED"
        old.write_text(json.dumps(record))
        self.commit("mutate-old-record")
        with self.assertRaisesRegex(ValueError,"NON_APPEND_ONLY_POST_BIRTH_HISTORY"):
            v25.evaluate(self.root,candidate,spec,self.health_dir,self.health_spec)

    def test_deleted_future_cohort_fails(self):
        self.add_rows(44,55)
        self.commit("only-eleven-future-records")
        result=self.discover()
        self.assertEqual(result["proposal_count"],0)


if __name__=="__main__":
    unittest.main()
