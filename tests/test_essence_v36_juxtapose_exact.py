"""Source-anchored adversarial JUXTAPOSE v3.6 microcore tests (stdlib only)."""
import copy
import itertools
import json
from pathlib import Path
import unittest

from tools import essence_v36_juxtapose_exact as j
from tools import essence_v32_keymaster_memory as km
from tools import essence_v33_epistemic_exchange as epi


def fake_verified_memories():
    k = km.empty_state()
    row = {"sequence":0, "previous_sha256":km.ROOT,
           "evidence_sha256":"a"*64, "source_commit":"a"*40,
           "donor_count":8, "verified_local_lessons":1,
           "keymaster_guard":"HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION",
           "authority_delta":0, "training_admission":False}
    row["receipt_sha256"] = km.seal(row)
    k["history"] = [row]
    k["state_sha256"] = km.seal({p:v for p,v in k.items() if p!="state_sha256"})
    e = epi.empty_state()
    row = {
      "turn":1,"entity":"JANUS_ESSENCE_EPISTEMIC_EXCHANGE",
      "previous_sha256":epi.ROOT,"source_fingerprint_sha256":"b"*64,
      "scout_identities":["SCOUT_%02d" % i for i in range(17)],
      "negative_evidence":[
        {"id":"DOVOD_SHA_25_OF_50_TEST_LEAKAGE","status":"NEGATIVE_CONTROL_CONTAMINATED"},
        {"id":"ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114","status":"HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"},
        {"id":"KEYMASTER_R2_REPLICATED_ABLATIONS","status":"UNRESOLVED_EIGHT_CONTRIBUTORS"},
      ],
      "constraints_inherited":list(epi.LAWS),
      "decision":"INTEGRATED_LESSON_NOT_ASCENDED",
      "production_authority":False}
    row["receipt_sha256"] = epi.seal(row)
    e["history"] = [row]
    e["state_sha256"] = epi.seal({p:v for p,v in e.items() if p!="state_sha256"})
    return k,e


