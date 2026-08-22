import copy
import sys
import tempfile
import types
import unittest
from pathlib import Path

# species_engine only needs RAW_LOGS_DIR from the historical config module.
# The real config imports torch, which is irrelevant to these contract tests.
config_stub = types.ModuleType("config")
config_stub.RAW_LOGS_DIR = tempfile.gettempdir()
sys.modules.setdefault("config", config_stub)

from auto_evolution import AutoEvolution
from janus_core.convergence_engine import SolutionField
from species_engine import Species, SpeciesEngine
from spiral_evolution import PreservingWindow, SpiralLedger
from swarm_optimizer import SwarmOptimizer


class FakeCore:
    def __init__(self, utility=1.0):
        self.alpha = 0.1
        self.gamma = 0.9
        self.epsilon = 0.2
        self.utility = utility

    def select_action(self, _state):
        return None

    def compute_utility(self, _state):
        return self.utility


class FakeEnv:
    def step(self, _state, _action):
        return None


class DeterministicEvolution(AutoEvolution):
    def mutate_core(self, core):
        candidate = copy.deepcopy(core)
        candidate.utility = core.utility - 0.25
        candidate.alpha += 0.01
        return candidate


class SpiralEvolutionTests(unittest.TestCase):
    def test_ledger_chains_parent_fingerprints(self):
        ledger = SpiralLedger("X")
        first = ledger.ascend(state_before={"v": 0}, candidate_state={"v": 1}, active_state_after={"v": 1}, promoted=True)
        second = ledger.ascend(state_before={"v": 1}, candidate_state={"v": 2}, active_state_after={"v": 1}, lessons=["not better"], promoted=False)
        self.assertEqual(second.turn, 1)
        self.assertEqual(second.parent_fingerprint, first.fingerprint)
        self.assertEqual(second.outcome, "INTEGRATED_LESSON")

    def test_preserving_window_archives_overflow(self):
        window = PreservingWindow(2)
        for value in range(5):
            window.append(value)
        self.assertEqual(list(window), [3, 4])
        self.assertEqual(window.archive, [0, 1, 2])
        self.assertEqual(window.all_items(), [0, 1, 2, 3, 4])

    def test_failed_mutation_becomes_lesson(self):
        evolution = DeterministicEvolution()
        core = FakeCore(utility=1.0)
        active, improved = evolution.evolve(core, object(), FakeEnv())
        self.assertFalse(improved)
        self.assertIs(active, core)
        self.assertEqual(len(evolution.history), 1)
        self.assertEqual(evolution.history[0]["outcome"], "INTEGRATED_LESSON")
        self.assertTrue(evolution.history[0]["lessons"])

    def test_species_cull_alias_never_extinguishes_identity(self):
        with tempfile.TemporaryDirectory() as td:
            engine = SpeciesEngine(registry_path=str(Path(td) / "species.json"))
            weak = engine.create_species("weak", "transformer")
            strong = engine.create_species("strong", "transformer")
            weak.fitness_history.append(0.1)
            strong.fitness_history.append(1.0)
            affected = engine.cull_weak_species(threshold=0.5)
            self.assertIn("weak", affected)
            self.assertFalse(weak.extinct)
            self.assertIn(weak.status, {"ASCENDING", "ACTIVE"})
            self.assertTrue(weak.lineage)
            self.assertIs(engine.get_species_by_name("weak"), weak)

    def test_legacy_extinction_is_recovered_on_load(self):
        recovered = Species.from_dict({
            "name": "ancestor",
            "arch_type": "hybrid",
            "population": [],
            "fitness_history": [0.1],
            "birth_time": 1,
            "extinct": True,
        })
        self.assertFalse(recovered.extinct)
        self.assertEqual(recovered.status, "RECOVERED_FROM_LEGACY_EXTINCTION")

    def test_solution_frontier_does_not_delete_lineage(self):
        field = SolutionField(frontier_size=3)
        for i in range(10):
            field.add({"i": i}, verify_score=i / 10, compression=0.5, progress=0.5)
        self.assertEqual(len(field.pool), 3)
        self.assertEqual(len(field.lineage), 10)
        self.assertEqual(len(field.lessons_below_frontier()), 7)

    def test_particle_slot_wraps_but_spiral_turn_does_not(self):
        optimizer = SwarmOptimizer(n_particles=2)
        seen = []
        for score in [1.0, 0.5, 0.25, 2.0, 1.5]:
            _, idx = optimizer.ask()
            seen.append((optimizer.spiral_turn - 1, idx))
            optimizer.tell(idx, score)
        self.assertEqual([x[0] for x in seen], [0, 1, 2, 3, 4])
        self.assertEqual([x[1] for x in seen], [0, 1, 0, 1, 0])
        self.assertEqual(len(optimizer.lineage), 5)
        self.assertFalse(optimizer.get_spiral_state()["logical_ring"])


if __name__ == "__main__":
    unittest.main()
