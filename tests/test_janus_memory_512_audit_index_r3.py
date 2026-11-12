"""Synthetic source/manifest fixtures; no real registry or frozen holdout."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from janus_model.memory_512_audit_index_r3 import (
    TARGET_BYTES, Hold, _chunks, audit_catalog, build_index,
    multi_hop, search_index,
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Memory512R3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.src = root / "source"
        self.idx = root / "projection"
        self.src.mkdir()
        self.idx.mkdir()
        data = {
            "data/rowan/a.json": json.dumps({
                "title":"Alpha Rowan observation",
                "related_paths":["data/rowan/b.json"],
                "status":"HYPOTHESIS_ONLY",
            }).encode(),
            "data/rowan/b.json": b'{"title":"Beta Rowan followup","verified":false}',
            "data/rowan/copy.json": b'{"title":"Beta Rowan followup","verified":false}',
            "data/rowan/bad.json": b'{"broken"',
            "data/rowan/holdout/protected.json": b'{"title":"secret blind research"}',
            "assets/demo.png": b"\x89PNG\r\nnot text",
        }
        for name, raw in data.items():
            file = self.src / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        self.git(self.src, "init", "-q")
        self.git(self.src, "config", "user.name", "fixture")
        self.git(self.src, "config", "user.email", "fixture@example.invalid")
        self.git(self.src, "add", ".")
        self.git(self.src, "commit", "-qm", "pinned source")
        self.source_sha = self.git(self.src,"rev-parse","HEAD").strip()
        objs = []
        for name, raw in sorted(data.items()):
            extension = Path(name).suffix
            objs.append({
                "extension":extension, "path":name,"namespace":name.split("/")[0],
                "memory_class":"REGISTRY_OBJECT", "sha256":sha(raw),
                "size_bytes":len(raw),"read_only":True,
                "scientific_authority_granted":False,
            })
        self.shard = {
            "schema":"janus.hrain.full_memory_shard.v1",
            "status":"READ_ONLY_FULL_CURRENT_MEMORY_SHARD",
            "source_commit":self.source_sha,
            "source_repository":"Hawkar-usls/janus-meta-registry",
            "shard_index":0,"object_count":len(objs),"objects":objs,
            "authority":{
                "read_only":True,"delete_allowed":False,
                "scientific_authority_granted":False,
                "source_mutation_allowed":False,
            },
        }
        shard_bytes=json.dumps(self.shard,sort_keys=True).encode()
        shard_path="assets/hrain-full-memory/shards/0000.json"
        file=self.idx/shard_path
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(shard_bytes)
        self.manifest={
            "schema":"janus.hrain.full_memory_manifest.v1",
            "status":"FULL_CURRENT_TRACKED_TREE_CATALOG",
            "source_repository":"Hawkar-usls/janus-meta-registry",
            "source_commit":self.source_sha,
            "authority":{
                "read_only":True,"delete_allowed":False,
                "scientific_authority_granted":False,
                "source_mutation_allowed":False,
            },
            "coverage":{
                "cataloged_blob_count":len(objs),"tracked_blob_count":len(objs),
                "generated_self_export_exclusion_count":0,
                "coverage_complete":True,
            },
            "statistics":{"cataloged_bytes":sum(len(v) for v in data.values())},
            "sharding":{"shard_count":1,"shards":[{
                "index":0,"path":shard_path,
                "sha256":sha(shard_bytes),"object_count":len(objs),
                "first_path":objs[0]["path"],"last_path":objs[-1]["path"],
            }]},
        }
        mf=self.idx/"assets/hrain-full-memory/manifest.json"
        mf.write_text(json.dumps(self.manifest,sort_keys=True),encoding="utf-8")
        self.git(self.idx,"init","-q")
        self.git(self.idx,"config","user.name","fixture")
        self.git(self.idx,"config","user.email","fixture@example.invalid")
        self.git(self.idx,"add",".")
        self.git(self.idx,"commit","-qm","pinned catalog")

    @staticmethod
    def git(root,*argv):
        return subprocess.check_output(["git","-C",str(root),*argv],text=True)

    def write_index(self):
        mf=self.idx/"assets/hrain-full-memory/manifest.json"
        mf.write_text(json.dumps(self.manifest,sort_keys=True),encoding="utf-8")

    def test_shard_source_validation_dedup_and_protected_exclusion(self):
        receipt, docs=audit_catalog(self.idx,self.src)
        self.assertEqual(receipt["catalog_files"],6)
        self.assertEqual(receipt["manifest_shards_verified"],1)
        self.assertEqual(receipt["hash_verified_parsed_text_files"],3)
        self.assertEqual(len(docs),2)
        self.assertEqual(receipt["excluded_objects_by_reason"]["INVALID_UTF8_OR_JSON"],1)
        self.assertEqual(receipt["excluded_objects_by_reason"]["PROTECTED_OR_GENERATED"],1)
        self.assertEqual(receipt["excluded_objects_by_reason"]["NON_TEXT_EXTENSION"],1)
        self.assertEqual(receipt["hash_verified_unique_candidate_text_bytes"],
                         sum(len((self.src/p).read_bytes()) for p in ("data/rowan/a.json","data/rowan/b.json")))
        self.assertEqual(receipt["remaining_gap_bytes"],
                         TARGET_BYTES-receipt["hash_verified_unique_candidate_text_bytes"])
        self.assertFalse(receipt["consent_or_training_cleared"])

    def test_bad_metadata_hash_fails_closed(self):
        self.manifest["sharding"]["shards"][0]["sha256"]="0"*64
        self.write_index()
        with self.assertRaisesRegex(Hold,"SHARD_SHA_MISMATCH"):
            audit_catalog(self.idx,self.src)

    def test_bad_source_bytes_fail_closed(self):
        (self.src/"data/rowan/a.json").write_bytes(b'{"tampered":true}')
        with self.assertRaisesRegex(Hold,"SOURCE_SHA_OR_SIZE_MISMATCH"):
            audit_catalog(self.idx,self.src)

    def test_wrong_git_snapshot_fails_closed(self):
        self.git(self.src,"commit","--allow-empty","-qm","moved source HEAD")
        with self.assertRaisesRegex(Hold,"SOURCE_SNAPSHOT_COMMIT_DRIFT"):
            audit_catalog(self.idx,self.src)

    def test_fts_retrieval_and_explicit_second_hop(self):
        report,docs=audit_catalog(self.idx,self.src)
        db=Path(self.temp.name)/"index.sqlite"
        rec=build_index(db,self.src,docs,focus="rowan",max_index_bytes=4096)
        self.assertEqual(rec["indexed_docs"],2)
        self.assertEqual(rec["sqlite_integrity"],"ok")
        result=search_index(db,"alpha")
        self.assertEqual(result[0]["path"],"data/rowan/a.json")
        self.assertEqual(result[0]["source_sha256"],sha((self.src/"data/rowan/a.json").read_bytes()))
        two=multi_hop(db,"alpha")
        self.assertEqual(two["status"],"EXPLICIT_REFERENCE_SECOND_HOP_FOUND")
        self.assertEqual(two["second"][0]["path"],"data/rowan/b.json")
        self.assertEqual(multi_hop(db,"nonsense-unseen-999")["status"],"NO_SUPPORTED_FIRST_HOP")
        self.assertFalse(rec["model_weights_changed"])

    def test_index_not_written_under_source_tree(self):
        _,docs=audit_catalog(self.idx,self.src)
        with self.assertRaisesRegex(Hold,"INDEX_MUST_BE_NEW_OUTSIDE_SOURCE"):
            build_index(self.src/"index.sqlite",self.src,docs)

    def test_unicode_chunk_boundaries_roundtrip(self):
        text="a"*4095+"€"+"🏛"*300+"good"
        chunks=_chunks(text)
        self.assertEqual("".join(x[2] for x in chunks),text)
        self.assertTrue(all(len(x[2].encode("utf-8"))<=4096 for x in chunks))
        self.assertTrue(all(end-begin==len(chunk.encode("utf-8")) for begin,end,chunk in chunks))

    def test_no_source_mutation(self):
        _,docs=audit_catalog(self.idx,self.src)
        db=Path(self.temp.name)/"index.sqlite"
        build_index(db,self.src,docs,focus="rowan",max_index_bytes=4096)
        self.assertEqual(self.git(self.src,"status","--porcelain"),"")


if __name__=="__main__":
    unittest.main()
