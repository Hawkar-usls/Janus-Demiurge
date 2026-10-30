"""Portable native training corpus bytes must match recorded SHA on Windows and Linux."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from janus_model import corpus, keymaster


def digest(data):
    return hashlib.sha256(data).hexdigest()


class PortableNativeCorpusTests(unittest.TestCase):
    def test_keymaster_pack_and_training_sha_match_raw_disk_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "config.json"
            config.write_text(json.dumps({"schema":"test", "max_bytes_per_contributor":120000}))
            contributors = [
                {"id":f"K{i}", "repository":f"example/owner{i}",
                 "cohort":"CORE_5" if i<5 else "EXTENDED_3"}
                for i in range(8)]
            def stub(c, max_bytes, temporary_root):
                payload = ("JANUS: проверка\n" * 20) + c["id"] + "\n"
                rec = {"id":c["id"],"repository":c["repository"],
                       "cohort":c["cohort"],"head_sha":"a"*40,
                       "configured_ref":"main","ref":"main","ref_strategy":"PINNED",
                       "provenance":"SYNTHETIC_TEST", "contributed_bytes":len(payload.encode()),
                       "contribution_sha256":digest(payload.encode()),
                       "training_pack_sha256":digest(payload.encode())}
                return rec, payload
            out = root / "keymaster"
            with patch.object(keymaster, "_validate_config",
                              return_value=(contributors,8)), patch.object(
                                  keymaster, "collect_repository", side_effect=stub):
                manifest = keymaster.collect(config, out)
            raw = (out / "training.txt").read_bytes()
            self.assertEqual(digest(raw), manifest["training_pack_sha256"])
            self.assertEqual(len(raw), manifest["training_bytes"])
            self.assertNotIn(b"\r\n", raw)
            for c in contributors:
                part = (out/"packs"/(c["id"]+".txt")).read_bytes()
                self.assertEqual(part.decode("utf-8").encode("utf-8"),part)
                self.assertNotIn(b"\r\n",part)

    def test_corpus_manifest_byte_counts_portable(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            registry=root/"registry"
            registry.mkdir()
            files=[]
            for is_holdout, name in ((False,"train.txt"),(True,"holdout.txt")):
                for i in range(200):
                    text=(("HOLDOUT\n" if is_holdout else "TRAINING\n")*8000
                          + f"FINAL-{i}\n")
                    payload=text.encode("utf-8")
                    if (int(digest(payload)[:8],16)%10==0)==is_holdout:
                        break
                else:
                    self.fail("Could not generate deterministic split")
                path=registry/name
                path.write_bytes(payload)
                files.append(path)
            extra=("eight contributors train only\n"*100)
            train_path=root/"pack.txt"
            train_path.write_bytes(extra.encode())
            manifest={
                "schema":"janus.keymaster.learning_contribution_manifest.v2",
                "status":"READY_8_OF_8","contributor_count":8,
                "required_contributor_count":8,
                "training_only":True,
                "adaptive_holdout_inclusion":False,
                "frozen_anchor_inclusion":False,
                "training_material_is_truth":False,
                "contribution_grants_authority":False,
                "source_execution":False,
                "cross_repository_write":False,
                "authority_delta":0,
                "training_pack_sha256":digest(extra.encode()),
                "training_bytes":len(extra.encode()),
                "contribution_sha256":"e"*64,
                "contributors":[
                    {"id":f"K{i}","repository":f"example/owner{i}",
                     "cohort":"CORE_5" if i<5 else "EXTENDED_3",
                     "contributed_bytes":100,"provenance":"TEST",
                     "ref":"main","head_sha":"a"*40,
                     "contribution_sha256":"b"*64,
                     "training_pack_sha256":"c"*64}
                    for i in range(8)],
            }
            manifest_path=root/"pack-manifest.json"
            manifest_path.write_text(json.dumps(manifest),encoding="utf-8")
            out=root/"corpus"
            with patch.object(corpus,"iter_source_files",return_value=files),patch.object(
                corpus,"_git_head",return_value="d"*40),patch.object(
                corpus,"DEFAULT_FRONTIER_MEMORY_TRAINING",root/"absent.txt"),patch.object(
                corpus,"DEFAULT_FRONTIER_MEMORY_MANIFEST",root/"absent.json"):
                result=corpus.build_corpus(
                    registry,out,max_train_bytes=200000,max_holdout_bytes=100000,
                    keymaster_training_path=train_path,keymaster_manifest_path=manifest_path)
            for fname,manifest_key in (("train.txt","train_bytes"),
                                       ("holdout.txt","holdout_bytes")):
                b=(out/fname).read_bytes()
                self.assertEqual(len(b),result[manifest_key])
                self.assertEqual(b,(out/fname).read_text(encoding="utf-8").encode("utf-8"))
                self.assertNotIn(b"\r\n",b)
            self.assertEqual((out/"registry_train.txt").read_bytes(),
                             (out/"registry_train.txt").read_text(encoding="utf-8").encode("utf-8"))
            self.assertEqual(result["keymaster_training_pack_sha256"],
                             digest(train_path.read_bytes()))


if __name__=="__main__":
    unittest.main()
