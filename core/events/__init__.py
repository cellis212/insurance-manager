"""Event system for Insurance Manager.

This module provides an asynchronous event bus for decoupled communication
between game systems and plugins.
"""

from .event_bus import EventBus, Event, EventPriority, event_bus, on_event

__all__ = [
    "EventBus",
    "Event", 
    "EventPriority",
    "event_bus",
    "on_event"
] 