import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import janus_essence_github_scout as scout


def sample(name, license="MIT", stars=30):
    return {
        "full_name": name, "license": {"spdx_id": license},
        "stargazers_count": stars, "private": False, "archived": False,
        "disabled": False,
    }


class GitHubScoutTests(unittest.TestCase):
    def test_metadata_only_license_and_alias_dedup(self):
        seen = []
        def search(q):
            seen.append(q)
            return {"items": [sample("example/tiny-gpt"),
                              sample("example/restrict", "NOASSERTION"),
                              sample("example/too-secret", "MIT") | {"private": True},
                              sample("example/tiny-gpt")]}
        r = scout.curate(search)
        self.assertEqual(seen, list(scout.QUERIES))
        self.assertEqual(len(r["repositories"]), 2)
        self.assertTrue(scout.verify(r))
        self.assertEqual(r["repositories"][0]["repository_level_license_gate"],
                         "METADATA_MATCH_REVIEW_REQUIRED")
        self.assertEqual(r["repositories"][1]["repository_level_license_gate"],
                         "LICENSE_HOLD")
        self.assertEqual(len(r["repositories"][0]["discovery_queries"]), len(scout.QUERIES))
        self.assertFalse(r["code_downloaded"])
        self.assertFalse(r["automatic_copy_or_install"])

    def test_reject_malformed_search(self):
        with self.assertRaisesRegex(ValueError, "MALFORMED_GITHUB_RESPONSE"):
            scout.curate(lambda q: {"message": "temporary rate limit"})

    def test_reject_source_execution_claim(self):
        r = scout.curate(lambda q: {"items": [sample("safe/project")]})
        r["repositories"][0]["source_executed"] = True
        r["sha256"] = hashlib.sha256(scout.canonical(
            {k:v for k,v in r.items() if k != "sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_CODE_REUSE"):
            scout.verify(r)

    def test_only_fixed_queries(self):
        with self.assertRaisesRegex(ValueError, "QUERY_OUTSIDE_CURATED_SET"):
            scout.read_search("http://example.com/malicious")
