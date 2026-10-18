"""R2 fail-closed GitHub HEAD/byte-audit acquisition, no external requests."""
from __future__ import annotations

from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import base64
from urllib.error import HTTPError

from janus_model.divergent_mind_r1 import FIELD_NAMES
from janus_model.divergent_mind_r1_benchmark import PACK
from janus_model.divergent_mind_r1_source_audit import git_blob_sha1
from janus_model.divergent_mind_r2 import (
    ALLOWED_REPOS, PublicGitHubReader, ReadFailure, capture,
)


def frozen():
    return json.loads(PACK.read_text(encoding="utf-8"))


def native_docs(pack: dict) -> dict[str, bytes]:
    """Synthetic full files shaped like inspected real native JSON.

    Only a test transport mock: these are not falsely described as real blobs.
    """
    docs = {}
    for key in FIELD_NAMES:
        excerpt = deepcopy(pack["sources"][key]["excerpt"])
        if key == "inaihr_state":
            excerpt["candidates"] = [{
                "id": c["id"],
                "status": c["status"],
                "attention_score": c["attention_score"],
                "focus_key": c["focus_key"],
                "authority": c["authority"],
                "meaning": {
                    "lineage": {
                        "source_ids": c["source_ids"],
                        "prior_candidate_id": c["prior_candidate_id"],
                    },
                    "evidence": {
                        "independent_replication_established": c["independent_replication_established"]
                    },
                },
            } for c in excerpt.pop("recent_candidates")]
        elif key == "eye_independence":
            excerpt["pairs"] = excerpt.pop("pairs_sample")
            excerpt.pop("pair_count")
        docs[key] = (json.dumps(excerpt, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    return docs


class MockReader:
    def __init__(self, pack: dict):
        self.ref = frozen()
        self.heads = {repo: next(src["origin"]["commit"] for src in pack["sources"].values()
                                 if src["origin"]["repository"] == repo)
                      for repo in ALLOWED_REPOS}
        self.files = native_docs(pack)
        self.get_blob_count = 0
        self.get_head_count = 0
        self.change_on_second_pass = False
        self.unknown = False
        self.tamper_blob = False

    def get_head(self, repository: str) -> str:
        self.get_head_count += 1
        if self.unknown:
            raise ReadFailure("UNKNOWN_RATE_LIMIT_OR_DENIED")
        if self.change_on_second_pass and self.get_head_count > len(ALLOWED_REPOS):
            if repository == ALLOWED_REPOS[0]:
                return "f" * 40
        return self.heads[repository]

    def get_blob(self, repository: str, commit: str, path: str) -> tuple[bytes, str]:
        self.get_blob_count += 1
        key = next(k for k, (repo, file_path, _) in FIELD_NAMES.items()
                   if repo == repository and file_path == path)
        raw = self.files[key]
        return raw, ("0" * 40 if self.tamper_blob else git_blob_sha1(raw))


class R2ReadOnlyTests(unittest.TestCase):
    def test_frozen_reference_head_drift_is_hold_before_reading(self):
        reader = MockReader(frozen())
        reader.heads["Hawkar-usls/Hrain"] = "0" * 40
        result = capture(reader, policy="require_frozen", reference=frozen())
        self.assertEqual(result["status"], "HOLD_SOURCE_HEAD_DRIFT")
        self.assertEqual(reader.get_blob_count, 0)
        self.assertIsNone(result["packet"])
        self.assertEqual(result["authority_delta"], 0)

    def test_fresh_opt_in_acquires_full_blobs_and_questions(self):
        reader = MockReader(frozen())
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "READ_ONLY_QUESTIONS_READY__NOT_RUNTIME_INTEGRATION")
        self.assertEqual(result["whole_blobs_verified"], 6)
        self.assertTrue(result["origin_path_at_commit_checked_via_github_contents_api"])
        self.assertEqual(reader.get_blob_count, 6)
        self.assertEqual(reader.get_head_count, 6)
        self.assertEqual(len(result["packet"]["questions_by_arm"]["native_baseline"]), 4)
        self.assertEqual(len(result["packet"]["questions_by_arm"]["divergent_r1"]), 4)

    def test_second_head_read_detects_race(self):
        reader = MockReader(frozen())
        reader.change_on_second_pass = True
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "HOLD_SOURCE_HEAD_DRIFT")
        self.assertEqual(result["detail"]["stage"], "DURING_ACQUISITION")
        self.assertIsNone(result["packet"])

    def test_unknown_rate_limit_not_silently_negative(self):
        reader = MockReader(frozen())
        reader.unknown = True
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "UNKNOWN_RATE_LIMIT_OR_DENIED")
        self.assertIsNone(result["packet"])

    def test_byte_hash_mismatch_never_reaches_questions(self):
        reader = MockReader(frozen())
        reader.tamper_blob = True
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "HOLD_BLOB_BYTES_MISMATCH_OR_OVERSIZE")
        self.assertIsNone(result["packet"])

    def test_frozen_same_head_but_wrong_blob_is_hold(self):
        reader = MockReader(frozen())
        result = capture(reader, policy="require_frozen", reference=frozen())
        self.assertEqual(result["status"], "HOLD_FROZEN_BLOB_CHANGED")
        self.assertIsNone(result["packet"])

    def test_unsupported_native_authority_rejected(self):
        reader = MockReader(frozen())
        doc = json.loads(reader.files["hrain_manifest"])
        doc["authority"]["archive_is_world_truth"] = True
        reader.files["hrain_manifest"] = json.dumps(doc).encode("utf-8")
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "HOLD_UNSUPPORTED_NATIVE_STATE_OR_AUTHORITY")

    def test_missing_schema_field_fails_closed(self):
        reader = MockReader(frozen())
        doc = json.loads(reader.files["inaihr_state"])
        doc.pop("registry")
        reader.files["inaihr_state"] = json.dumps(doc).encode("utf-8")
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "HOLD_NATIVE_SCHEMA_CHANGED")

    def test_corrupted_native_json_is_hold(self):
        reader = MockReader(frozen())
        reader.files["eye_independence"] = b"{broken"
        result = capture(reader, policy="read_fresh", reference=frozen())
        self.assertEqual(result["status"], "HOLD_INVALID_NATIVE_JSON")

    def test_question_packet_never_promotes_or_mutates(self):
        result = capture(MockReader(frozen()), policy="read_fresh")
        self.assertFalse(result["scientific_claim_promotion"])
        self.assertFalse(result["source_writeback"])
        self.assertEqual(result["authority_delta"], 0)
        packet = result["packet"]
        self.assertFalse(packet["runtime_organ_packets_sent"])
        self.assertFalse(packet["direct_eye_to_inaihr_bypass"])
        self.assertFalse(packet["effect_authority"])
        self.assertFalse(packet["scientific_claim_promotion"])
        self.assertEqual(packet["authority_delta"], 0)
        for questions in packet["questions_by_arm"].values():
            self.assertTrue(all(x["claim_promotion"] is False and
                                x["effect_authority"] is False for x in questions))

    def test_requires_explicit_frozen_reference_and_known_policy(self):
        with self.assertRaises(ValueError):
            capture(MockReader(frozen()), policy="require_frozen")
        with self.assertRaises(ValueError):
            capture(MockReader(frozen()), policy="commit_everywhere")

    def test_public_api_path_allowlist(self):
        reader = PublicGitHubReader()
        with self.assertRaises(ReadFailure):
            reader.get_head("Hawkar-usls/Unapproved")
        with self.assertRaises(ReadFailure):
            reader.get_blob("Hawkar-usls/Hrain", "0" * 40, ".env")
        with self.assertRaises(ReadFailure):
            reader.get_blob("Hawkar-usls/Hrain", "main", "state/neural-link/HEAD.json")

    def test_read_fresh_does_not_authorize_old_source_values(self):
        reader = MockReader(frozen())
        doc = json.loads(reader.files["inaihr_state"])
        doc["registry"]["source_commit"] = reader.ref["sources"]["hrain_provenance"]["excerpt"]["source_commit"]
        reader.files["inaihr_state"] = json.dumps(doc).encode("utf-8")
        result = capture(reader, policy="read_fresh")
        self.assertEqual(result["status"], "READ_ONLY_QUESTIONS_READY__NOT_RUNTIME_INTEGRATION")
        first_kind = result["packet"]["questions_by_arm"]["divergent_r1"][0]["kind"]
        self.assertEqual(first_kind, "CROSS_ORGAN_PIN_ALIGNMENT")

    def test_public_api_decodes_and_rehashes_whole_bytes(self):
        reader = PublicGitHubReader()
        raw = b'{"real":"whole blob bytes"}\n'
        blob_hash = git_blob_sha1(raw)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://api.github.com/repos/Hawkar-usls/Hrain/contents/file"

            def read(self, limit):
                return json.dumps({"sha": blob_hash, "encoding": "base64",
                                   "content": base64.b64encode(raw).decode()}).encode()

        key = FIELD_NAMES["hrain_head"]
        with patch("janus_model.divergent_mind_r2.urlopen", return_value=Response()):
            decoded, returned_hash = reader.get_blob(key[0], "a" * 40, key[1])
        self.assertEqual(decoded, raw)
        self.assertEqual(returned_hash, blob_hash)

    def test_public_api_propagates_rate_limit_as_unknown(self):
        reader = PublicGitHubReader()
        with patch("janus_model.divergent_mind_r2.urlopen", side_effect=HTTPError(
                "https://api.github.com", 403, "limit", {}, None)):
            with self.assertRaises(ReadFailure) as err:
                reader.get_head("Hawkar-usls/Hrain")
        self.assertEqual(err.exception.kind, "UNKNOWN_RATE_LIMIT_OR_DENIED")


if __name__ == "__main__":
    unittest.main()
