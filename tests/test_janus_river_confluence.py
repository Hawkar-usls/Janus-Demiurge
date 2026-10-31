"""Fail-closed offline tests for Demiurge's source-bound river intake."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import janus_river_confluence as river

HEX = "f" * 40


class FakeGitHub:
    def __init__(self):
        self.heads = {name: format(i + 1, "040x") for i, name in
                      enumerate([*river.BRAIN, *river.RESEARCH])}
        self.docs = {}
        self.run_success = True
        self.drop_ack = False
        self.manifest = {
            "schema": "janus.brain.five_face_cohort.v1",
            "model_calls_enabled": False,
            "paid_provider_calls_enabled": False,
            "default_write_permission": False,
            "faces": [
                {"repository": "Hawkar-usls/" + name, "ref": "main",
                 "anchor_path": anchor, "expected_schema": schema,
                 "role": role}
                for name, (anchor, schema, role) in river.BRAIN.items()
            ],
        }
        for name, (path, schema, _role) in river.BRAIN.items():
            self.docs[(name, path)] = (json.dumps({"schema": schema}).encode("utf-8")
                                       if schema else b"# Exact-source test fixture\n")
        self.docs[("janus-distributed-ai-swarm", "configs/brain_five_faces_v1.json")] = (
            json.dumps(self.manifest).encode("utf-8"))
        self.docs[("Janus-Fundamentum", river.RESEARCH["Janus-Fundamentum"][0])] = json.dumps({
            "schema": "janus.organ.cross_organ_source_link.v1",
            "blocked_claim": "P_VS_NP_OPEN",
        }).encode()
        self.docs[("TOPA", river.RESEARCH["TOPA"][0])] = json.dumps({
            "current_split": {"p_vs_np": "OPEN"},
        }).encode()
        self.docs[("janus-lapis", river.RESEARCH["janus-lapis"][0])] = json.dumps({
            "schema": "janus.universal_beetle.directions.v1", "directions": [],
        }).encode()

    def head(self, repo):
        return self.heads[repo]

    def doc(self, repo, commit, path):
        if commit != self.heads[repo]:
            raise river.Hold("SOURCE_HEAD_MISMATCH")
        return self.docs[(repo, path)]

    def json(self, url):
        if "/workflows/" in url and "/runs?" in url:
            return {"workflow_runs": [
                {"status": "completed", "conclusion": "success",
                 "head_branch": "main", "head_sha":
                    self.heads["janus-distributed-ai-swarm"] if self.run_success else HEX,
                 "event": "push", "id": 42}
            ]}
        if url.endswith("/jobs?per_page=100"):
            names = ["plan", "brain-route", "brain-independent-witness"]
            names += [f"brain-observe ({k})" for k in river.BRAIN]
            names += [f"brain-receive ({k})" for k in river.BRAIN]
            return {"jobs": [{"name": name, "conclusion": "success"} for name in names]}
        if url.endswith("/artifacts?per_page=100"):
            names = ["brain-five-mailboxes", "janus-five-brain-delivery-witness"]
            names += [f"brain-msg-{i}" for i in range(5)]
            names += [f"brain-ack-{i}" for i in range(5 - int(self.drop_ack))]
            return {"artifacts": [{"name": n, "expired": False} for n in names]}
        raise AssertionError("unexpected fake HTTP request: " + url)


POLICY = {
    "schema": "janus.research_organ_fabric.v1",
    "promotion_barrier": {
        "p_vs_np_auto_promotion": False,
        "fundamentum_mutation": False,
        "autonomous_merge": False,
    },
}


class RiverConfluenceTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()

    def test_five_brain_three_science_and_latest_witness(self):
        report = river.confluence(self.gh, POLICY)
        self.assertEqual(report["status"], "READ_ONLY_INTAKE_OK")
        self.assertEqual(report["brain_flow"]["source_count"], 5)
        self.assertEqual(report["science_flow"]["source_count"], 3)
        self.assertEqual(report["brain_flow"]["upstream_witness"]["workflow_run_id"], 42)
        self.assertEqual(report["science_flow"]["p_vs_np"], "OPEN")
        self.assertFalse(report["science_flow"]["universal_polynomial_algorithm_proved"])
        self.assertFalse(report["authority"]["remote_repository_write"])
        self.assertFalse(report["authority"]["new_model_calls"])
        self.assertFalse(report["authority"]["external_workflow_dispatch"])
        self.assertFalse(report["brain_flow"]["upstream_witness"]["artifact_payloads_replayed"])
        self.assertEqual(len({s["source_commit"] for s in report["brain_flow"]["sources"]}), 5)
        self.assertEqual(len({s["repo"] for s in report["science_flow"]["sources"]}), 3)

    def test_stale_workflow_is_hold_not_proven(self):
        self.gh.run_success = False
        report = river.confluence(self.gh, POLICY)
        self.assertEqual(report["status"], "HOLD_UNVERIFIED_UPSTREAM_WITNESS")
        self.assertIn("HOLD", report["brain_flow"]["upstream_witness"]["status"])
        self.assertFalse(report["science_flow"]["scientific_claim_promotion"])

    def test_partial_ack_is_hold(self):
        self.gh.drop_ack = True
        report = river.confluence(self.gh, POLICY)
        self.assertEqual(report["status"], "HOLD_UNVERIFIED_UPSTREAM_WITNESS")

    def test_guardrails_refuse_any_scientific_promotion(self):
        for field in ("p_vs_np_auto_promotion", "fundamentum_mutation", "autonomous_merge"):
            bad = json.loads(json.dumps(POLICY))
            bad["promotion_barrier"][field] = True
            with self.subTest(field=field), self.assertRaises(river.Hold):
                river.confluence(self.gh, bad)

    def test_false_claim_and_modified_face_route_fail_closed(self):
        self.gh.docs[("Janus-Fundamentum", river.RESEARCH["Janus-Fundamentum"][0])] = (
            b'{"schema":"janus.organ.cross_organ_source_link.v1","blocked_claim":"P_EQUALS_NP_PROVED"}')
        with self.assertRaises(river.Hold):
            river.confluence(self.gh, POLICY)
        self.gh = FakeGitHub()
        self.gh.manifest["faces"][0]["role"] = "ADMIN"
        self.gh.docs[("janus-distributed-ai-swarm", "configs/brain_five_faces_v1.json")] = (
            json.dumps(self.gh.manifest).encode())
        with self.assertRaises(river.Hold):
            river.confluence(self.gh, POLICY)

    def test_mismatched_anchor_schema_and_disallowed_paths(self):
        self.gh.docs[("AIFC", river.BRAIN["AIFC"][0])] = b'{"schema":"OTHER"}'
        with self.assertRaises(river.Hold):
            river.confluence(self.gh, POLICY)
        self.assertFalse(river.issha("bad"))
        self.assertTrue(river.issha(HEX))


if __name__ == "__main__":
    unittest.main()
