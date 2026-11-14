"""Tests original source-pinned Physarum Tero + Jones and real CODEX sibling trials."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v40_physarum_bridge as p
from tools import essence_v37_codex_gpt as c


class PhysarumDonorTests(unittest.TestCase):
    def test_authentic_original_source_pinned_and_no_legacy_execution(self):
        self.assertEqual(p.PHYSARUM_ORIGIN["sha256"],
            "e0e7a7d6f62acbae18a68141c4708f9d0006679d5e58bb95f36bc74c398dcf13")
        self.assertEqual(p.PHYSARUM_ORIGIN["size_bytes"],13493)
        self.assertFalse(p.PHYSARUM_ORIGIN["original_code_executed"])
        src=Path(p.__file__).read_text()
        self.assertNotIn("import physarum_engine",src)
        self.assertNotIn("pickle.load(",src)
        self.assertNotIn("torch.load(",src)
        self.assertNotIn("subprocess.",src)

    def test_tero_flow_conserves_mass_and_adapts_conductivity(self):
        n=p.TeroNetwork()
        init=n.d[5][6]
        q=n.step(5,9)
        self.assertAlmostEqual(sum(q[5]),1.0,places=7)
        self.assertAlmostEqual(sum(q[9]),-1.0,places=7)
        self.assertTrue(all(abs(sum(q[i]))<1e-7 for i in range(15)
                            if i not in (5,9)))
        self.assertEqual(q[5][6],-q[6][5])
        for _ in range(4):
            n.step(5,9)
        self.assertNotEqual(n.d[5][6],init)

    def test_disconnect_or_invalid_flow_fails_closed(self):
        n=p.TeroNetwork()
        with self.assertRaisesRegex(ValueError,"INVALID_PHYSARUM_TERMINALS"):
            n.step(5,5)
        with self.assertRaisesRegex(ValueError,"INVALID_PHYSARUM_TIMESTEP"):
            n.step(5,9,0.3)
        for i in range(n.n):
            n.d[0][i]=n.d[i][0]=0
        with self.assertRaisesRegex(ValueError,"PHYSARUM_DISCONNECTED_GRAPH"):
            n.step(0,9)

    def test_jones_swarm_is_reproducible_and_bounded(self):
        attract=[[1/(1+x+y) for x in range(5)] for y in range(3)]
        a=p.JonesSwarm()
        b=p.JonesSwarm()
        for _ in range(13):
            a.step(attract);b.step(attract)
        self.assertEqual(a.trail,b.trail)
        self.assertTrue(all(0<=x<=4 and 0<=y<=2 for x,y,_ in a.particles))
        self.assertGreater(sum(map(sum,a.trail)),0)

    def test_physarum_proposes_only_unseen_frozen_grid_candidate(self):
        observations={5:5.51,7:5.32,9:5.38}
        a=p.choose_physarum(observations)
        b=p.choose_physarum(observations)
        self.assertEqual(a,b)
        self.assertNotIn(a["selected"]["grid_index"],observations)
        self.assertEqual(a["baseline"]["grid_index"],7)
        self.assertEqual(a["network_steps"],12)
        self.assertEqual(a["swarm_steps"],12)
        self.assertFalse(a["future_external_exam_used"])

    def test_hidden_data_and_invalid_probe_veto(self):
        with self.assertRaisesRegex(ValueError,"INVALID_DEVELOPMENT_PROBE_SET"):
            p.choose_physarum({5:5.1,7:5.2,8:5.3})
        with self.assertRaisesRegex(ValueError,"INVALID_PROBE_LOSS"):
            p.choose_physarum({5:5.1,7:float("nan"),9:5.3})
        with self.assertRaisesRegex(ValueError,"INVALID_PROBE_LOSS"):
            p.choose_physarum({5:5.1,7:False,9:5.3})
        with self.assertRaisesRegex(ValueError,"INVALID_PARAMETER_GRID_INDEX"):
            p.config(1000)

    def test_real_g3_inherited_shadow_siblings_without_external_exam(self):
        import torch
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as root:
            torch.manual_seed(100)
            original=c.new_model(torch)
            raw,_=p.prior.weight_bytes(torch,original)
            sha=hashlib.sha256(raw).hexdigest()
            fakefreeze={"receipt_sha256":"c"*64}
            man={"manifest_sha256":"b"*64}
            train=torch.tensor(list(b"def verified_test_only():\n return True\n"*200),
                               dtype=torch.long)
            with patch.object(p,"load_g3",
                              return_value=(fakefreeze,original,man)),\
                 patch.object(p.prior,"train_bytes",
                              return_value=(train,train)),\
                 patch.object(p,"G3_WEIGHTS_SHA256",sha),\
                 patch.object(p,"G3_MANIFEST_SHA256","b"*64):
                with patch.object(p.g3,"github_fetch_pinned",
                                  side_effect=AssertionError(
                                      "EXTERNAL_EXAM_MUST_NOT_BE_FETCHED")):
                    report=p.run(root,"unused","unused",Path(root)/"shadow")
            self.assertEqual(report["measured_train_steps_including_probes"],22)
            self.assertTrue(report["sibling_results"]["control"]["actual_neural_update"])
            self.assertTrue(report["sibling_results"]["physarum"]["actual_neural_update"])
            self.assertEqual(report["g3_parent_weight_sha256"],sha)
            self.assertFalse(report["g3_external_cohort_consumed"])
            self.assertFalse(report["future_blind_generalization_proven"])
            self.assertFalse(report["production_authority"])
            self.assertNotEqual(report["sibling_results"]["control"]["weights_sha256"],
                                report["sibling_results"]["physarum"]["weights_sha256"])
            self.assertEqual(report["receipt_sha256"],p.prior.sha({
                k:v for k,v in report.items() if k!="receipt_sha256"}))


if __name__=="__main__":
    unittest.main()
