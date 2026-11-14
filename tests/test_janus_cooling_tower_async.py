"""Offline adversarial checks for the cooling tower; no GitHub access needed."""
import asyncio
from pathlib import Path
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import janus_cooling_tower_async as tower
from janus_cooling_tower_async import circulation, check_one, get_json


class CoolingTowerTests(unittest.TestCase):
    def test_one_crashed_organ_does_not_take_down_others(self):
        visited = []
        async def probe(organ):
            visited.append(organ)
            if organ == ("dead", None):
                raise RuntimeError("module crashed")
            return {"health": "PASS", "repo": organ[0]}
        organs = [("alive_a", None), ("dead", None), ("alive_b", None)]
        runs = asyncio.run(circulation(organs, probe, rounds=2, concurrency=3))
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertEqual(run["passed"], 2)
            self.assertEqual(run["unknown"], 1)
            self.assertEqual(run["failed"], 0)
            self.assertTrue(run["records"][1]["isolated"])
        self.assertEqual(visited.count(("alive_b", None)), 2)

    def test_bounded_parallelism_and_two_cycles(self):
        active = 0
        peak = 0
        async def probe(organ):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return {"health": "PASS"}
        runs = asyncio.run(circulation(list(range(10)), probe, concurrency=3))
        self.assertLessEqual(peak, 3)
        self.assertEqual([x["passed"] for x in runs], [10, 10])

    def test_reject_unbounded_or_duplicated_requests(self):
        async def probe(organ):
            return {"health": "PASS"}
        with self.assertRaises(ValueError):
            asyncio.run(circulation([1], probe, rounds=3))
        with self.assertRaises(ValueError):
            asyncio.run(circulation([1, 1], probe))
        with self.assertRaises(ValueError):
            asyncio.run(circulation(list(range(101)), probe))
        with self.assertRaises(ValueError):
            asyncio.run(circulation([1], probe, concurrency=99))

    def test_malformed_reply_is_isolated(self):
        async def probe(organ):
            return {"health": "FULLY_AUTONOMOUS"}
        runs = asyncio.run(circulation([("bad", None)], probe, rounds=1))
        self.assertEqual(runs[0]["unknown"], 1)
        self.assertEqual(runs[0]["records"][0]["error"], "ValueError")

    def test_no_external_repo_or_injected_workflow_path(self):
        with self.assertRaises(ValueError):
            get_json("/repos/attacker/anything/actions/runs")
        with self.assertRaises(ValueError):
            check_one("../../etc/passwd", "")
        with self.assertRaises(ValueError):
            check_one("Janus-Demiurge", "", "../evil.yml")

    def test_research_training_status_does_not_clear_or_poison_critical_gate(self):
        names=["Janus-Demiurge"]+["research-repo-"+str(i) for i in range(30)]
        async def fake_circulation(organs,probe):
            rows=[{"organ":organ,
                   "health":"FAIL" if organ==("Janus-Demiurge","essence-v19-gradirnya.yml") else "PASS"}
                  for organ in organs]
            return [{"cycle":i,"records":rows,"passed":sum(x["health"]=="PASS" for x in rows),
                     "failed":sum(x["health"]=="FAIL" for x in rows),"unknown":0}
                    for i in (1,2)]
        with tempfile.TemporaryDirectory() as d,patch.object(tower,"discover",return_value=names),patch.object(tower,"circulation",new=fake_circulation):
            result=asyncio.run(tower.live(Path(d)/"report.json",expected_min=30))
        self.assertEqual(result["gate"],"PASS_OBSERVATION_ONLY")
        self.assertEqual(result["critical_blocker_count"],0)
        self.assertEqual(result["research_workflows_monitored"],1)
        self.assertEqual(len(result["research_observations"]),2)
        self.assertFalse(result["research_quality_proven_by_workflow_status"])
        self.assertFalse(result["full_autonomy_accepted"])

    def test_source_keeps_autonomy_authority_at_zero(self):
        src = (Path(__file__).resolve().parents[1] / "tools/janus_cooling_tower_async.py").read_text()
        self.assertIn('"new_workflow_dispatches": 0', src)
        self.assertIn('"new_module_executions": 0', src)
        self.assertIn('"production_code_writes": 0', src)
        self.assertNotIn("exec_module", src)
        self.assertNotIn("subprocess.run(", src)