class JuxtaposeExactMicrocoreTests(unittest.TestCase):
    def test_frozen_repository_cases_real_disk(self):
        source = Path(__file__).resolve().parents[1] / (
            "research/essence/juxtapose_v36/frozen_cases.json")
        cases = json.loads(source.read_text())
        receipt = j.run_cases(cases, *fake_verified_memories())
        self.assertEqual(receipt["cases_verified"],4)
        self.assertEqual(receipt["unresolved_negative_cases_preserved"],1)
        self.assertEqual(receipt["status"],"COLD_FULL_EXACT_RESEARCH_PASS_NOT_MODEL_GAIN")
        self.assertTrue(all(x["report"]["coverage_ratio"] == 1.0
                            for x in receipt["cases"]))
        self.assertFalse(receipt["warm_or_hot_authority_earned"])
        self.assertFalse(receipt["future_prospective_gain_proven"])
        self.assertFalse(receipt["production_authority"])
        self.assertEqual(receipt["receipt_sha256"],j.seal(
            {k:v for k,v in receipt.items() if k!="receipt_sha256"}))

    def test_full_exact_root_probe_follows_legal_pivots(self):
        root = [[1,2],[-1,3],[2,-3]]
        x = j.field_search(root,80)
        self.assertEqual(x["mode"],"COLD_JUXTAPOSE_FULL")
        self.assertEqual(x["available_pivots"],3)
        self.assertEqual(x["exact_probed_pivots"],3)
        self.assertEqual(x["coverage_ratio"],1.0)
        self.assertTrue(all(r["exact_verified"] for r in x["receipts"]))
        self.assertTrue(x["chosen_verified_receipt"])

    def test_negated_units_generate_verified_empty_clause(self):
        a = j.normalize([[1],[-1]])
        probe = j.transition(a,1,50)
        self.assertEqual(probe["status"],"TERMINAL_UNSAT")
        self.assertTrue(probe["exact_verified"])
        self.assertEqual(probe["raw_resolvents"],1)

    def test_raw_cap_overflow_never_says_unsat(self):
        x=j.field_search([[1,2],[-1,3],[1,-2],[-1,-3]],1)
        self.assertEqual(x["status"],"UNKNOWN_RESOURCE_LIMIT")
        self.assertIsNone(x["chosen_verified_receipt"])
        self.assertTrue(all(r["status"]=="OVERFLOW" for r in x["receipts"]))
        self.assertFalse(x["theorem_or_p_vs_np_proved"])

    def test_unknown_under_cap_not_given_truth_authority(self):
        x=j.field_search([[1],[-1]],1)
        self.assertEqual(x["status"],"UNKNOWN_RESOURCE_LIMIT")
        self.assertFalse(x["model_predicted_truth"])

    def test_tautology_cnf_canonicalization(self):
        a=j.normalize([[1,-1],[1,2],[-1,3]])
        b=j.normalize([[1,2],[-1,3]])
        self.assertEqual(a,b)

    def test_subsumed_clause_removed(self):
        self.assertEqual(j.normalize([[1],[1,2],[1,2],[2,3]]),
                         j.normalize([[1],[2,3]]))

    def test_invalid_zero_literal(self):
        with self.assertRaisesRegex(ValueError,"INVALID_CNF_LITERAL"):
            j.normalize([[0,1]])

    def test_noninteger_literal(self):
        with self.assertRaisesRegex(ValueError,"INVALID_CNF_LITERAL"):
            j.normalize([[True]])

    def test_more_than_six_variable_ids(self):
        with self.assertRaisesRegex(ValueError,"INVALID_CNF_LITERAL"):
            j.normalize([[7]])

    def test_resource_cap_is_bounded(self):
        with self.assertRaisesRegex(ValueError,"INVALID_RAW_RESOURCE_CAP"):
            j.field_search([[1],[-1]],j.MAX_CAP+1)

    def test_empty_root_is_not_proof(self):
        with self.assertRaisesRegex(ValueError,"NO_NONTERMINAL"):
            j.field_search([],10)

    def test_cold_is_default_without_support_even_if_adviser_confident(self):
        self.assertEqual(j.search_mode(.99,0),"COLD_JUXTAPOSE_FULL")

    def test_warm_only_with_separate_support(self):
        self.assertEqual(j.search_mode(.54,2),"WARM_JUXTAPOSE_HYBRID")

    def test_hot_only_with_stricter_support(self):
        self.assertEqual(j.search_mode(.80,3),"HOT_PREDICTIVE")
        self.assertEqual(j.search_mode(.80,2),"WARM_JUXTAPOSE_HYBRID")

    def test_warm_fallback_expands_until_verified(self):
        x=j.field_search([[1,2],[-1,3],[1,-2]],100,authority=.55,
                         independent_exact_epochs=2)
        self.assertIn(x["status"],("EXACT_TRANSITION_WITNESS_FOUND",
                                  "UNKNOWN_RESOURCE_LIMIT"))
        self.assertTrue(all(r["exact_verified"]
                            for r in x["receipts"] if r["status"]!="OVERFLOW"))

    def test_hot_resource_limit_expands_to_full_field(self):
        x=j.field_search([[1,2],[-1,3],[1,-2],[-1,-3]],1,
                         authority=.9,independent_exact_epochs=4)
        self.assertEqual(x["status"],"UNKNOWN_RESOURCE_LIMIT")
        self.assertEqual(x["exact_probed_pivots"],x["available_pivots"])

    def test_every_probe_receipt_is_sealed(self):
        out=j.field_search([[1,2],[-1,3],[2,-3]],100)
        for r in out["receipts"]:
            self.assertEqual(r["receipt_sha256"],j.seal(
                {k:v for k,v in r.items() if k!="receipt_sha256"}))

    def test_pair_work_not_free_under_parallel_clone(self):
        out=j.field_search([[1,2],[-1,3],[2,-3]],100)
        self.assertEqual(out["total_pair_work_not_free"],sum(
            x["pair_work"] for x in out["receipts"]))

    def test_exact_replay_catches_forged_transition(self):
        before=j.normalize([[1,2],[-1,3]])
        wrong=j.normalize([[2]])
        self.assertFalse(j.exact_exists_replay(before,wrong,1))

    def test_all_small_cnf_truth_tables_property(self):
        # Exhaustively sanity-check many small roots against a second
        # existential semantics implementation, independent of receipt labels.
        clauses=[[1],[-1],[2],[-2],[1,2],[1,-2],[-1,2],[-1,-2]]
        for i in range(1,150):
            formula=[clauses[(i//(1<<k)) % len(clauses)] for k in range(3)]
            cnf=j.normalize(formula)
            vars_={abs(v) for c in cnf for v in c}
            for p in vars_:
                r=j.transition(cnf,p,200)
                self.assertTrue(r["exact_verified"],(formula,p))
                self.assertIn(r["status"],("SAFE","TERMINAL_UNSAT"))

    def test_mismatched_negative_control_rejected_even_if_resigned(self):
        a,b=fake_verified_memories()
        b["history"][0]["negative_evidence"][0]["status"]="FAKE_PASS"
        row=b["history"][0]
        row["receipt_sha256"]=epi.seal({k:v for k,v in row.items()
                                       if k!="receipt_sha256"})
        b["state_sha256"]=epi.seal({k:v for k,v in b.items()
                                   if k!="state_sha256"})
        with self.assertRaisesRegex(ValueError,"NEGATIVE_CONTROLS"):
            j.validate_memory(a,b)

    def test_keymaster_memory_tamper_rejected(self):
        a,b=fake_verified_memories()
        a["history"][0]["verified_local_lessons"]=600
        with self.assertRaisesRegex(ValueError,"MEMORY_STATE_TAMPERED"):
            j.validate_memory(a,b)

    def test_untrusted_memory_no_automatic_hot(self):
        a,b=fake_verified_memories()
        out=j.validate_memory(a,b)
        self.assertEqual(out["independent_calibrated_juxtapose_epochs"],0)
        self.assertEqual(out["research_mode"],
                         "COLD_ONLY_UNTIL_EXACT_INDEPENDENT_CALIBRATION")

    def test_case_status_forgery_fails_closed(self):
        source=Path(__file__).resolve().parents[1] / (
            "research/essence/juxtapose_v36/frozen_cases.json")
        cases=json.loads(source.read_text())
        cases["cases"][0]["expected_status"]="UNKNOWN_RESOURCE_LIMIT"
        with self.assertRaisesRegex(ValueError,"REGRESSION"):
            j.run_cases(cases,*fake_verified_memories())

    def test_no_legacy_import_and_no_production_changes(self):
        import inspect
        code=inspect.getsource(j)
        self.assertNotIn("from experiments.mad_lab",code)
        self.assertNotIn("import juxtapose_250x250_exact",code)
        self.assertFalse(j.field_search([[1],[-1]],100)["production_authority"])


if __name__ == "__main__":
    unittest.main()
