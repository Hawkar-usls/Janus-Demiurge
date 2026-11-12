"""Synthetic R2 source/context checks. Not an independent held-out benchmark."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from janus_model.hrain_retrieval_eval_r2 import (
    BenchmarkHold, _evaluate_ranking, filename_baseline, run_benchmark,
)


class RetrievalBenchmarkR2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.projection = self.root / "projection.json"
        self.fixture = self.root / "cases.json"
        self.hrain = self.root / "hrain_select.py"
        self.nodes = [
            {"path":"data/rowan/ONE.json","label":"Rowan One","summary":"pipeline source","lineageKey":"ROWAN","readOnly":True,"deleteAllowed":False},
            {"path":"data/OTHER.json","label":"Other","summary":"unrelated","lineageKey":"OTHER","readOnly":True,"deleteAllowed":False},
        ]
        self.index = {
            "schema": "janus.hrain.registry_graph_index.v1_0",
            "status": "AUTO_GENERATED_READ_ONLY_ACTIVE_REGISTRY_PROJECTION",
            "sourceCommit": "a" * 40,
            "repository": "Hawkar-usls/janus-meta-registry",
            "mutationPolicy": {"interfaceWriteAuthority":False,"interfaceDeleteAuthority":False},
            "nodes": self.nodes,
        }
        self.cases = {
            "schema": "janus.native.hrain_retrieval_r2_development_smoke.v1",
            "status": "FROZEN_DEVELOPMENT_ANCHORS_NOT_INDEPENDENT_HOLDOUT",
            "projection_repo": "Hawkar-usls/janus-meta-registry",
            "projection_source_commit": "a" * 40,
            "node_count_expected": 2,
            "limit": 3,
            "cases":[
                {"id":"rowan","query":"rowan","gold":["data/rowan/ONE.json"]},
                {"id":"abstention","query":"frobnozzle","gold":[]},
            ],
            "authority":{
                "independent_blind_labels":False,"models_trained_on_cases":False,
                "scientific_claims_permitted":False,"registry_writes":False,
                "candidate_promotion":False,
            },
        }
        self.hrain.write_text(
            "def validate_projection(p):\n"
            "    assert isinstance(p['nodes'],list)\n"
            "def select_nodes(p,q,limit):\n"
            "    return [{'path':n['path']} for n in p['nodes'] if q.lower() in n['path'].lower()][:limit]\n",
            encoding="utf-8",
        )
        self.save()

    def save(self):
        self.projection.write_text(json.dumps(self.index))
        self.fixture.write_text(json.dumps(self.cases))

    def test_comparable_smoke_metrics_and_no_match_abstention(self):
        r = run_benchmark(self.projection,self.fixture,self.hrain)
        self.assertEqual(r["query_count"],2)
        self.assertEqual(r["hrain_graph"]["correct_cases"],2)
        self.assertEqual(r["filename_only_baseline"]["correct_cases"],2)
        self.assertEqual(r["hrain_graph"]["no_match_correct_abstentions"],1)
        self.assertFalse(r["model_answer_accuracy_measured"])
        self.assertFalse(r["claim_of_independent_generalization"])
        self.assertEqual(r["hrain_graph"]["cases_detail"][0]["gold_source_paths"], ["data/rowan/ONE.json"])
        self.assertEqual(r["hrain_graph"]["cases_detail"][1]["returned_source_paths"], [])

    def test_wrong_index_refused(self):
        self.index["sourceCommit"] = "b" * 40
        self.save()
        with self.assertRaisesRegex(BenchmarkHold,"FIXTURE_SOURCE_DRIFT"):
            run_benchmark(self.projection,self.fixture,self.hrain)

    def test_malformed_authority_refused(self):
        self.cases["authority"]["scientific_claims_permitted"] = True
        self.save()
        with self.assertRaisesRegex(BenchmarkHold,"FIXTURE_AUTHORITY_HOLD"):
            run_benchmark(self.projection,self.fixture,self.hrain)

    def test_gold_must_be_in_pinned_index(self):
        self.cases["cases"][0]["gold"] = ["data/imaginary.json"]
        self.save()
        with self.assertRaisesRegex(BenchmarkHold,"CASE_LABELS_INVALID"):
            run_benchmark(self.projection,self.fixture,self.hrain)

    def test_unrelated_documents_do_not_count_as_success(self):
        cases=[{"id":"q","query":"rowan","gold":["data/rowan/ONE.json"]}]
        fake=lambda q,k:["data/OTHER.json"]
        r=_evaluate_ranking(cases,fake,3)
        self.assertEqual(r["correct_cases"],0)
        self.assertEqual(r["hit_at_k_count"],0)

    def test_filename_baseline_no_guess(self):
        self.assertEqual(filename_baseline(self.index,"frobnozzle",3),[])
        self.assertEqual(filename_baseline(self.index,"rowan",3),["data/rowan/ONE.json"])


if __name__=="__main__":
    unittest.main()
