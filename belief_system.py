#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BELIEF SYSTEM — beliefs change by traceable spiral transitions, not resets."""

import json
import logging
import os
import random
from typing import Dict, List, Any

from config import RAW_LOGS_DIR
from spiral_evolution import SpiralLedger

logger = logging.getLogger("JANUS.BELIEF")

CONFIG = {
    'beliefs': ["P_EQUALS_NP", "P_NOT_EQUALS_NP", "BALANCE", "CHAOS"],
    'effects': {
        'P_EQUALS_NP': {'risk_tolerance': 0.8, 'learning_rate': 1.2, 'aggression': 0.9},
        'P_NOT_EQUALS_NP': {'risk_tolerance': 1.2, 'learning_rate': 0.9, 'aggression': 1.1},
        'BALANCE': {'risk_tolerance': 1.0, 'learning_rate': 1.0, 'aggression': 1.0},
        'CHAOS': {'risk_tolerance': 1.5, 'learning_rate': 1.5, 'aggression': 1.3}
    },
    'spread_chance': 0.1,
    'max_followers': 1000
}


class Belief:
    def __init__(self, name: str, doctrine: str):
        self.name = name
        self.doctrine = doctrine
        self.followers = 0
        self.effects = CONFIG['effects'].get(name, {})

    def spread(self):
        self.followers += 1

    def lose_follower(self):
        if self.followers > 0:
            self.followers -= 1

    def to_dict(self):
        return {
            'name': self.name,
            'doctrine': self.doctrine,
            'followers': self.followers,
            'effects': self.effects
        }

    @classmethod
    def from_dict(cls, data):
        belief = cls(data['name'], data['doctrine'])
        belief.followers = data['followers']
        belief.effects = data['effects']
        return belief


