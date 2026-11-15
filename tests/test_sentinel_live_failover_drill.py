"""SENTINEL real GitHub failover drill — synthetic negative contracts only.

These tests NEVER count as proof of real GitHub workflow dispatch.
The separate trusted-main Actions drill must observe real failed A/B, CAS
claim, C's recovery of A and peer A's recovery of B.
"""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import sentinel_live_failover_drill as d

NOW=datetime(2026,11,15,13,0,tzinfo=timezone.utc)


class SentinelLiveDrillContracts(unittest.TestCase):
    def test_three_same_repo_workflow_targets_only(self):
        self.assertEqual(set(d.TARGETS),{"A","B","C"})
        self.assertEqual(d.PAGESIZE,30)
        self.assertTrue(d.BASE.endswith("/Hawkar-usls/Janus-Demiurge"))
        calls=[]
        def fake(path,token,post=None):
            calls.append((path,post))
            return {"status":204,"accepted":True}
        out=d.dispatch("A","not-a-real-token-1234567",
                       "sentinel-drill-v1-43699912345",fault=True,call=fake)
        self.assertEqual(out["status"],204)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],
            "/actions/workflows/sentinel-node-a.yml/dispatches")
        self.assertEqual(calls[0][1]["inputs"],{
            "fault_inject":"true","recovery_only":"false",
            "drill_nonce":"sentinel-drill-v1-43699912345"})
        with self.assertRaisesRegex(RuntimeError,
                                    "UNAUTHORIZED_DRILL_NODE_DISPATCH"):
            d.dispatch("WORKER","test","sentinel-drill-v1-43699912345",
                       fault=True,call=fake)
        with self.assertRaisesRegex(RuntimeError,
                                    "UNAUTHORIZED_DRILL_NODE_DISPATCH"):
            d.dispatch("A","test","bad",fault=True,call=fake)
        with self.assertRaisesRegex(RuntimeError,
                                    "UNAUTHORIZED_DRILL_NODE_DISPATCH"):
            d.dispatch("B","test","sentinel-drill-v1-43699912345",
                       fault=True,recovery=True,call=fake)

    def test_isolated_failure_is_an_actual_failed_workflow_not_a_forged_state(self):
        nonce="sentinel-drill-v1-43699912345"
        bad={
            "id":123,"event":"workflow_dispatch","head_branch":"main",
            "status":"completed","conclusion":"failure",
            "display_title":"JANUS SENTINEL B · "+nonce,
            "created_at":NOW.isoformat(),"html_url":"https://github.com/ok"
        }
        self.assertEqual(d.find_tagged([bad],"B",nonce,conclusion="failure"),bad)
        self.assertIsNone(d.find_tagged([bad],"B",nonce,conclusion="success"))
        with self.assertRaisesRegex(RuntimeError,
                                    "DUPLICATE_DRILL_NONCE_IN_GITHUB"):
            d.find_tagged([bad,bad],"B",nonce,conclusion="failure")

    def test_claim_must_be_exact_c_to_a_with_original_failure(self):
        failed={
            "id":501,"created_at":(NOW-timedelta(minutes=15)).isoformat()
        }
        base={
            "schema":"janus.sentinel.recovery_state/1.0",
            "epoch":1,"authority":"BOUNDED_GITHUB_ACTIONS_ONLY",
            "production_model_updates":False,
            "last_dispatch":{
                "A":{
                    "target":"A","issuer":"C","run_id":"100001",
                    "issued_at":NOW.isoformat(),
                    "observed_target_run_id":501,"claim_epoch":1,
                    "outcome":"ATTEMPTED_NOT_CONFIRMED",
                }
            }
        }
        self.assertEqual(
            d.validate_claim(base,"A",failed,"C")["issuer"],"C")
        self.assertIsNone(d.validate_claim(
            base,"A",{"id":502,"created_at":NOW.isoformat()},"C"))
        with self.assertRaisesRegex(RuntimeError,"BAD_RECOVERY_CLAIM"):
            d.validate_claim(base,"A",failed,"B")
        base["last_dispatch"]["A"]["outcome"]="FABRICATED_SUCCESS"
        with self.assertRaisesRegex(RuntimeError,"BAD_RECOVERY_CLAIM"):
            d.validate_claim(base,"A",failed,"C")

    def test_recovered_success_only_after_genuine_claim(self):
        fault={
            "id":701,
            "created_at":(NOW-timedelta(minutes=15)).isoformat()
        }
        claim={
            "issued_at":(NOW-timedelta(minutes=2)).isoformat(),
            "issuer":"C","run_id":"123456","claim_epoch":7
        }
        expected="JANUS SENTINEL A · sentinel-recovery-C-123456-7"
        earlier={
            "id":702,"event":"workflow_dispatch","status":"completed",
            "display_title":expected,
            "conclusion":"success","head_branch":"main",
            "created_at":(NOW-timedelta(minutes=4)).isoformat()
        }
        valid=dict(earlier,id=703,
                   created_at=(NOW+timedelta(seconds=1)).isoformat())
        def fetch(path,token,post=None):
            return {"workflow_runs":[earlier,valid]}
        self.assertEqual(
            d.prove_healthy_after_claim("A",fault,claim,"token",call=fetch),
            valid)
        def only_old(path,token,post=None):
            return {"workflow_runs":[earlier]}
        self.assertIsNone(
            d.prove_healthy_after_claim("A",fault,claim,"token",
                                        call=only_old))

    def test_existing_cooldown_cannot_be_forged(self):
        prior={
            "last_dispatch":{
              "B":{"issued_at":NOW.isoformat()}
            }
        }
        with patch.object(d,"utcnow",return_value=NOW+timedelta(minutes=12)):
            with self.assertRaisesRegex(RuntimeError,
                                        "DRILL_CANNOT_BYPASS_EXISTING_COOLDOWN_B"):
                d.check_no_unknown_prior_claim(prior,["B"])
        with patch.object(d,"utcnow",return_value=NOW+timedelta(minutes=91)):
            d.check_no_unknown_prior_claim(prior,["B"])

    def test_workflow_fault_inputs_only_under_explicit_nonce(self):
        repo=Path(__file__).resolve().parents[1]
        for role in ("a","b","c"):
            source=(repo/".github/workflows"/
                    f"sentinel-node-{role}.yml").read_text()
            self.assertIn("sentinel-drill-v1-",source)
            self.assertIn("inputs.fault_inject",source)
            self.assertIn("exit 61",source)
            self.assertIn("!inputs.recovery_only",source)
        live=(repo/".github/workflows"/
              "sentinel-real-failover-drill.yml").read_text()
        self.assertIn("fault-drill-one-shot-lock.json",live)
        self.assertIn("actions: write",live)
        self.assertIn("SENTINEL_PAUSED",live)
        self.assertIn("failover-drill-receipt.json",live)

    def test_no_unbounded_jobs_or_production_access(self):
        source=Path(d.__file__).read_text()
        for forbidden in ("kubectl ","docker compose","deploy_production",
                          "git push --force","os.system(",
                          "pickle.load(","torch.load("):
            self.assertNotIn(forbidden,source)
        self.assertIn("WAIT_SECONDS=26*60",source)
        self.assertIn("PAGESIZE=30",source)


if __name__=="__main__":
    unittest.main()
