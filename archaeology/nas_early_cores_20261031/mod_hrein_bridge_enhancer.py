# -*- coding: utf-8 -*-
"""
mod_hrein_bridge_enhancer.py
JANUS NAS — HRAIN BRIDGE ENHANCER
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("JANUS.HREIN_ENHANCER")

ROOT_DIR = os.environ.get("JANUS_ROOT_DIR", "/app")
RUNTIME_PATH = os.environ.get("JANUS_RUNTIME_DIR") or os.path.join(ROOT_DIR, "runtime")
LAST_IMPORTED_JSON = os.path.join(RUNTIME_PATH, "last_imported.json")
HRAIN_SIGNAL_JSON = os.path.join(RUNTIME_PATH, "hraint_signal.json")
HRAIN_GRAPH_BRIDGE_JSON = os.path.join(RUNTIME_PATH, "hraint_graph_bridge.json")
ELITE_WORLD_JSON = os.path.join(RUNTIME_PATH, "atom_elite_snapshot.json")
SCAN_INTERVAL = 120


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class HreinBridgeEnhancer:
    def __init__(self, core: Any) -> None:
        self.core = core

    async def run_loop(self) -> None:
        logger.info("HREIN_ENHANCER: online.")
        while True:
            try:
                await self.tick()
                await asyncio.sleep(SCAN_INTERVAL)
            except asyncio.CancelledError:
                logger.info("HREIN_ENHANCER: stopping.")
                raise
            except Exception:
                logger.exception("HREIN_ENHANCER LOOP ERROR")
                await asyncio.sleep(60)

    async def tick(self) -> None:
        imported = _read_json(LAST_IMPORTED_JSON) or {}
        elite = _read_json(ELITE_WORLD_JSON) or {}
        meta = imported.get("meta", {}) if isinstance(imported.get("meta"), dict) else {}

        signal = {
            "updated_at": int(time.time()),
            "event_id": meta.get("event_id"),
            "dedupe_key": meta.get("dedupe_key"),
            "graph_hint": meta.get("graph_hint"),
            "thought_hint": meta.get("thought_hint"),
            "experience_hints": meta.get("experience_hints"),
            "titan_hints": meta.get("titan_hints"),
            "elite_world_present": bool(elite),
            "elite_summary": self._summarize_elite(elite),
        }

        graph_bridge = self._build_bridge(meta, elite)

        self._write_json(HRAIN_SIGNAL_JSON, signal)
        self._write_json(HRAIN_GRAPH_BRIDGE_JSON, graph_bridge)
        await self._publish(signal, graph_bridge)

    def _summarize_elite(self, elite: Dict[str, Any]) -> Dict[str, Any]:
        if not elite:
            return {}
        return {
            "pilot": elite.get("pilot_name") or elite.get("pilot", {}).get("name"),
            "system": elite.get("current_system"),
            "galaxy_index": elite.get("galaxy_index"),
            "mission": elite.get("mission"),
            "faction": elite.get("faction"),
            "biome": elite.get("biome"),
            "threat": elite.get("threat_level"),
            "goal": elite.get("goal"),
        }

    def _build_bridge(self, meta: Dict[str, Any], elite: Dict[str, Any]) -> Dict[str, Any]:
        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []

        event_id = meta.get("event_id") or f"jgpt:{int(time.time())}"
        root_id = f"janus:jgpt:event:{event_id}"
        nodes.append({
            "id": root_id,
            "label": "JGPT Event",
            "type": "jgpt",
            "description": meta.get("thought_hint") or "Structured JGPT/NAS event",
        })

        graph_hint = meta.get("graph_hint")
        if isinstance(graph_hint, dict):
            for node in graph_hint.get("nodes", [])[:80]:
                if isinstance(node, dict) and node.get("id"):
                    nodes.append(node)
            for link in graph_hint.get("links", [])[:120]:
                if isinstance(link, dict) and link.get("source") and link.get("target"):
                    links.append(link)

        thought_hint = meta.get("thought_hint")
        if thought_hint:
            thought_id = f"{root_id}:thought"
            nodes.append({
                "id": thought_id,
                "label": "Thought Hint",
                "type": "thought",
                "description": str(thought_hint),
            })
            links.append({"source": root_id, "target": thought_id, "type": "thinks"})

        for idx, exp in enumerate(meta.get("experience_hints", [])[:12]):
            exp_id = f"{root_id}:experience:{idx}"
            nodes.append({
                "id": exp_id,
                "label": "Experience Hint",
                "type": "experience",
                "description": str(exp),
            })
            links.append({"source": root_id, "target": exp_id, "type": "experienced"})

        if elite:
            elite_root = "janus:elite:world"
            nodes.append({
                "id": elite_root,
                "label": "ATOM-ELITE",
                "type": "elite_world",
                "description": "Live ATOM-ELITE world bridge",
            })
            links.append({"source": root_id, "target": elite_root, "type": "observes"})

            system = elite.get("current_system")
            if system:
                sys_id = f"janus:elite:system:{system}"
                nodes.append({
                    "id": sys_id,
                    "label": str(system),
                    "type": "elite_system",
                    "description": "Current Elite system",
                })
                links.append({"source": elite_root, "target": sys_id, "type": "located_in"})

            mission = elite.get("mission")
            if mission:
                mission_id = f"janus:elite:mission:{str(mission)[:48]}"
                nodes.append({
                    "id": mission_id,
                    "label": "Mission",
                    "type": "elite_mission",
                    "description": str(mission),
                })
                links.append({"source": elite_root, "target": mission_id, "type": "pursues"})

        return {
            "updated_at": int(time.time()),
            "namespace": "janus:jgpt:*",
            "nodes": self._dedupe_nodes(nodes),
            "links": self._dedupe_links(links),
        }

    def _dedupe_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = {}
        for n in nodes:
            nid = n.get("id")
            if nid:
                out[nid] = n
        return list(out.values())

    def _dedupe_links(self, links: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = {}
        for l in links:
            key = (l.get("source"), l.get("target"), l.get("type"))
            if key[0] and key[1]:
                out[key] = l
        return list(out.values())

    async def _publish(self, signal: Dict[str, Any], graph_bridge: Dict[str, Any]) -> None:
        try:
            if hasattr(self.core, "context") and isinstance(self.core.context, dict):
                self.core.context["hraint_signal"] = signal
                self.core.context["hraint_graph_bridge"] = graph_bridge
        except Exception:
            logger.debug("HREIN_ENHANCER: context publish skipped.", exc_info=True)

        try:
            memory = getattr(self.core, "memory", None)
            if memory is not None and hasattr(memory, "remember"):
                res = memory.remember(
                    "HREIN_ENHANCER",
                    f"event={signal.get('event_id')} elite={signal.get('elite_world_present')} nodes={len(graph_bridge.get('nodes', []))}",
                    tags="HRAIN,JGPT,ELITE,GRAPH",
                )
                if asyncio.iscoroutine(res):
                    await res
        except Exception:
            logger.debug("HREIN_ENHANCER: memory publish skipped.", exc_info=True)

    def _write_json(self, path: str, data: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


async def run(core: Any) -> None:
    enhancer = HreinBridgeEnhancer(core)
    core.hrein_bridge_enhancer = enhancer

    nexus = getattr(core, "nexus", None)
    if nexus is not None:
        active = getattr(nexus, "active_services", None)
        if hasattr(active, "add"):
            try:
                active.add("mod_hrein_bridge_enhancer")
            except Exception:
                pass

    await enhancer.run_loop()
