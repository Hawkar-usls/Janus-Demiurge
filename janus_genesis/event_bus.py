# janus_genesis/event_bus.py
"""
Единая шина событий для всего мира.
Позволяет системам общаться без жёстких связей.
"""

class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, handler):
        """Подписать функцию на тип события."""
        self._subscribers.setdefault(event_type, []).append(handler)

    def emit(self, event_type, **payload):
        """Оповестить всех подписчиков о событии."""
        for handler in self._subscribers.get(event_type, []):
            handler(**payload)