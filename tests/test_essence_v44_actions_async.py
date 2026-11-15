"""ESSENCE v4.4: standard-library adversarial async state/queue controls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v44_actions_async as worker

EXAMPLE=bytes("def f(x): return x + 33\n","utf-8")
SOURCE_SHA="a"*40


def state(root):
    root=Path(root)/"essence-runtime"
    root.mkdir(parents=True)
    config={
      "schema":worker.CONFIG,
      "data_branch":"essence-actions-state",
      "active_sha256":worker.EXPECTED["baseline14"],
      "shadow_sha256":worker.EXPECTED["physarum"],
      "training_allowed":False,
      "production_authority":False,
      "continuous_hosted_process_claim":False,
      "max_requests_per_wakeup":4,
    }
    (root/"config.json").write_text(json.dumps(config))
    return root


def create(root,name,text):
    path=root/"inbox"/(name+".json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    return path


def request(name,data=EXAMPLE):
    return json.dumps({"schema":worker.REQUEST,
                       "request_id":name,
                       "input_hex":data.hex()})


class GitHubOnlyAsyncWorkerContract(unittest.TestCase):
    def test_payload_is_exactly_24_public_bytes(self):
        self.assertEqual(len(EXAMPLE),24)
        self.assertEqual(worker.validate_hex(EXAMPLE.hex()),EXAMPLE)
        for invalid in ("abc","f"*46,"f"*50,"z"*48,None,""):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError,"EXACTLY_24_BYTES"):
                    worker.validate_hex(invalid)

    def test_idle_pulse_requires_no_model_install_or_branch_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            plan=worker.prepare(root,"pulse","","14325","1",SOURCE_SHA,
                                Path(d)/"plan.json")
            self.assertFalse(plan["needs_models"])
            self.assertEqual(plan["pending_before"],0)
            with patch.object(worker,"real_models",
                              side_effect=AssertionError("no torch needed")):
                out=worker.execute(root,Path(d)/"plan.json",Path(d)/"out.json",
                                   "not-mounted","not-mounted")
            self.assertEqual(out["status"],"IDLE_NO_WORK_PROCESSED")
            self.assertFalse((root/"events").exists())
            self.assertFalse(out["production_authority"])

    def test_queue_processes_real_code_path_with_mocked_models_and_no_bytes_in_results(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            create(root,"job-001",request("job-001"))
            plan=worker.prepare(root,"pulse","","14325","1",SOURCE_SHA,
                                Path(d)/"plan.json")
            self.assertTrue(plan["needs_models"])
            mock_scores={
                "baseline14":{"checkpoint_sha256":worker.EXPECTED["baseline14"],
                              "next_byte":97,"logits_sha256":"a"*64},
                "physarum":{"checkpoint_sha256":worker.EXPECTED["physarum"],
                            "next_byte":98,"logits_sha256":"b"*64},
            }
            with patch.object(worker,"real_models",return_value=(object(),{})):
                with patch.object(worker,"infer",return_value=mock_scores):
                    out=worker.execute(root,Path(d)/"plan.json",
                                       Path(d)/"out.json","c","p")
            self.assertEqual(out["status"],"WORK_PROCESSED")
            self.assertEqual(out["accepted_count"],1)
            receipt=json.loads((root/"results/job-001.json").read_text())
            self.assertEqual(receipt["frozen_models"],mock_scores)
            self.assertTrue(receipt["candidate_shadow_only"])
            self.assertEqual(receipt["active_model"],"baseline14")
            self.assertNotIn(EXAMPLE.hex(),json.dumps(receipt))
            self.assertEqual(receipt["receipt_sha256"],
                             worker.digest({k:v for k,v in receipt.items()
                                            if k!="receipt_sha256"}))
            self.assertTrue((root/"events/14325-1.json").is_file())
            plan2=worker.prepare(root,"pulse","","14326","1",SOURCE_SHA,
                                 Path(d)/"plan2.json")
            self.assertFalse(plan2["needs_models"])

    def test_dispatch_is_one_distinct_result_per_run_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            plan=worker.prepare(root,"infer",EXAMPLE.hex(),"7456","2",
                                SOURCE_SHA,Path(d)/"plan.json")
            self.assertTrue(plan["needs_models"])
            with patch.object(worker,"real_models",return_value=(object(),{})):
                with patch.object(worker,"infer",return_value={
                    "baseline14":{},"physarum":{}
                }):
                    out=worker.execute(root,Path(d)/"plan.json",
                        Path(d)/"out.json","b","p",EXAMPLE.hex())
            self.assertEqual(out["accepted_count"],1)
            self.assertTrue((root/"results/dispatch-7456-2.json").exists())
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_RECEIPT_COLLISION"):
                with patch.object(worker,"real_models",return_value=(object(),{})):
                    with patch.object(worker,"infer",return_value={
                        "baseline14":{},"physarum":{}
                    }):
                        worker.execute(root,Path(d)/"plan.json",
                            Path(d)/"again.json","b","p",EXAMPLE.hex())

    def test_malformed_queue_request_rejected_once_without_torch(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            create(root,"bad-001",json.dumps({
                "schema":worker.REQUEST,"request_id":"bad-001",
                "input_hex":"x"*48}))
            plan=worker.prepare(root,"pulse","","1","1",SOURCE_SHA,
                                Path(d)/"plan.json")
            self.assertFalse(plan["needs_models"])
            with patch.object(worker,"real_models",
                              side_effect=AssertionError("no torch")):
                out=worker.execute(root,Path(d)/"plan.json",
                                   Path(d)/"out.json","b","p")
            self.assertEqual(out["rejected_count"],1)
            self.assertFalse((root/"results/bad-001.json").stat().st_size==0)
            self.assertEqual(json.loads((root/"results/bad-001.json").read_text())[
                "status"],"REJECTED_REQUEST_FAIL_CLOSED")
            self.assertEqual(worker.choose_pending(root)[1],0)

    def test_tampered_state_config_vetoes_before_importing_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            config=json.loads((root/"config.json").read_text())
            config["production_authority"]=True
            (root/"config.json").write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"DATA_BRANCH_CONFIG_TAMPERED"):
                worker.prepare(root,"pulse","","7","1",SOURCE_SHA,
                               Path(d)/"plan.json")

    def test_queue_symlink_refused_and_oversized_request_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            path=create(root,"first",request("first"))
            linked=root/"inbox"/"link.json"
            linked.symlink_to(path)
            with self.assertRaisesRegex(ValueError,"UNSAFE_ASYNC_INBOX_ENTRY"):
                worker.prepare(root,"pulse","","7","1",SOURCE_SHA,
                               Path(d)/"badplan.json")
            linked.unlink()
            oversized=create(root,"huge-001","X"*600)
            plan=worker.prepare(root,"pulse","","7","1",SOURCE_SHA,
                                Path(d)/"plan.json")
            self.assertTrue(plan["needs_models"]) # valid "first" also present
            self.assertEqual(plan["pending_before"],2)
            self.assertEqual(len(oversized.read_bytes()),600)

    def test_model_exception_is_not_incorrectly_counted_as_bad_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            create(root,"job-002",request("job-002"))
            worker.prepare(root,"pulse","","77","1",SOURCE_SHA,
                           Path(d)/"plan.json")
            with patch.object(worker,"real_models",return_value=(object(),{})):
                with patch.object(worker,"infer",
                                  side_effect=RuntimeError("FAIL_NONFINITE")):
                    with self.assertRaisesRegex(RuntimeError,"FAIL_NONFINITE"):
                        worker.execute(root,Path(d)/"plan.json",
                                       Path(d)/"out.json","b","p")
            self.assertFalse((root/"results/job-002.json").exists())

    def test_four_at_a_time_pending_queue_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root=state(d)
            for i in range(9):
                create(root,f"req-{i:03}",request(f"req-{i:03}"))
            plan=worker.prepare(root,"pulse","","1","1",SOURCE_SHA,
                                Path(d)/"plan.json")
            self.assertEqual(len(plan["selected"]),4)
            self.assertEqual(plan["pending_before"],9)

    def test_no_remote_execution_or_production_authority(self):
        text=Path(worker.__file__).read_text()
        self.assertNotIn("torch.load(",text)
        self.assertNotIn("pickle.load(",text)
        self.assertNotIn("eval(",text)
        self.assertNotIn("os.system(",text)
        self.assertNotIn("urllib.request",text)
        self.assertIn("worker_os_persistent",text)
        self.assertIn('"production_authority":False',text)


if __name__=="__main__":
    unittest.main()
