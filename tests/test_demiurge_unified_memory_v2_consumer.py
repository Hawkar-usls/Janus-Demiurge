from __future__ import annotations
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TARGET=Path(__file__).resolve().parents[1]/"tools"/"demiurge_unified_memory_v2_consumer.py"
spec=importlib.util.spec_from_file_location("demiurge_umv2_consumer",TARGET)
consumer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)
COMMIT="a"*40
MANIFEST="b"*64
PREFIX="https://github.com/Hawkar-usls/janus-meta-registry/blob/"+COMMIT+"/"

def fixture():
    p={
        "schema":consumer.INPUT_SCHEMA,
        "origin":{"repository":consumer.REPO,"source_commit":COMMIT,
                  "source_manifest_sha256":MANIFEST,"index_sha256":"9"*64,
                  "indexed_json":2,"explicit_relations":1},
        "query":{"text":"SCOBY","fts_literal":'"SCOBY"',"limit":8},
        "matches":[{"id":1,"path":"research/scoby.json","title":"SCOBY","sha256":"1"*64,
                    "url":PREFIX+"research/scoby.json","parse_status":"OK","excerpt":"SCOBY",
                    "related":[{"id":2,"path":"research/skin.json","sha256":"2"*64,
                                "url":PREFIX+"research/skin.json","kind":"EXPLICIT_PATH"}]}],
        "control":{"read_only":True,"external_effect_permitted":False,"direct_graph_mutation_permitted":False,
                   "github_write_permitted":False,"authority_delta":0,"mass_effect_budget_delta":0},
        "claim_ceiling":{"catalog_presence_is_truth":False,
                         "reference_is_independent_evidence":False,
                         "memory_proposal_is_admission":False,"receipts_are_authentication":False}
    }
    p["packet_sha256"]=consumer.digest(p)
    return p

def rehash(p):
    p["packet_sha256"]=consumer.digest({k:v for k,v in p.items() if k!="packet_sha256"})
    return p

class DemiurgeMemoryConsumerTests(unittest.TestCase):
    def check(self,packet):
        return consumer.project(packet,source_commit=COMMIT,manifest_sha256=MANIFEST)
    def test_accepts_pinned_context_only(self):
        result=self.check(fixture())
        self.assertEqual(result["status"],"CONTEXT_CANDIDATE_READ_ONLY")
        self.assertEqual((len(result["graph"]["nodes"]),len(result["graph"]["edges"])),(2,1))
        self.assertFalse(result["routing"]["module_admission_authorized"])
        self.assertFalse(result["claim_ceiling"]["scientific_truth_established"])
    def test_existing_memory_graph_query_accepts_projection(self):
        from restored.memory_graph_query import related_subgraph
        output=self.check(fixture())
        graph=related_subgraph(output["graph"],"research/scoby.json",depth=1)
        self.assertTrue(graph["found"])
        self.assertEqual((len(graph["nodes"]),len(graph["edges"])),(2,1))
        self.assertFalse(graph["authority"]["mutates_graph"])
        self.assertFalse(graph["authority"]["declares_semantic_truth"])
    def test_detects_hash_tampering(self):
        packet=fixture();packet["matches"][0]["title"]="forged"
        with self.assertRaisesRegex(ValueError,"PACKET_INTEGRITY_HOLD"):
            self.check(packet)
    def test_rejects_authority_escalation_even_rehashed(self):
        packet=fixture();packet["control"]["github_write_permitted"]=True
        with self.assertRaisesRegex(ValueError,"AUTHORITY_DELTA_HOLD"):
            self.check(rehash(packet))
    def test_rejects_wrong_expected_pin(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_PIN_MISMATCH"):
            consumer.project(fixture(),source_commit="c"*40,manifest_sha256=MANIFEST)
    def test_rejects_forged_link_even_rehashed(self):
        packet=fixture();packet["matches"][0]["related"][0]["url"]="https://evil.invalid/record"
        with self.assertRaisesRegex(ValueError,"DOCUMENT_SOURCE_PROVENANCE_HOLD"):
            self.check(rehash(packet))
    def test_rejects_unbounded_matches(self):
        packet=fixture();packet["query"]["limit"]=1
        packet["matches"].append({**packet["matches"][0],"id":2,"path":"research/skin.json",
            "sha256":"2"*64,"url":PREFIX+"research/skin.json","related":[]})
        with self.assertRaisesRegex(ValueError,"MATCH_BUDGET_HOLD"):
            self.check(rehash(packet))
if __name__=="__main__":unittest.main()
