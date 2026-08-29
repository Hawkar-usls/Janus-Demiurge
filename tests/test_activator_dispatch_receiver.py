import unittest

from tools.activator_dispatch_receiver import canonical_hash, receive, verify_ack


def packet(target="Hawkar-usls/Janus-Demiurge"):
    body = {
        "schema": "janus.activator.dispatch_packet.v0.3",
        "packet_id": "",
        "created_at": 1.0,
        "activation_id": "act-test",
        "activation_receipt_hash": "a" * 64,
        "route_match": "research_or_anomaly_investigation",
        "target_organ": target,
        "operation": "WAKE_ORGAN_READ_ONLY",
        "risk_class": "R0_INTERNAL_READ_ONLY_ORGAN_WAKE",
        "required_gates": ["raw_provenance", "falsifier"],
        "dispatch_authorized": True,
        "external_effect_authorized": False,
        "claim_authority_granted": False,
        "command_authority_granted": False,
        "effect_scope": "GITHUB_INTERNAL_READ_ONLY_ANALYSIS",
        "delivery_terminal": "AUTHORIZED_INTERNAL_HANDOFF",
    }
    body["packet_id"] = "dsp-" + canonical_hash({
        "activation_receipt_hash": body["activation_receipt_hash"],
        "target_organ": body["target_organ"],
        "operation": body["operation"],
    })
    body["packet_hash"] = canonical_hash(body)
    return body


def reseal(obj):
    obj = dict(obj)
    obj.pop("packet_hash", None)
    obj["packet_hash"] = canonical_hash(obj)
    return obj


class ActivatorDispatchReceiverTests(unittest.TestCase):
    def test_valid_packet_is_acknowledged_without_execution(self):
        ack = receive(packet())
        self.assertTrue(ack["accepted"])
        self.assertEqual(ack["terminal"], "ACK_ACCEPTED_NO_EXECUTION")
        self.assertFalse(ack["execution_authorized"])
        self.assertFalse(ack["execution_performed"])
        self.assertFalse(ack["claim_authority_granted"])
        self.assertFalse(ack["external_effect_authorized"])
        self.assertTrue(verify_ack(ack))

    def test_tampered_packet_is_rejected(self):
        p = packet()
        p["route_match"] = "tampered"
        ack = receive(p)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["terminal"], "ACK_REJECTED_INVALID_PACKET")
        self.assertFalse(ack["execution_performed"])

    def test_wrong_target_is_rejected_even_when_resealed(self):
        p = packet(target="Hawkar-usls/Demi_Head")
        ack = receive(p)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["terminal"], "ACK_REJECTED_WRONG_TARGET")

    def test_authority_escalation_is_rejected_even_when_resealed(self):
        p = packet()
        p["external_effect_authorized"] = True
        p = reseal(p)
        ack = receive(p)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["terminal"], "ACK_REJECTED_AUTHORITY_ESCALATION")
        self.assertFalse(ack["execution_authorized"])

    def test_write_operation_is_rejected_even_when_identity_and_hash_are_recomputed(self):
        p = packet()
        p["operation"] = "EXECUTE_AND_WRITE"
        p["packet_id"] = "dsp-" + canonical_hash({
            "activation_receipt_hash": p["activation_receipt_hash"],
            "target_organ": p["target_organ"],
            "operation": p["operation"],
        })
        p = reseal(p)
        ack = receive(p)
        self.assertFalse(ack["accepted"])
        self.assertEqual(ack["terminal"], "ACK_REJECTED_AUTHORITY_ESCALATION")


if __name__ == "__main__":
    unittest.main()
