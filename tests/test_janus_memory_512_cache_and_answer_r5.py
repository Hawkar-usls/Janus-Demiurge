"""R5 cache+native eval regression tests; synthetic public files only."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from janus_model.memory_512_audit_index_r3 import Hold
from janus_model import memory_512_cache_r5 as cache
from janus_model.memory_512_answer_eval_r5 import packed_prompt, source_answer


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.src=root/"src"
        self.cat=root/"catalog"
        self.src.mkdir()
        self.cat.mkdir()
        self.src_path="data/rowan/pipeline.json"
        self.payload=json.dumps({
            "latest_completed_source_run":"42969641041",
            "related_paths":["data/rowan/other.json"],
            "archived_receipt_sha256_prefixes":["b"*20],
        },sort_keys=True).encode()
        f=self.src/self.src_path
        f.parent.mkdir(parents=True)
        f.write_bytes(self.payload)
        self.source_commit=self.git(self.src,init=True)
        row={
            "path":self.src_path,
            "extension":".json","namespace":"data",
            "sha256":sha(self.payload),
            "size_bytes":len(self.payload),
            "read_only":True,"scientific_authority_granted":False,
        }
        shard={
            "schema":"janus.hrain.full_memory_shard.v1",
            "status":"READ_ONLY_FULL_CURRENT_MEMORY_SHARD",
            "source_commit":self.source_commit,
            "source_repository":"Hawkar-usls/janus-meta-registry",
            "shard_index":0,"object_count":1,"objects":[row],
            "authority":{"read_only":True,"delete_allowed":False,
                         "source_mutation_allowed":False,"scientific_authority_granted":False},
        }
        p="assets/hrain-full-memory/shards/0000.json"
        shard_raw=json.dumps(shard,sort_keys=True).encode()
        shard_file=self.cat/p
        shard_file.parent.mkdir(parents=True)
        shard_file.write_bytes(shard_raw)
        manifest={
            "schema":"janus.hrain.full_memory_manifest.v1",
            "status":"FULL_CURRENT_TRACKED_TREE_CATALOG",
            "source_commit":self.source_commit,
            "source_repository":"Hawkar-usls/janus-meta-registry",
            "coverage":{"coverage_complete":True,"cataloged_blob_count":1,
                        "tracked_blob_count":1,"generated_self_export_exclusion_count":0},
            "statistics":{"cataloged_bytes":len(self.payload)},
            "authority":{"read_only":True,"delete_allowed":False,
                         "source_mutation_allowed":False,"scientific_authority_granted":False},
            "sharding":{"shard_count":1,"shards":[{"index":0,"path":p,
                "sha256":sha(shard_raw),"object_count":1,
                "first_path":self.src_path,"last_path":self.src_path}]},
        }
        mf=self.cat/"assets/hrain-full-memory/manifest.json"
        mf.parent.mkdir(parents=True,exist_ok=True)
        mf.write_text(json.dumps(manifest,sort_keys=True))
        self.catalog_commit=self.git(self.cat,init=True)
        self.cache_dir=root/"cache"

    @staticmethod
    def git(root,init=False):
        def git(*args):
            return subprocess.check_output(
                ["git","-C",str(root),*args],text=True).strip()
        if init:
            git("init","-q")
            git("config","user.name","synthetic r5")
            git("config","user.email","r5-test@example.invalid")
            git("add",".")
            git("commit","-qm","synthetic immutable state")
            return git("rev-parse","HEAD")
        return git()

    def pins(self):
        return patch.multiple(cache,EXPECTED_SOURCE_COMMIT=self.source_commit,
                              EXPECTED_CATALOG_COMMIT=self.catalog_commit,
                              EXPECTED_DOCS=1,EXPECTED_BYTES=len(self.payload))

    def test_new_cache_then_verified_cross_run_hit(self):
        with self.pins():
            new=cache.ensure_cached_index(self.cache_dir,self.cat,self.src)
            again=cache.ensure_cached_index(self.cache_dir,self.cat,self.src)
        self.assertEqual(new["status"],"BUILT_NEW_INDEX_AND_VERIFIED")
        self.assertEqual(again["status"],"REUSED_INDEX_VERIFIED_AGAINST_PINNED_SOURCE")
        self.assertEqual(again["docs"],1)
        self.assertFalse(again["cache_is_permanent"])
        self.assertEqual(subprocess.check_output(
            ["git","-C",str(self.src),"status","--porcelain"],text=True).strip(),"")

    def test_corrupted_sqlite_never_silently_rebuilt(self):
        with self.pins():
            cache.ensure_cached_index(self.cache_dir,self.cat,self.src)
            with (self.cache_dir/"index.sqlite").open("ab") as f:
                f.write(b"corruption")
            with self.assertRaisesRegex(Hold,"R5_SQLITE_SHA_MISMATCH"):
                cache.ensure_cached_index(self.cache_dir,self.cat,self.src)

    def test_corrupt_cache_receipt_rejected(self):
        with self.pins():
            cache.ensure_cached_index(self.cache_dir,self.cat,self.src)
            m=self.cache_dir/"index-receipt.json"
            d=json.loads(m.read_text())
            d["verified_source_bytes"]+=1
            m.write_text(json.dumps(d))
            with self.assertRaisesRegex(Hold,"R5_CACHE_RECEIPT_TAMPERED"):
                cache.ensure_cached_index(self.cache_dir,self.cat,self.src)

    def test_missing_cache_can_fail_closed(self):
        with self.pins():
            with self.assertRaisesRegex(Hold,"R5_CACHE_MISS_AND_BUILD_NOT_AUTHORIZED"):
                cache.ensure_cached_index(self.cache_dir,self.cat,self.src,allow_rebuild=False)

    def test_source_mutation_fails_before_reuse(self):
        with self.pins():
            cache.ensure_cached_index(self.cache_dir,self.cat,self.src)
            (self.src/self.src_path).write_bytes(b'{"fabricated":true}')
            with self.assertRaisesRegex(Hold,"SOURCE_SHA_OR_SIZE_MISMATCH"):
                cache.ensure_cached_index(self.cache_dir,self.cat,self.src)

    def test_target_scalar_is_from_sha_verified_source(self):
        row={"path":self.src_path,"field":"latest_completed_source_run",
             "expected":"42969641041"}
        eligible=[{"path":self.src_path,"sha256":sha(self.payload),
                   "size_bytes":len(self.payload),
                   "source_commit":self.source_commit}]
        from janus_model import memory_512_answer_eval_r5 as evaluator
        with patch.object(evaluator,"EXPECTED_SOURCE_COMMIT",self.source_commit):
            self.assertEqual(source_answer(self.src,row,eligible),"42969641041")
            bad={**row,"expected":"invented"}
            with self.assertRaisesRegex(Hold,"R5_EVAL_FROZEN_GOLD_MISMATCH"):
                source_answer(self.src,bad,eligible)


class ContextPromptTests(unittest.TestCase):
    def test_memory_prompt_is_bounded_and_cites_actual_source_value(self):
        base=packed_prompt("EDEM Giza gate?","gate_status",None,128)
        memory=packed_prompt("EDEM Giza gate?","gate_status","GEOMETRY_GATE_FAIL",128)
        self.assertLessEqual(len(base.encode())+1,128)
        self.assertLessEqual(len(memory.encode())+1,128)
        self.assertNotIn("GEOMETRY_GATE_FAIL",base)
        self.assertIn("C:gate_status=GEOMETRY_GATE_FAIL",memory)

    def test_oversized_memory_prompt_refused(self):
        with self.assertRaisesRegex(Hold,"R5_EVAL_CONTEXT_OVERFLOW"):
            packed_prompt("x"*41,"long_field_name"*3,"Y"*70,128)
        with self.assertRaisesRegex(Hold,"R5_EVAL_QUESTION_BUDGET"):
            packed_prompt("x"*44,"gate_status",None,128)


if __name__=="__main__":
    unittest.main()
