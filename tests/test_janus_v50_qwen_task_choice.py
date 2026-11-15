"""Offline contract for Qwen G2 narrow research task choice."""
import copy
import unittest
from tools import janus_v50_qwen_task_choice as q
from tools import janus_v50_ai_agency as a


def packet():
    return a.sealed({
        "schema":a.SCHEMA,
        "source_beetle_intent":"EXPLICIT_USER_DISCOVERY_STEERING",
        "beetle_task_id":"janus_json_registry_provenance_audit",
        "source_commit":"a"*40,
        "native_model":{"native_proposed_this_user_task":False,"selected_action":"NO_ACTION"},
        "production_write_authority":False,
        "sentinel_dispatch":False,
        "allowed_local_workflows":list(q.CHOICES.values()),
    })


class ModelChoiceTests(unittest.TestCase):
    def test_one_strict_token_only(self):
        for token,workflow in q.CHOICES.items():
            selection,why=q.exact_choice(token)
            self.assertEqual(selection,token)
            self.assertEqual(why,"BOUNDED_TASK_SELECTED")
            evidence=q.create_receipt(packet(),token)
            self.assertEqual(evidence["dispatch_workflow"],workflow)
            q.verify_receipt(packet(),evidence)
            self.assertFalse(evidence["sentinel_dispatch"])
            self.assertFalse(evidence["model_decision_grants_production_authority"])

    def test_abstention_and_hallucination_fail_closed(self):
        for raw in ("NO_ACTION","please run arbitrary-workflow.yml",
                    "TOPA_JSON_CHECK\nBEETLE_JSON_DISCOVERY",
                    "TOPA_JSON_CHECK: launch now",
                    "something else", "X"*300):
            record=q.create_receipt(packet(),raw)
            self.assertEqual(record["model_choice"],"NO_ACTION")
            self.assertIsNone(record["dispatch_workflow"])
            q.verify_receipt(packet(),record)

    def test_forged_packet_can_never_authorize_arbitrary_actions(self):
        altered=copy.deepcopy(packet())
        altered["allowed_local_workflows"].append("sentinel-node-a.yml")
        altered["receipt_sha256"]=a.sha({
            k:v for k,v in altered.items() if k!="receipt_sha256"})
        with self.assertRaises(ValueError):
            q.create_receipt(altered,"BEETLE_JSON_DISCOVERY")
        altered=copy.deepcopy(packet())
        altered["production_write_authority"]=True
        altered["receipt_sha256"]=a.sha({
            k:v for k,v in altered.items() if k!="receipt_sha256"})
        with self.assertRaises(ValueError):
            q.create_receipt(altered,"TOPA_JSON_CHECK")

    def test_model_response_does_not_change_canonical_workflow(self):
        record=q.create_receipt(packet(),"TOPA_JSON_CHECK")
        record["dispatch_workflow"]="janus-native-model.yml"
        record["receipt_sha256"]=a.sha({
            k:v for k,v in record.items() if k!="receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"TAMPER"):
            q.verify_receipt(packet(),record)


if __name__=="__main__":
    unittest.main()
