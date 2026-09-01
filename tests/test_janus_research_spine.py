import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from janus_model.extensions import research_spine as rs


class ResearchSpineTests(unittest.TestCase):
    def _write(self, root: Path, rel: str, content: str = "{}\n") -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_bound_spine_is_fundamentum_first_and_non_authoritative(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            topa = base / "TOPA"
            demi = base / "Demi_Head"
            fund = base / "Janus-Fundamentum"
            for root in (topa, demi, fund):
                root.mkdir()

            self._write(topa, "protocols/TOPA_FOUNDATION.json")
            self._write(topa, "data/TOPA-MATHEMATICAL-RESEARCH-MODE-2026-08-24-v1.1.json")
            self._write(
                topa,
                rs.TOPA_ROUTER.as_posix(),
                "print('JANUS_TOPA_EPISTEMIC_ROUTER_V1_3_SELF_TEST=PASS')\n",
            )
            self._write(demi, "README.md", "# Demi Head\n")
            self._write(demi, "PROJECT_STATUS.json")
            self._write(demi, ".janus/PROPERTY_A.json")
            self._write(fund, "README.md", "# Fundamentum\n")
            self._write(fund, "docs/CURRENT_RESEARCH_STATUS.md", "P_VS_NP = OPEN\n")

            with mock.patch.object(rs, "git_head", side_effect=["a" * 40, "b" * 40, "c" * 40]):
                obj = rs.build_research_spine(
                    topa,
                    demi,
                    fund,
                    ["test"],
                    enable_arxiv=False,
                )

            self.assertEqual(obj["status"], "READY_WITH_ARXIV_DEGRADED")
            self.assertEqual(obj["improvement_policy"]["primary_target"], rs.PRIMARY_TARGET)
            self.assertTrue(obj["improvement_policy"]["no_novel_bounded_evidence_means_no_action"])
            self.assertFalse(obj["claim_ceiling"]["topa_output_is_world_truth"])
            self.assertFalse(obj["claim_ceiling"]["arxiv_presence_is_truth"])
            self.assertFalse(obj["claim_ceiling"]["demi_head_property_is_independent_evidence"])
            self.assertEqual(obj["research_spine"]["topa"]["router_self_test"]["status"], "PASS")
            self.assertEqual(obj["research_spine"]["demi_head"]["property_link_count"], 1)
            self.assertEqual(len(obj["context_sha256"]), 64)

    def test_missing_topa_router_blocks_required_spine(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            topa = base / "TOPA"
            demi = base / "Demi_Head"
            fund = base / "Janus-Fundamentum"
            for root in (topa, demi, fund):
                root.mkdir()
            self._write(topa, "protocols/TOPA_FOUNDATION.json")
            self._write(topa, "data/TOPA-MATHEMATICAL-RESEARCH-MODE-2026-08-24-v1.1.json")
            self._write(demi, "README.md")
            self._write(demi, "PROJECT_STATUS.json")
            self._write(fund, "README.md")
            self._write(fund, "docs/CURRENT_RESEARCH_STATUS.md")

            with mock.patch.object(rs, "git_head", side_effect=["a" * 40, "b" * 40, "c" * 40]):
                obj = rs.build_research_spine(topa, demi, fund, ["test"], enable_arxiv=False)
            self.assertEqual(obj["status"], "BLOCKED_REQUIRED_RESEARCH_ORGAN")
            self.assertEqual(obj["research_spine"]["topa"]["router_self_test"]["status"], "BLOCKED")

    def test_arxiv_bounds_are_explicit(self):
        self.assertEqual(rs.ARXIV_ENDPOINT, "https://export.arxiv.org/api/query")
        self.assertLessEqual(len(rs.DEFAULT_ARXIV_QUERIES), 6)
        self.assertIn("CRITICAL_INTEGRITY", rs.CRITICAL_OVERRIDE_CLASSES)


if __name__ == "__main__":
    unittest.main()
