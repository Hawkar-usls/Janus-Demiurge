#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WORLD MEMORY — историческая память мира.
"""

import time
from typing import List, Dict, Any

CONFIG = {
    'max_events': 10000,
    'trim_to': 5000
}


class WorldMemory:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def record(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Записывает событие в память.
        """
        self.events.append({
            "time": time.time(),
            "type": event_type,
            "data": data
        })
        if len(self.events) > CONFIG['max_events']:
            self.events = self.events[-CONFIG['trim_to']:]

    def get_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        """Возвращает последние n событий."""
        return self.events[-n:]

    def get_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Возвращает все события заданного типа."""
        return [e for e in self.events if e["type"] == event_type]