#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autonomous graph growth logic for HRAIN."""

from __future__ import annotations

import math
import random
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

from restored.experimental_sat_profile import clause_occupancy_profile, graph_fragment_to_clauses


VALID_NODE_TYPES = {"janus", "ally", "threat", "intel", "sleeper", "plug", "info"}
PROTECTED_ROLES = {"core", "shrine", "daemon", "observer"}

TYPE_EMOJI = {
    "janus": "🧠",
    "ally": "🤖",
    "threat": "🐉",
    "intel": "✨",
    "sleeper": "💤",
    "plug": "🔌",
    "info": "💎",
}

TYPE_TEMP = {"janus": 37.0, "ally": 44.0, "threat": 68.0, "intel": 31.0, "sleeper": 18.0, "plug": 52.0, "info": 27.0}
TYPE_PURITY = {"janus": 96.0, "ally": 72.0, "threat": 38.0, "intel": 88.0, "sleeper": 52.0, "plug": 66.0, "info": 91.0}

ROOTS = [
    ("core", "JANUS", "janus", "Primary root of the living graph.", (0.0, 0.0), "🧠"),
    ("shrine", "Shrine", "info", "Sanctuary where ideas crystallize.", (-260.0, 140.0), "⛩️"),
    ("daemon", "Maxwell", "plug", "Entropy-sorting daemon.", (260.0, -120.0), "⚙️"),
    ("observer", "Bioscope", "intel", "Telemetry observatory.", (320.0, 220.0), "🔭"),
]

ROOT_NAME_BANK = [
    ("Threshold Garden", "info"),
    ("Vector Cloister", "intel"),
    ("Dream Reservoir", "ally"),
    ("Mirror Atlas", "info"),
    ("Mycelium Spine", "ally"),
    ("Archive Current", "intel"),
    ("World Scaffold", "plug"),
]

LEXICON = {
    "ally": (["Living", "Fractal", "Adaptive", "Solar", "Tender"], ["Spore", "Walker", "Nest", "Garden", "Cell"]),
    "threat": (["Wild", "Rogue", "Splinter", "Obsidian", "Ferrous"], ["Shadow", "Rift", "Bite", "Spine", "Swarm"]),
    "intel": (["Silent", "Deep", "Oracle", "Crystal", "Hidden"], ["Lens", "Map", "Archive", "Beacon", "Signal"]),
    "sleeper": (["Dormant", "Cold", "Latent", "Submerged", "Still"], ["Seed", "Pocket", "Echo", "Vault", "Shell"]),
    "plug": (["Charged", "Entropy", "Voltage", "Conduit", "Copper"], ["Bridge", "Gate", "Switch", "Relay", "Loop"]),
    "info": (["Radiant", "Encoded", "Sacred", "Mnemonic", "Nested"], ["Glyph", "Diagram", "Mirror", "Thread", "Chalice"]),
    "janus": (["Axial", "Prime", "Liminal", "Mirror", "Sovereign"], ["Threshold", "Kernel", "Cathedral", "Engine", "Heart"]),
}


