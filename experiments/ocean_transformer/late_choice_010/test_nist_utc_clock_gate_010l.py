#!/usr/bin/env python3
"""No manufactured UTC correspondence, no signal and no photon-tuned offset."""
import unittest
import nist_utc_clock_gate_010l as x


class UTCProvenanceAdmission(unittest.TestCase):
    def test_actual_nist_input_stays_blocked(self):
        record=x.external_inventory()
        result=x.gate(record)
        self.assertEqual(result["status"],"BLOCKED_NO_INDEPENDENT_UTC_PPS_PAIRING")
        self.assertIsNone(result["candidate_from_utc_labels"])
        self.assertFalse(result["absolute_A_B_clock_offset_certified"])
        self.assertFalse(result["eligible_for_future_to_past_inference"])

    def test_hypothetical_external_pps_still_not_certified(self):
        record=x.external_inventory()
        record["has_externally_verified_matching_UTC_second_indices"]=True
        record["utc_pps_pairs"]=[
          {"utc_second":100+i,"alice_tick":100_000_000_000+i*12_800_000_000,
           "bob_tick":50_000_000_000+i*12_800_000_000} for i in range(4)]
        result=x.gate(record)
        self.assertEqual(result["candidate_from_utc_labels"]["candidate_counter_A_minus_B_epoch_ns_exact"],"3906250000")
        self.assertEqual(result["candidate_from_utc_labels"]["range_of_candidate_offsets_ticks"],0)
        self.assertFalse(result["absolute_A_B_clock_offset_certified"])
        self.assertFalse(result["independent_external_provenance_cryptographically_verified"])

    def test_no_unknown_utc_flag_silent_pairing(self):
        data=x.external_inventory()
        data["utc_pps_pairs"]=[{"utc_second":100+i,
          "alice_tick":100+i*100,"bob_tick":50+i*100} for i in range(3)]
        with self.assertRaisesRegex(ValueError,"SELF_PROVIDED_COMMON_UTC_LABELS_UNVERIFIED"):
            x.gate(data)

    def test_duplicate_utc_second_refused(self):
        pairs=[
            {"utc_second":100,"alice_tick":2,"bob_tick":1},
            {"utc_second":100,"alice_tick":3,"bob_tick":2},
            {"utc_second":101,"alice_tick":4,"bob_tick":3}
        ]
        with self.assertRaisesRegex(ValueError,"NONMONOTONIC"):
            x.analyze_utc_pairs(pairs)

    def test_missing_utc_seconds_explicit(self):
        pairs=[
            {"utc_second":100,"alice_tick":200,"bob_tick":100},
            {"utc_second":102,"alice_tick":202,"bob_tick":102},
            {"utc_second":103,"alice_tick":203,"bob_tick":103}
        ]
        with self.assertRaisesRegex(ValueError,"GAP_IN_UTC_SECOND"):
            x.analyze_utc_pairs(pairs)

    def test_integer_timetag_precision_kept_exact(self):
        self.assertEqual(str(x.PERIOD_NS),"5/64")
        a=x.analyze_utc_pairs([
            {"utc_second":j,"alice_tick":10**17+j*1000,
             "bob_tick":10**17-81+j*1000} for j in range(10,13)])
        self.assertEqual(a["candidate_counter_A_minus_B_epoch_ns_exact"],"405/64")

    def test_trusted_hardware_requires_more_than_self_attestation(self):
        data=x.external_inventory()
        data["has_externally_verified_matching_UTC_second_indices"]=True
        data["utc_pps_pairs"]=[
          {"utc_second":j,"alice_tick":5000+j*1000,"bob_tick":4000+j*1000}
          for j in range(20,23)]
        data["clock_anchor_external_custodian_signature_verification"]="I_SAY_TRUST_ME"
        data["hardware_cable_delay_uncertainty_calibration"]={"trust_me":True}
        outcome=x.gate(data)
        self.assertFalse(outcome["physical_timing_validated_for_010"])
        self.assertFalse(outcome["absolute_A_B_clock_offset_certified"])

if __name__=="__main__": unittest.main()
