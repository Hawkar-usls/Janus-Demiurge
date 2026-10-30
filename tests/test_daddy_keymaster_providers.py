"""Provider onboarding never confuses public evidence with owner authorization."""
import copy
import json
from pathlib import Path
import unittest

from daddy_keymaster.providers import compile_status, oci_shape_preflight, checked_input, digest

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = json.loads((ROOT/"daddy_keymaster/PROVIDER_ACTIVATION_REQUESTS.json").read_text())


def oci_fixture(shape="VM.Standard.A1.Flex", state="RUNNING", cpu=1, ram=6):
    return {"data":{"id":"ocid1.instance.oc1..PRIVATE-EXAMPLE",
        "shape":shape, "lifecycle-state":state,
        "shape-config":{"ocpus":cpu, "memory-in-gbs":ram},
        "public-ip":"192.0.2.20","some-private-key":"NEVER_EXPORT"}}


class ProviderActivationTests(unittest.TestCase):
    def test_no_existing_accounts_no_live_external_resources(self):
        out = compile_status(REQUESTS)
        self.assertEqual(out["status"], "NO_EXTERNAL_PROVIDER_ACTIVATED")
        self.assertEqual(set(out["providers"]),
                         {"oracle_always_free", "boinc_volunteer", "ray_cluster"})
        for row in out["providers"].values():
            self.assertFalse(row["actual_capacity_attested"])
            self.assertFalse(row["remote_dispatch_allowed"])
            self.assertTrue(row["missing_requirements"])
        self.assertEqual(out["paid_resources_created"], 0)
        self.assertEqual(out["network_connections_attempted"], 0)
        self.assertEqual(out, compile_status(REQUESTS))

    def test_oracle_synthetic_running_always_free_shape_is_not_account_proof(self):
        out = oci_shape_preflight(oci_fixture())
        self.assertTrue(out["fits_conservative_a1_shape"])
        self.assertFalse(out["home_region_proven"])
        self.assertFalse(out["ownership_proven"])
        self.assertFalse(out["always_free_billing_proven"])
        self.assertFalse(out["enables_remote_dispatch"])
        text=json.dumps(out)
        self.assertNotIn("PRIVATE-EXAMPLE", text)
        self.assertNotIn("192.0.2.20", text)
        self.assertNotIn("NEVER_EXPORT", text)

    def test_oracle_paid_size_or_other_shape_rejected(self):
        for args in ({"cpu":4}, {"ram":24}, {"shape":"VM.Standard3.Flex"},
                     {"state":"STOPPED"}):
            row = oci_shape_preflight(oci_fixture(**args))
            self.assertNotEqual(row["status"], "SHAPE_PREFLIGHT_PASS_OWNERSHIP_STILL_UNKNOWN")

    def test_oracle_missing_shape_proof_fails(self):
        for bad in ({}, {"data":{}}, {"data":{"shape":"VM.Standard.A1.Flex",
                    "shape-config":{"ocpus":True,"memory-in-gbs":6}}},
                    {"data":{"shape":"VM.Standard.A1.Flex",
                    "shape-config":{"ocpus":1,"memory-in-gbs":"6"}}}):
            with self.assertRaises(ValueError):
                oci_shape_preflight(bad)

    def test_self_claimed_perfect_oracle_cannot_activate(self):
        req=copy.deepcopy(REQUESTS)
        req["providers"]["oracle_always_free"] = {k:True for k in req["providers"]["oracle_always_free"]}
        row=compile_status(req)["providers"]["oracle_always_free"]
        self.assertEqual(row["readiness"], "CLAIMS_PRESENT_NEEDS_INDEPENDENT_AUTHENTICATED_VERIFICATION")
        self.assertFalse(row["actual_capacity_attested"])
        self.assertFalse(row["remote_dispatch_allowed"])

    def test_self_claimed_perfect_boinc_ray_cannot_activate(self):
        req=copy.deepcopy(REQUESTS)
        for provider in ("boinc_volunteer","ray_cluster"):
            req["providers"][provider] = {k:True for k in req["providers"][provider]}
        out=compile_status(req)
        for provider in ("boinc_volunteer","ray_cluster"):
            self.assertFalse(out["providers"][provider]["actual_capacity_attested"])
            self.assertFalse(out["providers"][provider]["activation_authority"])

    def test_policy_cannot_create_paid_resources(self):
        for key,val in (("estimated_monthly_cost_usd",1),("deploy_without_review",True),
                        ("remote_execution",True),("secrets_in_repository",True),
                        ("authority_delta",1)):
            req=copy.deepcopy(REQUESTS)
            req[key]=val
            with self.assertRaises(ValueError):
                checked_input(req)

    def test_extra_gate_or_unknown_provider_is_refused(self):
        req=copy.deepcopy(REQUESTS)
        req["providers"]["rogue"]={}
        with self.assertRaises(ValueError):
            checked_input(req)
        req=copy.deepcopy(REQUESTS)
        req["providers"]["ray_cluster"]["public_unauthenticated"]=True
        with self.assertRaises(ValueError):
            checked_input(req)

    def test_no_missing_gate_can_be_string_or_integer(self):
        for v in ("true", 1, None):
            req=copy.deepcopy(REQUESTS)
            req["providers"]["oracle_always_free"]["account_owner_authenticated"]=v
            with self.assertRaises(ValueError):
                checked_input(req)

    def test_need_owner_oci_shape_and_zero_spend_remains_unverified(self):
        out=compile_status(REQUESTS,instance=oci_fixture())
        row=out["providers"]["oracle_always_free"]
        self.assertTrue(row["local_shape_preflight"]["fits_conservative_a1_shape"])
        self.assertFalse(row["actual_capacity_attested"])
        self.assertEqual(out["paid_resources_created"],0)
        self.assertEqual(out["receipt_sha256"],
                         digest({k:v for k,v in out.items() if k!="receipt_sha256"}))


if __name__ == "__main__":
    unittest.main()
