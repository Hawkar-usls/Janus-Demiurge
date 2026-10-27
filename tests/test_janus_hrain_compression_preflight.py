"""JANUS HRAiN v89 cluster compression must not run on owner's private graph."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE=pathlib.Path(__file__).resolve().parents[1]/"tools/janus_hrain_compression_preflight.py"
spec=importlib.util.spec_from_file_location("cluster_guard",MODULE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class LegacyHrainCompressionGate(unittest.TestCase):
    def test_original_meta_member_links_would_be_erased(self):
        nodes={
            "a":{"data":{"role":"same"}},
            "b":{"data":{"role":"same"}},
            "c":{"data":{"role":"other"}}}
        edges={"a->b":{"weight":1},"c->a":{"weight":5},"b->c":{"weight":8}}
        copy=json.dumps({"nodes":nodes,"edges":edges},sort_keys=True)
        v=m.assess(nodes,edges)
        self.assertEqual(v["clustersDetected"],1)
        self.assertEqual(v["memberNodesAtRisk"],2)
        self.assertEqual(v["existingEdgesAtRisk"],3)
        self.assertEqual(v["newMetaMemberEdgesDeletedByOriginalRoutine"],4)
        self.assertEqual(v["status"],"BLOCK_LEGACY_DESTRUCTIVE_COMPRESSION")
        self.assertFalse(v["productionUseAuthorized"])
        self.assertEqual(copy,json.dumps({"nodes":nodes,"edges":edges},sort_keys=True))

    def test_no_candidates_is_still_not_permission_to_write(self):
        v=m.assess({"a":{"data":{"role":"x"}},"b":{"data":{"role":"y"}}},{})
        self.assertEqual(v["clustersDetected"],0)
        self.assertFalse(v["productionUseAuthorized"])
        self.assertEqual(v["status"],"NO_CLUSTER_LOSS_PREDICTED_FOR_THIS_SNAPSHOT")

    def test_source_integrity_and_confidentiality(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)
            logs=root/"raw_logs";logs.mkdir()
            state=logs/"hrain_graph_state.json"
            state.write_text(json.dumps({"nodes":{"privateId":{"data":{"agent_id":"SECRET_LABEL"}}},
                                      "edges":{},"tick":1}),encoding="utf8")
            report=m.run_file(state)
            self.assertIn("inputSha256",report)
            self.assertNotIn("privateId",str(report))
            self.assertNotIn("SECRET_LABEL",str(report))
            self.assertTrue(report["sourceGraphModified"] is False)
            self.assertFalse(report["productionUseAuthorized"])
            with self.assertRaises(ValueError):
                m.run_file(root/"private_secrets.json")

    def test_dangling_ambiguous_and_nonfinite_fail_closed(self):
        nodes={"a":{"data":{"purity":1}},"b":{"data":{"purity":2}}}
        self.assertEqual(m.assess(nodes,{"ghost->a":{}})["alreadyDanglingEdges"],1)
        for edges in ({"a->b->c":{}},{"a":{}}):
            with self.assertRaisesRegex(ValueError,"UNSAFE_EDGE_ID_HOLD"):
                m.assess(nodes,edges)
        with self.assertRaisesRegex(ValueError,"NONFINITE_SIMILARITY_HOLD"):
            m.assess({"a":{"data":{"purity":float("nan")}},
                      "b":{"data":{"purity":1}}},{})
        with self.assertRaisesRegex(ValueError,"PREFLIGHT_SIZE_BOUND_HOLD"):
            m.assess({str(i):{"data":{}} for i in range(1001)},{})

if __name__=="__main__":unittest.main()
