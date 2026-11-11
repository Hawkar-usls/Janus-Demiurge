"""Ocean R3 read-only witness acceptance/poisoning tests; stdlib only."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from experiments.ocean_transformer.ocean_r3_registry_bridge import (
    SOURCE_SCHEMA, QUALITY_SCHEMA, OCEAN_SCHEMA, chronology_allowed,
    registry_witness, verify_pair, combine, digest,
)

HEAD="a7b2e83e0c6abe8ac024486c7296c2f3f893b56f"
SHA="a"*64

def records():
    source={
        "schema":SOURCE_SCHEMA,
        "sources":{"wikipedia":{"status":"PUBLIC_ENCYCLOPEDIA_METADATA",
                                 "article_metadata":[{"title":"Time dilation"}]}},
        "source_class":"PUBLIC_UNTRUSTED_METADATA_QUARANTINE",
        "training_permitted":False,"factual_claims_verified":False,
        "scientific_admission":"HOLD",
        "observed_at_utc":"2026-11-11T16:00:00+00:00"
    }
    source["source_digest_sha256"]=digest(source["sources"])
    source["record_id"]="JANUS-PUBLIC-SOURCES-"+source["source_digest_sha256"][:20]
    source["receipt_sha256"]=digest(source)
    quality={
        "schema":QUALITY_SCHEMA,
        "source_record_id":source["record_id"],
        "source_receipt_sha256":source["receipt_sha256"],
        "source_digest_sha256":source["source_digest_sha256"],
        "new_metadata_id_count":1,
        "metadata_sources_with_integrity":1,
        "proposed_action":"HUMAN_REVIEW_ONLY",
        "model_training_authorized":False,
        "model_training_dispatched":False,
        "scientific_knowledge_promoted":False,
        "neural_model_improved":False,
        "news_claims_fact_checked":False,
        "article_claims_independently_verified":False,
        "external_blind_science_evaluator_used":False
    }
    quality["quality_receipt_sha256"]=digest(quality)
    return source,quality

def write_pair(base,source,quality,with_source=True,with_quality=True):
    root=Path(base)
    sdir=root/"data/observations/public_source_quarantine"
    qdir=root/"data/observations/public_source_quality"
    sdir.mkdir(parents=True,exist_ok=True);qdir.mkdir(parents=True,exist_ok=True)
    name=source["record_id"].removeprefix("JANUS-PUBLIC-SOURCES-")
    if with_source:
        (sdir/(source["record_id"]+".json")).write_text(json.dumps(source))
    if with_quality:
        (qdir/("JANUS-R3-QUALITY-"+name+".json")).write_text(json.dumps(quality))

class OceanR3(unittest.TestCase):
    def test_legacy_no_quality_does_not_auto_approve(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"data/observations/public_source_quarantine"
            p.mkdir(parents=True)
            # Existing pre-R3 observation is recognized as legacy only.
            (p/"JANUS-PUBLIC-SOURCES-5277ff2d788de4b43f27.json").write_text("{}")
            result=registry_witness(td,HEAD)
            self.assertEqual(result["paired_reviewed_metadata_records"],0)
            self.assertEqual(result["status"],"WAITING_FOR_FIRST_MERGED_R3_PAIR")
            self.assertFalse(result["raw_news_used_for_training"])
            self.assertEqual(result["scientific_admission"],"HOLD")

    def test_valid_linked_pair_is_research_context_not_gradient(self):
        s,q=records()
        with tempfile.TemporaryDirectory() as td:
            write_pair(td,s,q)
            out=registry_witness(td,HEAD)
            self.assertEqual(out["paired_reviewed_metadata_records"],1)
            self.assertEqual(out["newest_pairs"][0]["source_record_id"],s["record_id"])
            self.assertEqual(out["status"],"R3_METADATA_PRESENT_REVIEW_ONLY")
            self.assertFalse(out["quality_metadata_used_as_gradient_labels"])
            self.assertFalse(out["ocean_production_promotion"])
            self.assertEqual(out["witness_sha256"],
                digest({k:v for k,v in out.items() if k!="witness_sha256"}))

    def test_source_tamper_fails_even_when_filename_matches(self):
        s,q=records();s["training_permitted"]=True
        with self.assertRaisesRegex(ValueError,"R3_SOURCE_RECEIPT_HASH"):
            verify_pair(s,q)

    def test_quality_model_trust_escalation_always_refused(self):
        s,q=records();q["model_training_authorized"]=True
        q["quality_receipt_sha256"]=digest({k:v for k,v in q.items()
                                            if k!="quality_receipt_sha256"})
        with self.assertRaisesRegex(ValueError,"R3_QUALITY_UNTRUSTED_PROMOTION"):
            verify_pair(s,q)

    def test_orphan_pair_fails(self):
        s,q=records()
        with tempfile.TemporaryDirectory() as td:
            write_pair(td,s,q,with_source=False)
            with self.assertRaisesRegex(ValueError,"R3_ORPHAN_QUALITY"):
                registry_witness(td,HEAD)

    def test_nonlegacy_unpaired_source_fails(self):
        s,q=records()
        with tempfile.TemporaryDirectory() as td:
            write_pair(td,s,q,with_quality=False)
            with self.assertRaisesRegex(ValueError,"R3_NEW_UNPAIRED"):
                registry_witness(td,HEAD)

    def test_neural_chronology_excludes_quarantine_and_own_feedback(self):
        for path in (
            "data/observations/public_source_quarantine/JANUS-PUBLIC-SOURCES-x.json",
            "data/observations/public_source_quality/JANUS-R3-QUALITY-x.json",
            "data/JANUS-META-NEXT-self.json",
            "data/JANUS-AIR-ALERT-forecast.json"
        ):
            self.assertFalse(chronology_allowed(path),path)
        self.assertTrue(chronology_allowed("data/experiments/APPROVED-PUBLIC-PAPER.json"))

    def test_ocean_summary_links_real_model_metrics_without_promotion(self):
        s,q=records()
        with tempfile.TemporaryDirectory() as td:
            write_pair(td,s,q)
            witness=registry_witness(td,HEAD)
            report={
                "schema":"janus.meta_next.train_result.v1",
                "production_promotion":False,
                "candidate_weights_sha256":SHA,
                "test_model":{"accuracy":.28},
                "test_baselines":{"majority_accuracy":.32,"markov_accuracy":.37},
                "architecture":"JanusTinyTransformer",
                "meta_head":HEAD
            }
            result=combine(report,witness)
            self.assertEqual(result["source_metadata_pairs_accepted_as_research_context"],1)
            self.assertEqual(result["model_test_accuracy"],.28)
            self.assertFalse(result["model_auto_promoted"])
            self.assertTrue(result["model_improvement_not_established_by_metadata"])

    def test_no_production_model_promotion_even_when_model_is_better(self):
        s,q=records()
        with tempfile.TemporaryDirectory() as td:
            write_pair(td,s,q)
            witness=registry_witness(td,HEAD)
            report={"schema":"janus.meta_next.train_result.v1",
                    "production_promotion":True,
                    "candidate_weights_sha256":SHA,
                    "test_model":{"accuracy":1.0},
                    "test_baselines":{"majority_accuracy":.2,"markov_accuracy":.3}}
            with self.assertRaisesRegex(ValueError,"OCEAN_CANDIDATE_NOT_RESEARCH_ONLY"):
                combine(report,witness)

    def test_invalid_registry_head_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"META_HEAD_NOT_A_SHA"):
                registry_witness(td,"main")

if __name__=="__main__":
    unittest.main()
