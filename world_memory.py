#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WORLD MEMORY — историческая память мира без потери старых событий."""

import time
from typing import List, Dict, Any

from spiral_evolution import PreservingWindow, fingerprint_payload

CONFIG = {
    'max_events': 10000,
    'trim_to': 5000,
}


class WorldMemory:
    """Bounded active memory plus an append-only archive of older events."""

    def __init__(self, max_events: int = None):
        self.max_events = int(max_events or CONFIG['max_events'])
        self.events = PreservingWindow(self.max_events)
        self.spiral_turn = 0

    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        event = {
            "turn": self.spiral_turn,
            "time": time.time(),
            "type": event_type,
            "data": data,
        }
        event["fingerprint"] = fingerprint_payload(event)
        self.spiral_turn += 1
        self.events.append(event)

    # Compatibility alias used by some older modules.
    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        self.record(event_type, data)

    def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        return list(self.events)[-n:]

    def get_recent_events(self, n: int = 50) -> List[Dict[str, Any]]:
        return self.get_recent(n)

    def get_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.events.all_items() if e["type"] == event_type]

    def all_events(self) -> List[Dict[str, Any]]:
        """Return the complete preserved world lineage, active + archived."""
        return self.events.all_items()

    def get_importance(self, event_type: str) -> float:
        matches = self.get_by_type(event_type)
        total = len(self.events.all_items())
        return (len(matches) / total) if total else 0.0

    def summarize(self) -> Dict[str, Any]:
        all_events = self.events.all_items()
        by_type: Dict[str, int] = {}
        for event in all_events:
            by_type[event["type"]] = by_type.get(event["type"], 0) + 1
        return {
            "total_events": len(all_events),
            "active_events": len(self.events),
            "archived_events": len(self.events.archive),
            "spiral_turn": self.spiral_turn,
            "by_type": by_type,
            "logical_ring": False,
        }
