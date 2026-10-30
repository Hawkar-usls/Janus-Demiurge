import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import beetle_runtime_consumer as consumer
from janus_model.extensions import research_spine_v2 as spine
from janus_model.extensions import wikipedia_trunk as wiki


class BeetleRuntimeConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / "inbox"
        self.output = self.root / "runtime"
        self.manifest = self.root / "delivery.json"
        self.entries = []
        self.add_batch(1)

    def write(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(consumer.canonical_bytes(obj) + b"\n")

    def item(self, title="Replay-safe discovery processing", url="https://example.org/research/1"):
        return {"schema": "janus.beetle.repo_memory_item.v2", "target_repository": consumer.REPOSITORY,
                "epistemic_status": "DISCOVERY_INBOX__UNVERIFIED__NO_PROOF_AUTHORITY",
                "candidate_id": "candidate-1", "context_id": "context-1", "direction_id": "provenance::CONTROL",
                "url": url, "title": title, "score": 10}

    def add_batch(self, sequence, items=None):
        batch_id = f"{sequence:020x}"
        packet = {"schema": "janus.beetle.repo_memory_batch.v1", "batch_id": batch_id,
                  "target_repository": consumer.REPOSITORY, "claim_ceiling": consumer.CLAIM_CEILING,
                  "items": items if items is not None else [self.item()]}
        path = self.inbox / "batches" / f"{batch_id}.json"
        self.write(path, packet)
        self.entries.append({"batch_id": batch_id, "sequence": sequence, "sha256": consumer.digest(path.read_bytes())})
        self.write(self.manifest, {"schema": "janus.beetle.delivery_queue.v1", "target_repository": consumer.REPOSITORY,
                                  "next_sequence": len(self.entries) + 1, "entries": self.entries})
        self.write(self.inbox / "ACK.json", {"schema": "janus.beetle.inbox_ack.v1", "target_repository": consumer.REPOSITORY,
                   "status": consumer.INBOX_STATUS, "last_sequence": sequence, "batch_id": batch_id,
                   "sha256": self.entries[-1]["sha256"]})
        return path

    def run_consumer(self, max_batches=16):
        return consumer.consume(self.manifest, self.inbox, self.output, source_commit="a" * 40,
                                consumer_commit="b" * 40, max_batches=max_batches)

    def snapshot(self):
        return {p.relative_to(self.output).as_posix(): p.read_bytes() for p in self.output.rglob("*.json")}

    def test_delivery_alone_never_claims_processing(self):
        self.assertFalse((self.output / "PROCESSING_ACK.json").exists())
        report = self.run_consumer()
        self.assertEqual(report["new_batches"], 1)
        context = consumer.load_context(self.output / "CONTEXT.json")
        self.assertEqual(context["last_processed_sequence"], 1)
        self.assertFalse(context["capabilities"]["is_verified_evidence"])
        self.assertFalse(context["capabilities"]["is_direct_gradient_signal"])

    def test_replay_preserves_all_results_and_receipts_byte_for_byte(self):
        self.run_consumer()
        before = self.snapshot()
        self.assertEqual(self.run_consumer()["new_batches"], 0)
        self.assertEqual(before, self.snapshot())

    def test_bounded_backlog_resumes_in_order(self):
        self.add_batch(2)
        first = self.run_consumer(max_batches=1)
        self.assertEqual((first["last_sequence"], first["remaining_delivered"]), (1, 1))
        self.assertEqual(self.run_consumer()["last_sequence"], 2)

    def test_does_not_process_beyond_delivered_ack(self):
        old_ack = (self.inbox / "ACK.json").read_bytes()
        self.add_batch(2)
        (self.inbox / "ACK.json").write_bytes(old_ack)
        self.assertEqual(self.run_consumer()["last_sequence"], 1)

    def test_corrupt_second_batch_does_not_partially_advance_window(self):
        path = self.add_batch(2)
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "BATCH_HASH"):
            self.run_consumer()
        self.assertEqual(self.snapshot(), {})

    def test_wrong_recipient_or_claim_is_rejected_before_effects(self):
        for field, value in (("target_repository", "Hawkar-usls/Hrain"), ("claim_ceiling", "VERIFIED")):
            with self.subTest(field=field):
                packet = {"schema": "janus.beetle.repo_memory_batch.v1", "batch_id": self.entries[0]["batch_id"],
                          "target_repository": consumer.REPOSITORY, "claim_ceiling": consumer.CLAIM_CEILING, "items": [self.item()]}
                packet[field] = value
                with self.assertRaisesRegex(ValueError, "BATCH_REJECTED"):
                    consumer.triage(packet, self.entries[0], "c" * 64)

    def test_unsafe_metadata_and_nonfinite_scores_are_rejected(self):
        for field, value in (("epistemic_status", "VERIFIED"), ("url", "file:///secrets"),
                             ("url", "https://example.org/" + "x" * 2048),
                             ("candidate_id", "x" * 129), ("score", float("nan"))):
            with self.subTest(field=field):
                item = self.item()
                item[field] = value
                packet = {"schema": "janus.beetle.repo_memory_batch.v1", "batch_id": self.entries[0]["batch_id"],
                          "target_repository": consumer.REPOSITORY, "claim_ceiling": consumer.CLAIM_CEILING, "items": [item]}
                with self.assertRaises(ValueError):
                    consumer.triage(packet, self.entries[0], "c" * 64)

    def test_repeated_source_lenses_do_not_multiply_routes(self):
        self.add_batch(2, items=[self.item(), self.item(), self.item("Another source", "https://example.org/research/2")])
        self.run_consumer()
        context = consumer.load_context(self.output / "CONTEXT.json")
        self.assertEqual(len(context["research_routes"]), 2)
        result = json.loads((self.output / "results" / "00000000000000000002.json").read_text())
        self.assertEqual(result["items_triaged"], 3)
        self.assertEqual(sum(r["disposition"] == "DEFERRED_BY_BOUNDED_WINDOW" for r in result["items"]), 1)

    def test_crash_after_result_is_recovered_without_second_effect(self):
        original = consumer._write
        def crash(path, obj, **kwargs):
            if path.parent.name == "receipts":
                raise OSError("injected interruption")
            return original(path, obj, **kwargs)
        with mock.patch.object(consumer, "_write", side_effect=crash):
            with self.assertRaises(OSError):
                self.run_consumer()
        self.assertFalse((self.output / "PROCESSING_ACK.json").exists())
        result_bytes = (self.output / "results" / "00000000000000000001.json").read_bytes()
        self.run_consumer()
        self.assertEqual(result_bytes, (self.output / "results" / "00000000000000000001.json").read_bytes())
        self.assertEqual(self.run_consumer()["new_batches"], 0)

    def test_crash_after_receipt_before_cursor_reuses_receipt(self):
        original = consumer._write
        def crash(path, obj, **kwargs):
            if path.name == "PROCESSING_ACK.json":
                raise OSError("injected interruption")
            return original(path, obj, **kwargs)
        with mock.patch.object(consumer, "_write", side_effect=crash):
            with self.assertRaises(OSError):
                self.run_consumer()
        receipt = self.output / "receipts" / "00000000000000000001.json"
        receipt_bytes = receipt.read_bytes()
        self.run_consumer()
        self.assertEqual(receipt_bytes, receipt.read_bytes())

    def test_derived_context_is_rebuilt_after_interruption(self):
        self.run_consumer()
        expected = (self.output / "CONTEXT.json").read_bytes()
        (self.output / "CONTEXT.json").unlink()
        self.assertEqual(self.run_consumer()["new_batches"], 0)
        self.assertEqual(expected, (self.output / "CONTEXT.json").read_bytes())

    def test_corrupt_receipt_cannot_skip_processing(self):
        self.run_consumer()
        receipt = self.output / "receipts" / "00000000000000000001.json"
        receipt.write_bytes(receipt.read_bytes().replace(b'"authority_delta":0', b'"authority_delta":1'))
        with self.assertRaisesRegex(ValueError, "SAVED_RESULT"):
            self.run_consumer()

    def test_changed_processor_requires_explicit_migration(self):
        self.run_consumer()
        path = self.output / "PROCESSING_ACK.json"
        cursor = json.loads(path.read_text())
        cursor["processor_sha256"] = "f" * 64
        self.write(path, cursor)
        with self.assertRaisesRegex(ValueError, "PROCESSING_CURSOR"):
            self.run_consumer()

    def test_missing_history_cannot_be_hidden_by_valid_cursor(self):
        self.run_consumer()
        (self.output / "results" / "00000000000000000001.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_consumer()

    def test_context_tamper_or_authority_inflation_is_rejected(self):
        self.run_consumer()
        path = self.output / "CONTEXT.json"
        context = json.loads(path.read_text())
        context["capabilities"]["is_verified_evidence"] = True
        context.pop("context_sha256")
        context["context_sha256"] = consumer.digest(consumer.canonical_bytes(context))
        self.write(path, context)
        with self.assertRaisesRegex(ValueError, "CONTEXT_REJECTED"):
            consumer.load_context(path)

    def test_packet_and_registry_inspiration_both_reach_next_search(self):
        self.run_consumer()
        org_path, wiki_path, synth_path = [self.root / f"{name}.json" for name in ("org", "wiki", "synth")]
        self.write(wiki_path, {"schema": wiki.SCHEMA, "status": "READY"})
        from janus_model.extensions.org_surface import SCHEMA as org_schema
        self.write(org_path, {"schema": org_schema, "status": "READY_PUBLIC_ALL_BOUND_PRIVATE_UNMOUNTED"})
        caps = {key: False for key in ("may_be_used_as_world_truth", "may_be_direct_gradient_signal",
                                      "may_grant_mutation_authority", "may_auto_promote_semantic_candidate")}
        registry_ref = {"source_registry_commit": "d" * 40, "source_records": [{"path": "data/recovery.json", "sha256": "e" * 64}]}
        self.write(synth_path, {"schema": "janus.semantic_synthesis_context.v1", "capabilities": caps,
                   "candidate_context": [registry_ref], "research_route_seeds": ["Preserved lineage recovery"],
                   "source": {"candidate_count_selected": 1}})
        base = {"schema": "janus.research_spine.v1", "status": "READY", "research_spine": {}, "claim_ceiling": {}, "laws": []}
        with mock.patch.object(spine.base, "build_research_spine", return_value=copy.deepcopy(base)):
            research = spine.build_research_spine_v2(self.root, self.root, self.root, org_path, wiki_path, [],
                semantic_synthesis_path=synth_path, beetle_context_path=self.output / "CONTEXT.json", enable_arxiv=False)
        topics = wiki.derive_topics(None, research, max_topics=6)
        self.assertIn("Preserved lineage recovery", topics)
        self.assertIn("Replay safe discovery processing", topics)
        self.assertEqual(research["research_spine"]["semantic_synthesis"]["candidate_context"][0], registry_ref)
        self.assertEqual(research["research_spine"]["beetle"]["research_routes"][0]["input_sha256"], self.entries[0]["sha256"])
        self.assertFalse(research["claim_ceiling"]["beetle_triage_is_model_learning"])


if __name__ == "__main__":
    unittest.main()