class HrainAutonomy:
    """Quarantined All Star research autonomy; synthetic-only manual admission.

    Does not launch itself or receive access to owner-private persisted state.
    """

    def __init__(self, graph_engine, *, synthetic_only: bool = False):
        self.graph = graph_engine
        self._synthetic_only = bool(synthetic_only)
        self.runtime: Dict[str, Any] = {
            "running": False,
            "cycle": 0,
            "roots_created": 0,
            "branches_created": 0,
            "links_created": 0,
            "nodes_pruned": 0,
            "device_updates": 0,
            "daemon_interventions": 0,
            "daemon_mode": "warming",
            "last_action": "Awaiting ignition",
            "last_focus": None,
            "last_profile": None,
            "math_engine": "vested-clause-profile",
            "recent_events": deque(maxlen=200),
        }

    def enable_synthetic_sandbox(self) -> None:
        """Explicit opt-in for disposable synthetic tests, never live memory."""
        if not self._synthetic_only or self.graph.nodes or self.graph.edges:
            raise PermissionError("HRAIN_AUTONOMY_RESEARCH_ONLY_HOLD")
        self.runtime["running"] = True

    def _assert_synthetic_enabled(self) -> None:
        if not self._synthetic_only or not self.runtime["running"]:
            raise PermissionError("HRAIN_AUTONOMY_RESEARCH_ONLY_HOLD")

    def roots(self) -> List[Dict[str, Any]]:
        return [node for node in self.graph.nodes.values() if not node["data"].get("parentId")]

    def children(self, node_id: str) -> List[Dict[str, Any]]:
        return [node for node in self.graph.nodes.values() if node["data"].get("parentId") == node_id]

    def find_role(self, role: str) -> Optional[str]:
        for node_id, node in self.graph.nodes.items():
            if node["data"].get("role") == role:
                return node_id
        return None

    def top(self) -> Optional[Dict[str, Any]]:
        if not self.graph.nodes:
            return None
        return max(self.graph.nodes.values(), key=lambda node: node["energy"])

    def _type_defaults(self, node_type: str) -> tuple[float, float]:
        safe = node_type if node_type in VALID_NODE_TYPES else "ally"
        return TYPE_TEMP[safe], TYPE_PURITY[safe]

    def _position(self, parent_id: Optional[str], explicit: Optional[tuple[float, float]]) -> tuple[float, float]:
        if explicit is not None:
            return explicit
        if parent_id and parent_id in self.graph.nodes:
            parent = self.graph.nodes[parent_id]
            angle = random.random() * math.tau
            radius = 140.0 + min(160.0, 18.0 * len(self.children(parent_id)))
            return (
                float(parent["data"].get("x", 0.0)) + math.cos(angle) * radius,
                float(parent["data"].get("y", 0.0)) + math.sin(angle) * radius,
            )
        angle = random.random() * math.tau
        radius = 260.0 + 42.0 * len(self.roots())
        return math.cos(angle) * radius, math.sin(angle) * radius

    def _node_payload(self, label: str, node_type: str, description: str, parent_id: Optional[str], role: str, level: int, score: float, x: float, y: float, emoji: Optional[str], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        temp, purity = self._type_defaults(node_type)
        data = {
            "label": label,
            "emoji": emoji or TYPE_EMOJI.get(node_type, "🔹"),
            "x": round(x, 3),
            "y": round(y, 3),
            "parentId": parent_id,
            "description": description,
            "chatHistory": [],
            "level": int(level),
            "score": max(0.01, min(0.99, score)),
            "role": role,
            "purity": purity,
            "temp": temp,
            "agent_id": role or label.lower().replace(" ", "_"),
            "created_at": datetime.now().isoformat(),
            "lineage_depth": 0 if not parent_id else level - 1,
        }
        if extra:
            data.update(extra)
        return data

    def create_node(self, node_type: str, label: str, description: str, *, parent_id: Optional[str] = None, role: str = "idea", energy: float = 1.0, level: int = 1, score: float = 0.5, emoji: Optional[str] = None, position: Optional[tuple[float, float]] = None, extra: Optional[Dict[str, Any]] = None) -> str:
        self._assert_synthetic_enabled()
        safe_type = node_type if node_type in VALID_NODE_TYPES else "ally"
        x, y = self._position(parent_id, position)
        payload = self._node_payload(label, safe_type, description, parent_id, role, level, score, x, y, emoji, extra)
        node_id = self.graph.add_node(safe_type, payload, energy=energy)
        if parent_id:
            self.graph.add_edge(parent_id, node_id, "growth", weight=1.0)
        return node_id

    def ensure_foundation(self) -> List[str]:
        self._assert_synthetic_enabled()
        created = []
        for role, label, node_type, description, position, emoji in ROOTS:
            if self.find_role(role):
                continue
            self.create_node(node_type, label, description, role=role, energy=1.25, level=1, score=0.88, emoji=emoji, position=position)
            self.runtime["roots_created"] += 1
            created.append(label)
        return created

    def public_state(self) -> Dict[str, Any]:
        nodes = []
        for node in self.graph.nodes.values():
            data = node["data"]
            nodes.append({
                "id": node["id"],
                "label": data.get("label", node["type"]),
                "emoji": data.get("emoji", TYPE_EMOJI.get(node["type"], "🔹")),
                "type": node["type"] if node["type"] in VALID_NODE_TYPES else "ally",
                "x": data.get("x", 0.0),
                "y": data.get("y", 0.0),
                "parentId": data.get("parentId"),
                "description": data.get("description", ""),
                "chatHistory": data.get("chatHistory", []),
                "level": data.get("level", 1),
                "score": data.get("score", 0.0),
                "energy": round(float(node.get("energy", 0.0)), 4),
                "role": data.get("role"),
            })
        links = [{"source": key.split("->")[0], "target": key.split("->")[1], "weight": round(float(edge.get("weight", 1.0)), 4)} for key, edge in self.graph.edges.items()]
        return {"nodes": nodes, "links": links, "meta": self.snapshot(include_recent=False)}

    def run_dynamics(self) -> None:
        self._assert_synthetic_enabled()
        self.graph.decay_edges()
        self.graph.decay_nodes()
        self.graph.propagate_energy()
        self.graph.reinforce_active_paths()
        self.graph.random_exploration()
        self.graph.auto_link()
        self.graph.temporal_decay()

    def edge_exists(self, src: str, dst: str) -> bool:
        return f"{src}->{dst}" in self.graph.edges or f"{dst}->{src}" in self.graph.edges

    def upsert_device(self, device_id: str, payload: Any) -> None:
        self._assert_synthetic_enabled()
        role = f"device:{device_id}"
        existing = self.find_role(role)
        observer_id = self.find_role("observer") or self.find_role("core")
        if existing and existing in self.graph.nodes:
            node = self.graph.nodes[existing]
            node["energy"] = min(2.0, node["energy"] + 0.12)
            node["last_used"] = self.graph.tick
            node["data"]["description"] = f"Telemetry stream from {device_id}."
            node["data"]["last_payload"] = payload
            node["data"]["last_seen"] = datetime.now().isoformat()
        else:
            self.create_node(
                "plug",
                device_id.upper(),
                f"Telemetry stream from {device_id}.",
                parent_id=observer_id,
                role=role,
                energy=0.95,
                level=2,
                score=0.5,
                emoji="📡",
                extra={"last_payload": payload, "last_seen": datetime.now().isoformat()},
            )
        self.runtime["device_updates"] += 1

    def snapshot(self, include_recent: bool = True) -> Dict[str, Any]:
        payload = {
            "status": "ok",
            "running": self.runtime["running"],
            "cycle": self.runtime["cycle"],
            "daemon_mode": self.runtime["daemon_mode"],
            "last_action": self.runtime["last_action"],
            "last_focus": self.runtime["last_focus"],
            "last_profile": self.runtime["last_profile"],
            "math_engine": self.runtime["math_engine"],
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
            "root_nodes": len(self.roots()),
            "roots_created": self.runtime["roots_created"],
            "branches_created": self.runtime["branches_created"],
            "links_created": self.runtime["links_created"],
            "nodes_pruned": self.runtime["nodes_pruned"],
            "device_updates": self.runtime["device_updates"],
            "daemon_interventions": self.runtime["daemon_interventions"],
        }
        if include_recent:
            payload["recent_events"] = list(self.runtime["recent_events"])[-30:]
        return payload

    def record(self, kind: str, text: str, **extra: Any) -> Dict[str, Any]:
        event = {"timestamp": datetime.now().isoformat(), "cycle": self.runtime["cycle"], "kind": kind, "text": text, "extra": extra}
        self.runtime["recent_events"].append(event)
        self.runtime["last_action"] = text
        self.runtime["last_focus"] = extra.get("focus")
        return event

    def _profile(self, focus: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        children = []
        for node in self.children(focus["id"]):
            data = node["data"]
            children.append(
                {
                    "id": node["id"],
                    "label": data.get("label", node["id"]),
                    "type": node["type"],
                    "score": data.get("score", 0.0),
                }
            )
        n_vars, clauses = graph_fragment_to_clauses(children)
        if n_vars <= 0 or not clauses:
            return None
        profile = clause_occupancy_profile(n_vars, clauses).to_dict()
        self.runtime["last_profile"] = {
            "n_vars": profile["n_vars"],
            "distinct_vested_clauses": profile["distinct_vested_clauses"],
            "universe_size": profile["universe_size"],
            "saturation_ratio": round(float(profile["saturation_ratio"]), 4),
            "open_space": profile["open_space"],
        }
        return profile

    def _maxwell(self, focus: Optional[Dict[str, Any]]) -> str:
        self._assert_synthetic_enabled()
        self.runtime["daemon_interventions"] += 1
        self.runtime["daemon_mode"] = "sorting"
        removable = []
        for node in self.graph.nodes.values():
            role = str(node["data"].get("role", ""))
            if role in PROTECTED_ROLES or role.startswith("device:"):
                continue
            if self.children(node["id"]):
                continue
            removable.append(node)
        removable.sort(key=lambda node: node["energy"])
        if removable and removable[0]["energy"] < 0.11 and len(self.graph.nodes) > 14:
            # Retention firewall: an observer may detect an old/weak leaf,
            # but MUST NOT delete private memory or claim it was pruned.
            self.runtime["daemon_mode"] = "retention_hold"
            return "Maxwell retention HOLD; no node pruned"
        hot = sorted(self.graph.nodes.values(), key=lambda node: node["energy"], reverse=True)
        if len(hot) >= 2 and not self.edge_exists(hot[0]["id"], hot[1]["id"]):
            self.graph.add_edge(hot[0]["id"], hot[1]["id"], "daemon", weight=1.15)
            self.runtime["links_created"] += 1
            self.runtime["daemon_mode"] = "bridging"
            return f"Maxwell linked {hot[0]['data'].get('label', hot[0]['id'])} -> {hot[1]['data'].get('label', hot[1]['id'])}"
        if focus is not None:
            daemon_id = self.find_role("daemon")
            if daemon_id and not self.edge_exists(daemon_id, focus["id"]):
                self.graph.add_edge(daemon_id, focus["id"], "daemon", weight=1.1)
                self.runtime["links_created"] += 1
                self.runtime["daemon_mode"] = "observing"
                return f"Maxwell locked onto {focus['data'].get('label', focus['id'])}"
        self.runtime["daemon_mode"] = "stabilizing"
        return "Maxwell stabilized the field"

    def _grow_child(self, parent: Dict[str, Any], override_type: Optional[str] = None) -> str:
        self._assert_synthetic_enabled()
        node_type = override_type or random.choice([parent["type"], "ally", "intel", "info", "plug", "sleeper"])
        adjectives, nouns = LEXICON[node_type if node_type in LEXICON else "ally"]
        label = f"{random.choice(adjectives)} {random.choice(nouns)}"
        level = int(parent["data"].get("level", 1) or 1) + 1
        score = max(0.01, min(0.99, float(parent["data"].get("score", 0.45) or 0.45) * 0.85 + random.uniform(-0.08, 0.18)))
        new_id = self.create_node(node_type, label, f"Autonomous branch grown from {parent['data'].get('label', parent['id'])}.", parent_id=parent["id"], role="idea", energy=max(0.45, float(parent["energy"]) * 0.72), level=level, score=score)
        self.runtime["branches_created"] += 1
        return new_id

    def cycle_once(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        if not self.runtime["running"] or not self._synthetic_only:
            return self.public_state(), {
                "kind": "HOLD_NOT_ACTIVATED", "text": "Synthetic research autonomy disabled"
            }
        limit = int(self.graph.config["max_nodes"])
        missing_roots = sum(1 for role, *_ in ROOTS if self.find_role(role) is None)
        if len(self.graph.nodes) + missing_roots > limit or len(self.graph.nodes) >= limit:
            return self.public_state(), {
                "kind": "CAPACITY_HOLD", "text": "Historical graph protected; no eviction"
            }
        self.graph.tick += 1
        self.runtime["cycle"] += 1
        created = self.ensure_foundation()
        if created:
            event = self.record("foundation", f"Foundation seeded: {', '.join(created)}", focus="foundation")
            self.run_dynamics()
            return self.public_state(), event
        focus = self.top()
        profile = self._profile(focus) if focus else None
        saturation = float((profile or {}).get("saturation_ratio", 0.0))
        if profile and saturation >= 0.92 and len(self.roots()) < 8:
            for label, node_type in ROOT_NAME_BANK:
                if label.lower() not in {str(node["data"].get("label", "")).lower() for node in self.graph.nodes.values()}:
                    self.create_node(node_type, label, f"Autonomous root born because saturation={saturation:.3f}.", role="root:autonomous", energy=1.1, level=1, score=0.76)
                    self.runtime["roots_created"] += 1
                    self.run_dynamics()
                    return self.public_state(), self.record("root", f"New root emerged: {label}", focus=label)
        if focus:
            if random.random() < 0.3:
                text = self._maxwell(focus)
                self.run_dynamics()
                return self.public_state(), self.record("daemon", text, focus=focus["data"].get("label", focus["id"]))
            node_id = self._grow_child(focus, override_type=random.choice(["ally", "intel", "info", "plug"]))
            label = self.graph.nodes[node_id]["data"].get("label", node_id)
            self.run_dynamics()
            return self.public_state(), self.record("growth", f"Branch grown under {focus['data'].get('label', focus['id'])}: {label}", focus=focus["data"].get("label", focus["id"]))
        self.run_dynamics()
        return self.public_state(), self.record("idle", "HRAIN idled", focus=None)
