# janus_genesis/tachyon_evolution.py
"""Tachyon Evolution — counterfactual world rollouts, not future prediction.

Every simulated action branch is retained as a learning attempt. The chosen
branch may become the active recommendation, while non-winning branches remain
ancestry/constraints for later turns.
"""

import copy
import logging
from typing import List, Any, Dict

from spiral_evolution import SpiralLedger, fingerprint_payload

logger = logging.getLogger("JANUS.TACHYON_EVOLUTION")

CONFIG = {
    'simulation_depth': 20,
    'simulation_runs': 5,
    'evaluation_weights': {'population': 1.0, 'institutions': 5.0, 'memes': 2.0, 'economy': 0.1}
}


class TachyonEvolutionEngine:
    def __init__(self, world: Any):
        self.world = world
        self.simulation_depth = CONFIG['simulation_depth']
        self.simulation_runs = CONFIG['simulation_runs']
        self.spiral = SpiralLedger("JANUS_TACHYON_COUNTERFACTUAL")
        self.evaluation_history: List[Dict[str, Any]] = []

    def clone_world(self) -> Any:
        if hasattr(self.world, 'clone_for_simulation'):
            return self.world.clone_for_simulation()
        return copy.deepcopy(self.world)

    def simulate_rollout(self, action: str) -> Dict[str, Any]:
        """Run bounded counterfactual simulations for one action branch."""
        scores = []
        for run_index in range(self.simulation_runs):
            sim_world = self.clone_world()
            from .strategic_actions import StrategicExecutor
            executor = StrategicExecutor()
            executor.execute(action, sim_world)
            for _ in range(self.simulation_depth):
                sim_world.update()
            scores.append(self.evaluate(sim_world))
        mean_score = sum(scores) / len(scores) if scores else 0.0
        return {
            "action": action,
            "simulation_runs": self.simulation_runs,
            "simulation_depth": self.simulation_depth,
            "scores": scores,
            "mean_score": mean_score,
            "claim_scope": "COUNTERFACTUAL_SIMULATION_ONLY",
            "world_truth": False,
        }

    def simulate(self, action: str) -> float:
        """Compatibility API: returns counterfactual mean score, not a future fact."""
        return self.simulate_rollout(action)["mean_score"]

    def predict_future(self, state=None, action=None):
        """Legacy compatibility name. This method does not predict physical future events."""
        if action is None:
            action = state
        return self.simulate_rollout(str(action))

    def evaluate(self, world: Any) -> float:
        population = len(world.population)
        institutions = len(world.institutions.institutions) if hasattr(world, 'institutions') else 0
        memes = len(world.memes.memes) if hasattr(world, 'memes') else 0
        economy = sum(world.economy.resources.values()) if hasattr(world, 'economy') else 0
        weights = CONFIG['evaluation_weights']
        return (
            population * weights['population']
            + institutions * weights['institutions']
            + memes * weights['memes']
            + economy * weights['economy']
        )

    def choose_best_action(self, actions: List[str]) -> str:
        """Evaluate every branch, retain all of them, then admit one recommendation."""
        if not actions:
            turn = self.spiral.ascend(
                state_before={"actions": []},
                candidate_state={"branches": []},
                active_state_after={"recommended_action": None},
                lessons=["No action candidates were available; preserve this as a no-ascent constraint."],
                constraints=["NO_ACTION_CANDIDATES"],
                promoted=False,
                outcome="NO_ASCENT",
            )
            self.evaluation_history.append(turn.to_dict())
            return None

        branches = []
        for action in actions:
            branch = self.simulate_rollout(action)
            branches.append(branch)
            logger.debug("Действие %s: counterfactual score %.2f", action, branch["mean_score"])

        best = max(branches, key=lambda item: item["mean_score"])
        non_winners = [
            {
                "action": branch["action"],
                "mean_score": branch["mean_score"],
                "lesson": "Branch not selected this turn; retain as explored counterfactual evidence.",
            }
            for branch in branches
            if branch is not best
        ]
        turn = self.spiral.ascend(
            state_before={"candidate_actions": list(actions)},
            candidate_state={"branches": branches},
            active_state_after={
                "recommended_action": best["action"],
                "recommended_score": best["mean_score"],
                "recommendation_fingerprint": fingerprint_payload(best),
            },
            lessons=[
                "All counterfactual branches retained; winner is a simulation recommendation, not future truth.",
                *[f"Retained non-winning branch: {item['action']} score={item['mean_score']}" for item in non_winners],
            ],
            constraints=["SIMULATION_OUTPUT_MUST_NOT_BE_PROMOTED_TO_FUTURE_EVENT_FACT"],
            score_candidate=float(best["mean_score"]),
            promoted=True,
            outcome="ASCENDED",
        )
        record = turn.to_dict()
        record["all_branches"] = branches
        record["non_winning_branches"] = non_winners
        self.evaluation_history.append(record)
        return best["action"]
