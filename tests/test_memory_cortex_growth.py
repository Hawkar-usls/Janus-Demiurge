import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from janus_model import memory_cortex_growth as g


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "state"
        self.source = self.home / "source"
        self.source.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.put("data/baseline.json", '{"schema":"baseline","value":7}')
        self.commit()
        self.state = g.new_state()
        raw = (self.source / "data/baseline.json").read_bytes()
        g.add_text(self.root, self.state, raw, {"repository": g.REGISTRY,
                   "commit": g.git_head(self.source), "path": "data/baseline.json"})
        baseline_blob = next(g.git_files(self.source))[1]
        self.state["seen_registry_blobs"][baseline_blob] = "BASELINE"
        g.publish(self.root, self.state, "BASELINE")
        self.save()
        self.policy = {"publish_new_bytes": 4194304, "publish_new_documents": 2,
                       "max_registry_documents_per_scan": 512, "max_primary_fetches_per_scan": 8}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.source), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def put(self, name, body):
        path = self.source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def save(self):
        g.write_json(self.root / "STATE.json", g.sealed(self.state))

    def scan(self, fetch=lambda u: self.fail("unexpected network fetch")):
        return g.collect(self.root, self.source, None, self.policy, fetch=fetch)

    def test_priority_error_memory_once_and_exact_bytes(self):
        import hashlib
        def seal(x):
            return {**x, "sha256": hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
        prior=seal({"schema":"h38n3.error_memory.v1","production":False,"errors":[1]})
        memory=seal({"schema":"h38n4.error_memory.v1","production":False,"previous":prior})
        self.put(g.ERROR_MEMORY_PATH,json.dumps(memory))
        self.commit()
        raw=(self.source/g.ERROR_MEMORY_PATH).read_bytes()
        with patch.object(g,"ERROR_MEMORY_SOURCE_SHA",g.digest(raw)), patch.object(g,"ERROR_MEMORY_SEAL",memory["sha256"]):
            first=self.scan()
            self.assertEqual(first["generation"],1)
            self.assertTrue(first["error_memory"]["active"])
            self.assertEqual(g.read_object(self.root,g.digest(raw),len(raw)),raw)
            second=self.scan()
            self.assertEqual(second["generation"],1)
            self.assertFalse(second["error_memory"]["publish_requested"])

    def test_priority_error_memory_wrong_hash_never_publishes(self):
        self.put(g.ERROR_MEMORY_PATH,'{"production":false}')
        self.commit()
        with self.assertRaisesRegex(g.Hold,"ERROR_MEMORY_SOURCE_PIN_MISMATCH"):
            self.scan()
        self.assertEqual(g.load_state(self.root)["generation"],0)

    def test_unchanged_run_is_noop_and_does_not_rebuild_or_read_old_text(self):
        self.scan()
        before = (self.root / "STATE.json").read_bytes()
        with patch.object(g, "raw_from_tree", side_effect=AssertionError("old source reread")), \
                patch.object(g, "build_active_index", side_effect=AssertionError("index rebuilt")):
            r = self.scan()
        self.assertEqual(r["status"], "NO_NEW_INFORMATION")
        self.assertEqual((self.root / "STATE.json").read_bytes(), before)
        self.assertEqual(len(list((self.root / "generations").glob("*.json"))), 1)

    def test_pending_survives_restart_and_publishes_once_at_document_threshold(self):
        self.put("data/one.json", '{"schema":"new-one","answer":11}')
        self.commit()
        first = self.scan()
        self.assertEqual(first["generation"], 0)
        self.assertEqual(first["pending_documents"], 1)
        self.assertEqual(len(g.load_state(self.root)["pending"]), 1)
        self.put("data/two.json", '{"schema":"new-two","answer":22}')
        self.commit()
        second = self.scan()
        self.assertEqual(second["status"], "GENERATION_PUBLISHED")
        self.assertEqual(second["generation"], 1)
        self.assertEqual(second["active_documents"], 3)
        self.assertEqual(second["pending_documents"], 0)
        third = self.scan()
        self.assertEqual(third["status"], "NO_NEW_INFORMATION")
        self.assertEqual(third["generation"], 1)
        manifest = g.checked(json.loads((self.root / "generations/000001.json").read_text()))
        previous = g.checked(json.loads((self.root / "generations/000000.json").read_text()))
        self.assertEqual(manifest["parent_manifest_sha256"], previous["receipt_sha256"])

    def test_byte_threshold_can_publish_without_document_threshold(self):
        self.policy["publish_new_bytes"] = 8
        self.put("data/one.json", '{"actual":"new information"}')
        self.commit()
        self.assertEqual(self.scan()["generation"], 1)

    def test_same_bytes_new_path_or_beetle_id_are_not_new_capacity(self):
        self.put("data/copy.json", (self.source / "data/baseline.json").read_text())
        self.commit()
        r = self.scan()
        self.assertEqual(r["pending_unique_source_bytes"], 0)
        state = g.load_state(self.root)
        self.assertFalse(g.add_text(self.root, state,
            (self.source / "data/baseline.json").read_bytes(), {"primary_id": "other"}))
        self.assertEqual(len(state["records"]), 1)

    def test_source_worktree_tampering_is_rejected_by_git_blob_replay(self):
        self.put("data/new.json", '{"value":111}')
        self.commit()
        self.put("data/new.json", '{"value":222}')
        with self.assertRaisesRegex(g.Hold, "GIT_BLOB"):
            self.scan()

    def test_sealed_private_invalid_and_large_inputs_are_excluded(self):
        self.put("data/sealed_answers.json", '{"value":"hidden"}')
        self.put("data/invalid.json", '{broken')
        self.put("data/large.txt", "x" * (g.MAX_DOC + 1))
        self.put("data/private.json", '{"private":true}')
        self.commit()
        r = self.scan()
        self.assertEqual(r["pending_documents"], 0)
        self.assertEqual(r["active_documents"], 1)

    def test_corrupted_cas_never_becomes_a_published_generation(self):
        self.put("data/new.json", '{"value":33}')
        self.commit()
        self.scan()
        state = g.load_state(self.root)
        sha = state["pending"][0]
        g.object_path(self.root, sha).write_bytes(b"forged")
        self.put("data/other.json", '{"value":44}')
        self.commit()
        with self.assertRaisesRegex(g.Hold, "CONTENT_HASH"):
            self.scan()
        self.assertEqual(json.loads((self.root / "CURRENT.json").read_text())["generation"], 0)

    def test_tampered_state_is_not_silently_reset(self):
        path = self.root / "STATE.json"
        data = json.loads(path.read_text())
        data["active"] = []
        g.write_json(path, data)
        with self.assertRaisesRegex(g.Hold, "HASH_MISMATCH"):
            self.scan()

    def test_pointer_and_manifest_cannot_silently_drift(self):
        path = self.root / "CURRENT.json"
        data = json.loads(path.read_text())
        data["generation"] = 8
        g.write_json(path, g.sealed(data))
        with self.assertRaisesRegex(g.Hold, "MANIFEST_DRIFT"):
            g.load_state(self.root)

    def test_query_has_exact_provenance_and_abstains(self):
        result = g.query(self.root, "baseline")
        self.assertEqual(result["status"], "VERIFIED_SOURCE_POINTERS_ONLY")
        cite = result["citations"][0]
        self.assertEqual(cite["sha256"], g.digest((self.source / "data/baseline.json").read_bytes()))
        self.assertEqual(cite["origin"]["repository"], g.REGISTRY)
        self.assertEqual(g.query(self.root, "zzzznonexistent")["status"], "NO_MATCH")
        self.assertFalse(result["model_inference_executed"])

    def test_uninitialized_query_is_explicit(self):
        self.assertEqual(g.query(self.home / "empty", "memory")["status"], "UNINITIALIZED")

    def test_only_provider_identifiers_can_become_fetch_urls(self):
        self.assertIsNone(g.canonical_lead("https://127.0.0.1/records/3"))
        self.assertIsNone(g.canonical_lead("https://zenodo.org.evil.test/records/3"))
        self.assertIsNone(g.canonical_lead("https://user@zenodo.org/records/3"))
        self.assertIsNone(g.canonical_lead("https://zenodo.org:invalid/records/3"))
        self.assertIsNone(g.canonical_lead("https://zenodo.org/records/3?url=https://evil.test"))
        self.assertEqual(g.canonical_lead("https://arxiv.org/abs/2601.12345v2")[0], "arxiv:2601.12345v2")

    def seed_lead(self, ident="zenodo:123"):
        self.state["beetle_queue"][ident] = {"url": "https://zenodo.org/api/records/123",
            "candidate_id": "candidate1", "beetle_commit": "b" * 40,
            "beetle_path": "data/beetle-state/candidates.parts/part-000001.jsonl",
            "discovered_at": "2026-11-23", "attempts": 0, "retry_at": 0}

    def test_primary_is_independently_fetched_then_never_refetched(self):
        self.seed_lead()
        raw = json.dumps({"id": 123, "metadata": {"title": "A primary title",
            "description": "Measured source abstract describing reproducible retrieval and its limitations."}}).encode()
        fetches = []
        fetch = lambda url: fetches.append(url) or raw
        first = g.consume_beetle(self.root, self.state, fetch=fetch)
        second = g.consume_beetle(self.root, self.state, fetch=fetch)
        self.assertEqual(len(fetches), 1)
        self.assertEqual(first["new_primary_texts"], 1)
        self.assertEqual(second["primary_fetches"], 0)
        record = self.state["records"][self.state["pending"][0]]
        self.assertEqual(record["origin"]["provider_sha256"], g.digest(raw))
        self.assertIn("NOT_FULL_PAPER", record["origin"]["kind"])

    def test_provider_id_mismatch_rejected_without_capacity_gain(self):
        self.seed_lead()
        raw = b'{"id":456,"metadata":{"title":"wrong","description":"this must never enter the source corpus as record 123"}}'
        result = g.consume_beetle(self.root, self.state, fetch=lambda url: raw)
        self.assertEqual(result["new_primary_texts"], 0)
        self.assertEqual(self.state["pending"], [])
        self.assertEqual(self.state["beetle_done"]["zenodo:123"]["status"], "REJECTED_PRIMARY_RECORD")

    def test_transient_fetch_failure_backoff_does_not_mark_success(self):
        self.seed_lead()
        def fail(url):
            raise urllib.error.URLError("unavailable")
        g.consume_beetle(self.root, self.state, fetch=fail, now=100)
        self.assertNotIn("zenodo:123", self.state["beetle_done"])
        result = g.consume_beetle(self.root, self.state, fetch=lambda u: self.fail("early retry"), now=200)
        self.assertEqual(result["primary_fetches"], 0)

    def test_beetle_cursor_continues_new_lines_and_deduplicates_provider(self):
        root = self.source / "data/beetle-state/candidates.parts"
        root.mkdir(parents=True)
        part = root / "part-000001.jsonl"
        row = {"schema": "janus.universal_beetle.candidate.v1", "candidate_id": "one",
               "url": "https://zenodo.org/records/123", "discovered_at": "2026-11-23"}
        part.write_text(json.dumps(row) + "\n")
        self.commit()
        first = g.read_beetle_leads(self.state, self.source)
        second = g.read_beetle_leads(self.state, self.source)
        self.assertEqual((first["lines_consumed"], second["lines_consumed"]), (1, 0))
        self.assertEqual(len(self.state["beetle_queue"]), 1)
        with part.open("a") as f:
            f.write(json.dumps({**row, "candidate_id": "two"}) + "\n")
        self.commit()
        third = g.read_beetle_leads(self.state, self.source)
        self.assertEqual(third["lines_consumed"], 1)
        self.assertEqual(len(self.state["beetle_queue"]), 1)
        part.write_text("{}\n")
        with self.assertRaisesRegex(g.Hold, "TRUNCATED"):
            g.read_beetle_leads(self.state, self.source)

    def test_arxiv_xml_id_and_entity_boundary(self):
        raw = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2601.12345v2</id><title>A study</title><summary>An original abstract concerning memory retrieval with stated controls and limitations.</summary></entry></feed>'
        self.assertIn(b"original abstract", g.primary_text("arxiv:2601.12345", raw))
        with self.assertRaisesRegex(g.Hold, "ID_MISMATCH"):
            g.primary_text("arxiv:2601.99999", raw)
        with self.assertRaisesRegex(g.Hold, "ENTITIES"):
            g.primary_text("arxiv:2601.12345", b'<!DOCTYPE x>' + raw)

    def test_recent_beetle_discovery_is_not_starved_by_old_backlog(self):
        base = self.source / "data/beetle-state/candidates.parts"
        base.mkdir(parents=True)
        part = base / "part-000002.jsonl"
        rows = []
        for i in range(1800):
            rows.append({"schema": "janus.universal_beetle.candidate.v1", "candidate_id": str(i),
                "url": f"https://zenodo.org/records/{10000+i}", "discovered_at": "2026-01-01",
                "summary": "x" * 200})
        rows.append({"schema": "janus.universal_beetle.candidate.v1", "candidate_id": "fresh",
            "url": "https://zenodo.org/records/99999", "discovered_at": "2026-11-23",
            "direction_id": "memory_cortex_incremental_sources::FORWARD"})
        part.write_text(''.join(json.dumps(x) + '\n' for x in rows))
        self.commit()
        for i in range(4096):
            self.state["beetle_queue"][f'zenodo:{i}'] = {"discovered_at": "2025-01-01", "retry_at": 999999999999}
        # More than one bounded hot read may be needed, but no archive slot is
        # required and none of the 4096 old queued IDs is discarded.
        for _ in range(4):
            g.read_beetle_leads(self.state, self.source)
        self.assertEqual(self.state["beetle_queue"]["zenodo:99999"]["priority"], 2)
        self.assertIn('zenodo:0', self.state["beetle_queue"])
        self.assertNotIn(str(part.relative_to(self.source)), self.state["beetle_offsets"])
        fetched = []
        raw = b'{"id":99999,"metadata":{"title":"Fresh","description":"A newly discovered primary abstract with genuine research content."}}'
        g.consume_beetle(self.root, self.state, max_fetches=1,
                         fetch=lambda u: fetched.append(u) or raw, now=1)
        self.assertEqual(fetched, ['https://zenodo.org/api/records/99999'])

    def test_symlink_source_object_refused(self):
        sha = self.state["active"][0]
        path = g.object_path(self.root, sha)
        path.unlink()
        path.symlink_to(self.source / "data/baseline.json")
        with self.assertRaisesRegex(g.Hold, "SYMLINK"):
            g.query(self.root, "baseline")

    def test_malformed_provider_shapes_do_not_crash_whole_intake(self):
        for raw in (b'[]', b'{"id":123,"metadata":null}',
                    b'{"id":123,"metadata":{"title":[],"description":42}}'):
            state = copy.deepcopy(self.state)
            state["beetle_queue"]["zenodo:123"] = {"url": "https://zenodo.org/api/records/123",
                "candidate_id": "bad", "beetle_commit": "b" * 40,
                "beetle_path": "data/beetle-state/candidates.parts/part-000001.jsonl",
                "discovered_at": "2026-11-23", "attempts": 0, "retry_at": 0}
            result = g.consume_beetle(self.root, state, fetch=lambda u: raw)
            self.assertEqual(result["fetch_errors"], 1)
            self.assertEqual(result["new_primary_texts"], 0)

    def test_crossing_byte_goal_does_not_require_an_exact_document_sum(self):
        used = sum(v["size"] for v in self.state["records"].values())
        raw = b'A genuinely different source document extending past the byte goal.'
        with patch.object(g, 'TARGET', used + 10), patch.object(g, 'MAX_CORPUS_BYTES', used + 100):
            self.assertTrue(g.add_text(self.root, self.state, raw, {"kind": "TEST_SOURCE"}))
            total = sum(v["size"] for v in self.state["records"].values())
            self.assertGreater(total, g.TARGET)
            self.assertLessEqual(total, g.MAX_CORPUS_BYTES)

    def test_capacity_pressure_retains_provider_for_later_and_is_not_bad_source(self):
        self.seed_lead()
        used = sum(v["size"] for v in self.state["records"].values())
        raw = b'{"id":123,"metadata":{"title":"Valid","description":"A valid primary abstract that remains queued during source storage pressure."}}'
        with patch.object(g, 'MAX_CORPUS_BYTES', used):
            result = g.consume_beetle(self.root, self.state, fetch=lambda u: raw, now=1)
        self.assertTrue(result["capacity_admission_paused"])
        self.assertIn('zenodo:123', self.state['beetle_queue'])
        self.assertNotIn('zenodo:123', self.state['beetle_done'])
        self.assertEqual(result['fetch_errors'], 0)

    def test_registry_capacity_pressure_does_not_lose_pending_verified_text(self):
        self.put('data/a_new.json', '{"value":"first acceptable new source"}')
        self.put('data/b_new.json', '{"value":"second acceptable source that does not fit"}')
        self.commit()
        used = sum(v["size"] for v in self.state["records"].values())
        first_size = (self.source / 'data/a_new.json').stat().st_size
        with patch.object(g, 'MAX_CORPUS_BYTES', used + first_size):
            result = self.scan()
        self.assertTrue(result['capacity_admission_paused'])
        self.assertEqual(result['status'], 'GENERATION_PUBLISHED')
        self.assertEqual(result['active_documents'], 2)
        self.assertEqual(result['pending_documents'], 0)
        self.assertEqual(g.load_state(self.root)['generation'], 1)

    def test_small_health_receipt_explains_errors_without_full_state_download(self):
        self.seed_lead()
        def fail(url):
            raise urllib.error.URLError('offline')
        g.consume_beetle(self.root, self.state, fetch=fail, now=1)
        report = g.intake_health(self.state)
        self.assertEqual(report['retrying_provider_ids'], 1)
        self.assertEqual(report['failure_counts'], {'URLError': 1})
        self.assertLess(len(json.dumps(report)), 4096)


if __name__ == "__main__":
    unittest.main()
