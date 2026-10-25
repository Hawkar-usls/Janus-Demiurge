"""Pure unit tests for authenticated-in-data cross-repository science council."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("rowan_council",Path(__file__).resolve().parents[1]/"tools"/"rowan_research_council.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixtures(n=0):
    state={
        "schema_id":"janus.rowan.observer_state.v1",
        "latest_durable_external_run":40147900977,
        "underlying_state_is_derived_from":"f7cbdd46d0f5a620dec8054e7e143f6137081586e471bd3790d7674f9ba0c604",
        "last_completed_mutants":n,
        "topa_gate":"OPEN"
    }
    packet={
        "schema_id":m.AURA_SCHEMA,
        "source":{"upstream_run":state["latest_durable_external_run"],
            "completed_mutants":n,
            "upstream_artifact_sha256":state["underlying_state_is_derived_from"],
            "state_sha256":m.sha(state)},
        "hypotheses":[{"id":hid,"status":"HYPOTHESIS_ONLY__NOT_MEASURED",
            "empirical_truth_probability":None} for hid in m.HYPOS],
        "search_proposals":[{"id":sid} for sid in m.FIXED_SEARCH],
        "next_discriminating_question_id":"RAW_ASSAY_LINEAGE" if n<8 else "EXTERNAL_HOLDOUT",
        "information_gain":"NOT_ESTIMATED_NO_CALIBRATED_HYPOTHESIS_PRIORS",
        "bounded_authority":{k:False for k in ("may_resolve_own_forecast","may_submit_rowan_jobs",
            "may_modify_rowan_credit_budget","may_change_model_weights","may_promote_TPOA_scientific_gate")}
    }
    packet["packet_digest_sha256"]=m.sha(packet)
    return state,packet

class Tests(unittest.TestCase):
    def test_state_zero_does_not_promote(self):
        s,a=fixtures()
        o=m.council(s,a)
        self.assertEqual(o["completed_pilot_cases"],0)
        self.assertEqual(o["next_beetle_direction_id"],"protein_stability_falsifiers")
        self.assertFalse(o["gates"]["rowan_credit_spend_new"])
        self.assertIsNone(o["hypothesis_assigned_probability"])
    def test_completed_requires_external_holdout(self):
        s,a=fixtures(8)
        self.assertEqual(m.council(s,a)["next_aura_question_id"],"EXTERNAL_HOLDOUT")
    def test_deterministic_under_repeated_inputs(self):
        s,a=fixtures()
        self.assertEqual(m.council(s,a),m.council(s,a))
    def test_source_hash_mismatch_hold(self):
        s,a=fixtures()
        s["last_completed_mutants"]=1
        with self.assertRaises(m.CouncilHold):m.council(s,a)
    def test_tampered_oracle_packet_hash_hold(self):
        s,a=fixtures()
        a["search_proposals"][0]["id"]="PRIVATE_KEY_EXFIL"
        with self.assertRaises(m.CouncilHold):m.council(s,a)
    def test_oracle_self_promotion_rejected_even_rehash(self):
        s,a=fixtures()
        a["bounded_authority"]["may_submit_rowan_jobs"]=True
        a["packet_digest_sha256"]=m.sha({k:v for k,v in a.items() if k!="packet_digest_sha256"})
        with self.assertRaises(m.CouncilHold):m.council(s,a)
    def test_probabilities_cannot_be_invented(self):
        s,a=fixtures()
        a["hypotheses"][0]["empirical_truth_probability"]=0.9
        a["packet_digest_sha256"]=m.sha({k:v for k,v in a.items() if k!="packet_digest_sha256"})
        with self.assertRaises(m.CouncilHold):m.council(s,a)
    def test_wrong_scout_lane_is_rejected(self):
        s,a=fixtures()
        a["next_discriminating_question_id"]="RUN_PAID_MODEL"
        a["packet_digest_sha256"]=m.sha({k:v for k,v in a.items() if k!="packet_digest_sha256"})
        with self.assertRaises(m.CouncilHold):m.council(s,a)

if __name__=="__main__":unittest.main()
