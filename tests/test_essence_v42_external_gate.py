"""ESSENCE v4.2 adversarial tests — outside custodian workflow only, synthetic tasks."""
import base64
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import essence_v42_cleanroom_verifier as m
from tools import essence_v42_cost_replay as cost


ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/"research/essence/physarum_v42/external_replication_contract.json"


class CleanRoomPhysarumContract(unittest.TestCase):
    def test_protocol_frozen_before_outside_custodian(self):
        p=m.load_protocol(POLICY)
        self.assertEqual(p["status"],
                         "AWAITING_EXTERNAL_CUSTODIAN_AND_CLOSED_CHALLENGE")
        self.assertEqual(p["min_files"],10)
        self.assertEqual(p["min_source_families"],5)
        self.assertFalse(p["scientific_evidence"]["external_researcher_run_finished"])
        self.assertFalse(p["production_authority"])
        src=Path(m.__file__).read_text()
        self.assertNotIn("from tools import essence_v37",src)
        self.assertNotIn("torch.load(",src)
        self.assertNotIn("pickle.load(",src)
        self.assertNotIn("requests.get(",src)

    def synthetic_signing_inputs(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
        contract=m.load_protocol(POLICY)
        key=Ed25519PrivateKey.generate()
        pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        public_b64=base64.b64encode(pub).decode()
        files=[]
        for i in range(10):
            files.append({
                "path":f"tasks/task_{i}.py",
                "family":f"external_project_{i//2}",
                "sha256":hashlib.sha256(str(i).encode()).hexdigest(),
                "bytes":4096
            })
        challenge={
            "schema":m.CHALLENGE,
            "protocol_sha256":m.sha(contract),
            "challenge_id":"synthetic-test-no-scientific-claim",
            "made_after_model_freeze":True,
            "task_data_stays_with_external_custodian":True,
            "files":files,
        }
        sig=base64.b64encode(key.sign(m.canonical(challenge))).decode()
        pre={
            "schema":m.PRECOMMIT,
            "challenge_sha256":m.sha(challenge),
            "protocol_sha256":m.sha(contract),
            "public_external_commit_url":"https://example.org/not-a-real-proof",
            "external_custodian_identity":"SYNTHETIC_UNIT_TEST",
            "independent_organization":"SYNTHETIC_UNIT_TEST",
            "published_before_exam":True,
        }
        return contract,key,public_b64,hashlib.sha256(pub).hexdigest(),challenge,pre,sig

    def test_signatures_verify_but_do_not_establish_independence(self):
        contract,key,pub,fingerprint,ch,pre,sig=self.synthetic_signing_inputs()
        got=m.verify_commitment(contract,ch,pre,pub,sig,fingerprint)
        self.assertEqual(got,fingerprint)
        modified=dict(ch)
        modified["challenge_id"]="TAMPERED"
        with self.assertRaises(Exception):
            m.verify_commitment(contract,modified,pre,pub,sig,fingerprint)
        with self.assertRaisesRegex(ValueError,"UNREGISTERED_CUSTODIAN_FINGERPRINT"):
            m.verify_commitment(contract,ch,pre,pub,sig,"0"*64)

    def test_five_families_two_files_each_and_no_duplicates(self):
        contract,key,pub,fingerprint,ch,pre,sig=self.synthetic_signing_inputs()
        ch2=json.loads(json.dumps(ch))
        ch2["files"][1]["sha256"]=ch2["files"][0]["sha256"]
        sig2=base64.b64encode(key.sign(m.canonical(ch2))).decode()
        pre2=dict(pre, challenge_sha256=m.sha(ch2))
        with self.assertRaisesRegex(ValueError,"DUPLICATED_TEST_SAMPLE"):
            m.verify_commitment(contract,ch2,pre2,pub,sig2,fingerprint)
        ch3=json.loads(json.dumps(ch))
        ch3["files"][9]["family"]="external_project_0"
        sig3=base64.b64encode(key.sign(m.canonical(ch3))).decode()
        pre3=dict(pre, challenge_sha256=m.sha(ch3))
        with self.assertRaisesRegex(ValueError,
                                    "INSUFFICIENT_INDEPENDENT_TASK_FAMILIES"):
            m.verify_commitment(contract,ch3,pre3,pub,sig3,fingerprint)

    def test_cost_requires_signed_full_pheromone_probe_and_training(self):
        contract,key,pub,fingerprint,ch,pre,sig=self.synthetic_signing_inputs()
        data={
            "schema":m.COST,
            "protocol_sha256":m.sha(contract),
            "challenge_sha256":pre["challenge_sha256"],
            "g4_weights_sha256":{k:v["weights"] for k,v in m.G4.items()},
            "measured_on_same_cpu":True,
            "full_probe_steps":6,
            "per_sibling_steps":8,
            "no_cost_imputation":True,
            "hardware_description":"TEST_SYNTHETIC_CPU_NOT_EVIDENCE",
            "measurement_method":"CPU_PROCESS_TIME_SECONDS_REPLAY",
            "control_training_cpu_seconds":8.0,
            "physarum_probes_cpu_seconds":6.0,
            "physarum_network_search_cpu_seconds":0.5,
            "physarum_training_cpu_seconds":8.0,
        }
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"cost.json"
            p.write_text(json.dumps(data))
            signed=base64.b64encode(key.sign(m.canonical(data))).decode()
            self.assertEqual(m.signed_cost_ledger(p,contract,pre,pub,
                                                  signed,fingerprint),data)
            tampered=dict(data,full_probe_steps=0)
            p.write_text(json.dumps(tampered))
            with self.assertRaisesRegex(ValueError,"UNVERIFIABLE_FULL_SEARCH_COST"):
                m.signed_cost_ledger(p,contract,pre,pub,signed,fingerprint)

    def test_positive_result_requires_cpu_efficiency_not_just_loss(self):
        contract=m.load_protocol(POLICY)
        cost_data={
            "control_training_cpu_seconds":8.0,
            "physarum_probes_cpu_seconds":6.0,
            "physarum_network_search_cpu_seconds":0.5,
            "physarum_training_cpu_seconds":8.0
        }
        def rows(phys_value):
            out=[]
            for i in range(10):
                out.append({
                    "family":f"family_{i//2}",
                    "g3":{"cross_entropy":6.0,"inference_cpu_seconds":0.2},
                    "control":{"cross_entropy":5.5,"inference_cpu_seconds":0.2},
                    "physarum":{"cross_entropy":phys_value,
                                "inference_cpu_seconds":0.2}
                })
            return out
        bad=m.grade(rows(5.3),cost_data,contract)
        self.assertFalse(bad["requirement_cost_efficiency"])
        self.assertEqual(bad["statistical_status"],"NO_COST_ADJUSTED_PAIRED_GAIN")
        yes=m.grade(rows(4.0),cost_data,contract)
        self.assertTrue(yes["requirement_cost_efficiency"])
        self.assertEqual(yes["fam_sign_test_one_sided_p"],0.03125)
        self.assertEqual(yes["statistical_status"],"PASS_COST_ADJUSTED_PAIRED_GAIN")
        not_all=m.grade(rows(5.5),cost_data,contract)
        self.assertEqual(not_all["statistical_status"],
                         "NO_COST_ADJUSTED_PAIRED_GAIN")

    def test_real_g4_weights_are_cryptographically_pinned(self):
        self.assertEqual(m.G3_SHA,
                         "7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299")
        self.assertEqual(m.G4["control"]["manifest"],
                         cost.EXPECTED_MANIFESTS["control"])
        self.assertEqual(m.G4["physarum"]["weights"],
                         cost.EXPECTED_WEIGHTS["physarum"])

    def test_tensor_only_clean_model_is_finite(self):
        import torch
        torch.set_num_threads(1)
        net=m.clean_model(torch)
        net.eval()
        seq=torch.tensor([[1]*m.BLOCK,[2]*m.BLOCK],dtype=torch.long)
        with torch.inference_mode():
            pred=net(seq)
        self.assertEqual(tuple(pred.shape),(2,m.BLOCK,256))
        self.assertTrue(bool(torch.isfinite(pred).all()))
        self.assertEqual(m.WINDOWS,32)

    def test_cost_replay_resource_bounds(self):
        with self.assertRaisesRegex(ValueError,"UNBOUNDED_COST_REPLAY"):
            cost.bench("x","y","z","o",repetitions=4)
        self.assertEqual(cost.SEGMENTS,
                         ("probe_1","probe_2","probe_3",
                          "control_training","physarum_training"))


if __name__=="__main__":
    unittest.main()