class BeliefSystem:
    def __init__(self, save_file: str = None):
        self.save_file = save_file or os.path.join(RAW_LOGS_DIR, "beliefs.json")
        self.beliefs: Dict[str, Belief] = {}
        self.spiral = SpiralLedger("JANUS_BELIEF_SYSTEM")
        self.persisted_ancestry: List[Dict[str, Any]] = []
        self._init_beliefs()
        self.load_state()

    def _init_beliefs(self):
        for name in CONFIG['beliefs']:
            doctrine = f"Учение веры {name}"
            self.beliefs[name] = Belief(name, doctrine)

    def _snapshot(self, agents: List[Any] = None) -> Dict[str, Any]:
        snapshot = {"beliefs": {name: belief.to_dict() for name, belief in self.beliefs.items()}}
        if agents is not None:
            snapshot["agents"] = {
                str(getattr(agent, "id", index)): getattr(agent, "belief", None)
                for index, agent in enumerate(agents)
            }
        return snapshot

    def update(self, agents: List[Any], meta_goal: Any = None) -> None:
        if not agents:
            return
        before = self._snapshot(agents)
        transitions = []

        belief_counts = {name: 0 for name in self.beliefs}
        for agent in agents:
            if getattr(agent, "belief", None) and agent.belief in belief_counts:
                belief_counts[agent.belief] += 1
        for name, count in belief_counts.items():
            self.beliefs[name].followers = count

        for agent in agents:
            if random.random() < CONFIG['spread_chance']:
                total = sum(b.followers for b in self.beliefs.values())
                if total > 0:
                    names = list(self.beliefs.keys())
                    weights = [self.beliefs[n].followers for n in names]
                    chosen = random.choices(names, weights=weights, k=1)[0]
                    previous = getattr(agent, "belief", None)
                    agent.belief = chosen
                    transitions.append({
                        "agent_id": str(getattr(agent, "id", repr(agent))),
                        "from": previous,
                        "to": chosen,
                        "reason": "SPREAD",
                    })
                    logger.debug("Агент %s принял веру %s", str(getattr(agent, "id", "?"))[:8], chosen)

        for agent in agents:
            if not getattr(agent, "belief", None):
                chosen = random.choice(CONFIG['beliefs'])
                agent.belief = chosen
                transitions.append({
                    "agent_id": str(getattr(agent, "id", repr(agent))),
                    "from": None,
                    "to": chosen,
                    "reason": "INITIAL_ASSIGNMENT",
                })

        parameter_changes = []
        for agent in agents:
            if getattr(agent, "belief", None) and agent.belief in self.beliefs:
                belief = self.beliefs[agent.belief]
                for param, factor in belief.effects.items():
                    if hasattr(agent, param):
                        current = getattr(agent, param)
                        new_val = current * (0.9 + factor * 0.2)
                        setattr(agent, param, new_val)
                        parameter_changes.append({
                            "agent_id": str(getattr(agent, "id", repr(agent))),
                            "param": param,
                            "before": current,
                            "after": new_val,
                            "belief": agent.belief,
                        })

        after = self._snapshot(agents)
        changed = before != after
        self.spiral.ascend(
            state_before=before,
            candidate_state={
                "meta_goal": meta_goal,
                "belief_transitions": transitions,
                "parameter_changes": parameter_changes,
            },
            active_state_after=after,
            lessons=["Belief transitions preserved; changed beliefs are new turns of the same agents, not erased identities."],
            promoted=changed,
            outcome="ASCENDED" if changed else "NO_ASCENT",
        )
        self.save_state()

    def get_dominant_belief(self) -> tuple:
        if not self.beliefs:
            return (None, 0)
        dominant = max(self.beliefs.items(), key=lambda x: x[1].followers)
        return (dominant[0], dominant[1].followers)

    def narrate(self) -> List[str]:
        return [f"    {name}: {belief.followers}" for name, belief in self.beliefs.items()]

    def _all_spiral_records(self) -> List[Dict[str, Any]]:
        return [*self.persisted_ancestry, *[turn.to_dict() for turn in self.spiral.turns]]

    def save_state(self):
        state = {name: belief.to_dict() for name, belief in self.beliefs.items()}
        state["__spiral__"] = {
            "model": "SPIRAL_ACCUMULATIVE_NO_ENTITY_DELETION",
            "turns": self._all_spiral_records(),
        }
        try:
            tmp = self.save_file + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False)
            os.replace(tmp, self.save_file)
            logger.debug("💾 Belief system сохранён")
        except Exception as exc:
            logger.error("Ошибка сохранения belief system: %s", exc)

    def load_state(self):
        if not os.path.exists(self.save_file):
            return
        try:
            with open(self.save_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            for name, belief_data in data.items():
                if name in self.beliefs and isinstance(belief_data, dict):
                    self.beliefs[name].followers = belief_data.get('followers', 0)
                    self.beliefs[name].effects = belief_data.get('effects', self.beliefs[name].effects)
            spiral_data = data.get("__spiral__") if isinstance(data, dict) else None
            if isinstance(spiral_data, dict) and isinstance(spiral_data.get("turns"), list):
                # Preserve serialized historical receipts verbatim. Do not replay them into
                # a new hash chain and do not pretend loading is a fresh evolution event.
                self.persisted_ancestry = list(spiral_data["turns"])
            logger.info("📖 Belief system загружен: %s; ancestry=%s", self.get_dominant_belief(), len(self.persisted_ancestry))
        except Exception as exc:
            logger.error("Ошибка загрузки belief system: %s", exc)

    def reset(self):
        """Legacy debug API: start a fresh active belief state while preserving parent state."""
        before = self._snapshot()
        self.beliefs = {}
        self._init_beliefs()
        after = self._snapshot()
        self.spiral.ascend(
            state_before=before,
            candidate_state={"legacy_reset_request": True},
            active_state_after=after,
            lessons=["Legacy reset converted into a traceable new active turn; parent belief state retained."],
            constraints=["RESET_MUST_NOT_ERASE_LINEAGE"],
            promoted=True,
            outcome="ASCENDED_FROM_LEGACY_RESET",
        )
        self.save_state()
