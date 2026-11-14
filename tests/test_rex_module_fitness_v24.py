"""Rex v2.4: actual module generation, approval boundary and functional value.

Uses real generated candidate source and separate isolated subprocess execution.
The fixture is synthetic; the production evaluator replays tracked Rex ledgers.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import rex_module_fitness_v24 as fitness


def call(*args):
    r = subprocess.run([sys.executable, *map(str,args)], cwd=REPO,
                       text=True, capture_output=True)
    if r.returncode:
        raise AssertionError(f"Subprocess failed: {args}\n{r.stdout}\n{r.stderr}")
    return json.loads(r.stdout)


class FunctionalBirth(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.family = self.root / "rex/lifecycle_runs/rex_probe"
        self.family.mkdir(parents=True)
        self.generate_records(4)
        self.summary_id = "rex_probe_ledger_summary"
        self.health_id = "rex_probe_ledger_health"
        proposal = call("tools/demiurge_rex_need_discovery.py",
                        "--policy", REPO/"rex/need_discovery_policy.json",
                        "--repo-root", self.root)
        self.assertEqual(proposal["proposal_count"],1)
        self.summary_spec = self.make_spec(self.summary_id, "ledger_summary", 4)
        self.summary_dir = self.birth(self.summary_spec)

    def generate_records(self, n):
        for i in range(n):
            obj={"schema":"janus.rex.lifecycle_run_receipt.v1",
                 "module_id":"rex_probe",
                 "state":"EXECUTED_EXACT_SHA",
                 "result_status":"ALIVE" if i%3 else "RECOVERED",
                 "source_sha256":f"{i+1:064x}",
                 "authority_delta":0}
            (self.family/f"{i:05d}.json").write_text(json.dumps(obj)+"\n")

    def make_spec(self, mid, template, count):
        p = self.root / "rex/specs/generated" / f"{mid}.json"
        p.parent.mkdir(parents=True,exist_ok=True)
        spec={"schema":"janus.rex.module_spec.v1",
              "module_id":mid,"purpose":"Bounded real ledger health verification",
              "version":"1.0.0","template":template,"config":{},
              "nexus":{"request_autorun":True,
                       "input":{"observed_path":"rex/lifecycle_runs/rex_probe",
                                "observed_record_count":count}}}
        p.write_text(json.dumps(spec,sort_keys=True))
        return p

    def birth(self, spec):
        mod_id=json.loads(spec.read_text())["module_id"]
        folder=self.root/"rex/candidates"/mod_id
        call("tools/demiurge_rex.py","build",
             "--policy",REPO/"rex/policy.json",
             "--spec",spec,"--out-root",self.root/"rex/candidates")
        audit=call("tools/demiurge_rex.py","audit","--candidate-dir",folder)
        self.assertEqual(audit["status"],"PASS")
        return folder

    def prepare_health(self, count=44):
        self.generate_records(count)
        discovery=call("tools/demiurge_rex_need_discovery.py",
                       "--policy",REPO/"rex/need_discovery_policy.json",
                       "--repo-root",self.root)
        self.assertEqual(discovery["proposal_count"],1)
        paths=list((self.root/"rex/need_proposals/generated").glob("*.json"))
        health=[json.loads(p.read_text()) for p in paths
                if json.loads(p.read_text()).get("need_kind")=="LEDGER_HEALTH_GAP"]
        self.assertEqual(len(health),1)
        self.assertEqual(health[0]["suggested_desire"]["template"],"ledger_health")
        result=call("tools/nexus_rex_need_gate.py",
                    "--policy",REPO/"rex/need_gate_policy.json",
                    "--repo-root",self.root)
        self.assertEqual(result["approved_this_run"],1)
        self.assertTrue(any(row.get("reason")=="ALREADY_IMPLEMENTED_NEED_NO_NEW_ADMISSION"
                            for row in result["skipped"]))
        self.health_spec=self.make_spec(self.health_id,"ledger_health",count)
        self.health_dir=self.birth(self.health_spec)

    def test_end_to_end_need_discovery_sandbox_gain(self):
        self.prepare_health()
        report=fitness.evaluate(self.root, self.health_dir, self.health_spec,
                                self.summary_dir,self.summary_spec)
        self.assertEqual(report["status"],"RESEARCH_FUNCTIONAL_GAIN")
        self.assertTrue(report["new_functional_capability_proven"])
        self.assertGreaterEqual(report["retrospective_extra_records"],12)
        self.assertEqual(len(report["checks"]),2)
        self.assertTrue(all(row["preserved_legacy_contract"] for row in report["checks"]))
        self.assertTrue(all(row["new_status_distribution_correct"] for row in report["checks"]))
        self.assertFalse(report["quality_on_external_future_tasks_proven"])
        self.assertFalse(report["production_authority"])

    def test_tampered_generated_source_rejected(self):
        self.prepare_health()
        source=self.health_dir/"module.py"
        source.write_text(source.read_text()+"\n# altered\n")
        with self.assertRaisesRegex(ValueError,"REX_GENERATED_MODULE_INTEGRITY_FAILED"):
            fitness.evaluate(self.root,self.health_dir,self.health_spec,
                             self.summary_dir,self.summary_spec)

    def test_insufficient_extra_rows_rejected(self):
        self.prepare_health(count=44)
        for path in sorted(self.family.glob("*.json"))[14:]:
            path.unlink()
        with self.assertRaisesRegex(ValueError,"INSUFFICIENT_ADDITIONAL_REAL_RECORDS"):
            fitness.evaluate(self.root,self.health_dir,self.health_spec,
                             self.summary_dir,self.summary_spec)

    def test_discovery_stops_after_health_module_already_exists(self):
        self.prepare_health()
        again=call("tools/demiurge_rex_need_discovery.py",
                   "--policy",REPO/"rex/need_discovery_policy.json",
                   "--repo-root",self.root)
        self.assertEqual(again["proposal_count"],0)
        self.assertTrue(any(row.get("reason")=="health_module_already_exists"
                            for row in again["skipped"]))


if __name__ == "__main__":
    unittest.main()
