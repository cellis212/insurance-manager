"""Event bus for plugin communication in Insurance Manager.

This module provides an asynchronous event bus that allows plugins to
communicate without direct dependencies. Events can be emitted and
handled both synchronously and asynchronously.
"""

import asyncio
import inspect
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4
from weakref import WeakSet

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event handler priority levels."""
    
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


@dataclass
class Event:
    """Base class for all events in the system."""
    
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: UUID = field(default_factory=uuid4)
    correlation_id: Optional[UUID] = None
    
    def __post_init__(self):
        """Validate event after initialization."""
        if not self.event_type:
            raise ValueError("Event type cannot be empty")


@dataclass
class EventHandler:
    """Wrapper for event handler functions with metadata."""
    
    handler: Callable
    event_types: Set[str]
    priority: EventPriority = EventPriority.NORMAL
    plugin_name: Optional[str] = None
    is_async: bool = False
    
    def __post_init__(self):
        """Determine if handler is async after initialization."""
        self.is_async = inspect.iscoroutinefunction(self.handler)


class EventBus:
    """Asynchronous event bus for plugin communication.
    
    The event bus allows plugins to emit events and register handlers
    without knowing about each other. Supports both sync and async handlers,
    event filtering, priority ordering, and error handling.
    """
    
    def __init__(self):
        """Initialize the event bus."""
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._handler_errors: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._active_handlers: WeakSet = WeakSet()
        self._lock = asyncio.Lock()
    
    async def emit(
        self, 
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        correlation_id: Optional[UUID] = None,
        wait_for_handlers: bool = True
    ) -> Event:
        """Emit an event to all registered handlers.
        
        Args:
            event_type: Type of event to emit
            data: Event data dictionary
            source: Name of the plugin/component emitting the event
            correlation_id: Optional ID to correlate related events
            wait_for_handlers: If True, wait for all handlers to complete
            
        Returns:
            The emitted Event object
        """
        event = Event(
            event_type=event_type,
            data=data or {},
            source=source,
            correlation_id=correlation_id
        )
        
        # Add to history
        async with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history_size:
                self._event_history.pop(0)
        
        # Get handlers for this event type
        handlers = self._get_handlers_for_event(event_type)
        
        if not handlers:
            logger.debug(f"No handlers registered for event type: {event_type}")
            return event
        
        # Execute handlers
        if wait_for_handlers:
            await self._execute_handlers(event, handlers)
        else:
            # Fire and forget
            asyncio.create_task(self._execute_handlers(event, handlers))
        
        return event
    
    def emit_sync(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ) -> Event:
        """Synchronously emit an event (creates new event loop if needed).
        
        This is a convenience method for non-async contexts. Use sparingly.
        
        Args:
            event_type: Type of event to emit
            data: Event data dictionary
            source: Name of the plugin/component emitting the event
            
        Returns:
            The emitted Event object
        """
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, use create_task
            task = asyncio.create_task(
                self.emit(event_type, data, source, wait_for_handlers=False)
            )
            return Event(event_type=event_type, data=data or {}, source=source)
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.emit(event_type, data, source))
    
    def register(
        self,
        event_types: Union[str, List[str]],
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        plugin_name: Optional[str] = None
    ) -> None:
        """Register an event handler.
        
        Args:
            event_types: Event type(s) to handle (can use wildcards)
            handler: Callable to handle the event
            priority: Handler priority (lower executes first)
            plugin_name: Name of the plugin registering the handler
        """
        if isinstance(event_types, str):
            event_types = [event_types]
        
        event_handler = EventHandler(
            handler=handler,
            event_types=set(event_types),
            priority=priority,
            plugin_name=plugin_name
        )
        
        # Register for each event type
        for event_type in event_types:
            self._handlers[event_type].append(event_handler)
            # Sort by priority
            self._handlers[event_type].sort(key=lambda h: h.priority.value)
        
        # Track active handler
        self._active_handlers.add(event_handler)
        
        logger.debug(
            f"Registered handler {handler.__name__} for events: {event_types} "
            f"(plugin: {plugin_name}, priority: {priority.name})"
        )
    
    def unregister(self, handler: Callable) -> None:
        """Unregister an event handler.
        
        Args:
            handler: The handler function to unregister
        """
        removed_count = 0
        for event_type, handlers in self._handlers.items():
            handlers_to_remove = [h for h in handlers if h.handler == handler]
            for h in handlers_to_remove:
                handlers.remove(h)
                removed_count += 1
        
        if removed_count > 0:
            logger.debug(f"Unregistered handler {handler.__name__} ({removed_count} registrations)")
        else:
            logger.warning(f"Handler {handler.__name__} was not registered")
    
    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister all handlers for a specific plugin.
        
        Args:
            plugin_name: Name of the plugin whose handlers to remove
        """
        removed_count = 0
        for event_type, handlers in self._handlers.items():
            handlers_to_remove = [h for h in handlers if h.plugin_name == plugin_name]
            for h in handlers_to_remove:
                handlers.remove(h)
                removed_count += 1
        
        if removed_count > 0:
            logger.debug(f"Unregistered {removed_count} handlers for plugin: {plugin_name}")
    
    async def _execute_handlers(self, event: Event, handlers: List[EventHandler]) -> None:
        """Execute handlers for an event.
        
        Args:
            event: The event to handle
            handlers: List of handlers to execute
        """
        tasks = []
        
        for handler in handlers:
            try:
                if handler.is_async:
                    task = asyncio.create_task(self._call_async_handler(handler, event))
                    tasks.append(task)
                else:
                    # Run sync handler in thread pool to avoid blocking
                    task = asyncio.create_task(
                        asyncio.to_thread(self._call_sync_handler, handler, event)
                    )
                    tasks.append(task)
            except Exception as e:
                logger.error(
                    f"Error creating task for handler {handler.handler.__name__}: {str(e)}",
                    exc_info=True
                )
                self._record_handler_error(handler, event, e)
        
        # Wait for all handlers to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    handler = handlers[i]
                    logger.error(
                        f"Handler {handler.handler.__name__} failed for event "
                        f"{event.event_type}: {str(result)}",
                        exc_info=result
                    )
                    self._record_handler_error(handler, event, result)
    
    async def _call_async_handler(self, handler: EventHandler, event: Event) -> None:
        """Call an async event handler.
        
        Args:
            handler: The handler wrapper
            event: The event to handle
        """
        await handler.handler(event)
    
    def _call_sync_handler(self, handler: EventHandler, event: Event) -> None:
        """Call a sync event handler.
        
        Args:
            handler: The handler wrapper
            event: The event to handle
        """
        handler.handler(event)
    
    def _get_handlers_for_event(self, event_type: str) -> List[EventHandler]:
        """Get all handlers that match an event type.
        
        Supports wildcard matching with '*' at the end of handler patterns.
        
        Args:
            event_type: The event type to match
            
        Returns:
            List of matching handlers sorted by priority
        """
        matching_handlers = []
        
        # Direct match
        if event_type in self._handlers:
            matching_handlers.extend(self._handlers[event_type])
        
        # Wildcard matches
        for pattern, handlers in self._handlers.items():
            if pattern.endswith("*") and event_type.startswith(pattern[:-1]):
                matching_handlers.extend(handlers)
        
        # Sort by priority and remove duplicates
        seen = set()
        unique_handlers = []
        for handler in sorted(matching_handlers, key=lambda h: h.priority.value):
            if handler.handler not in seen:
                seen.add(handler.handler)
                unique_handlers.append(handler)
        
        return unique_handlers
    
    def _record_handler_error(
        self, 
        handler: EventHandler, 
        event: Event, 
        error: Exception
    ) -> None:
        """Record a handler error for debugging.
        
        Args:
            handler: The handler that failed
            event: The event being handled
            error: The exception that occurred
        """
        error_record = {
            "timestamp": datetime.now(timezone.utc),
            "handler_name": handler.handler.__name__,
            "plugin_name": handler.plugin_name,
            "event_type": event.event_type,
            "event_id": str(event.event_id),
            "error_type": type(error).__name__,
            "error_message": str(error)
        }
        
        self._handler_errors[handler.handler.__name__].append(error_record)
        
        # Keep only recent errors
        if len(self._handler_errors[handler.handler.__name__]) > 100:
            self._handler_errors[handler.handler.__name__].pop(0)
    
    def get_event_history(
        self, 
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get recent event history.
        
        Args:
            event_type: Filter by event type
            source: Filter by event source
            limit: Maximum number of events to return
            
        Returns:
            List of recent events matching the filters
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if source:
            events = [e for e in events if e.source == source]
        
        return events[-limit:]
    
    def get_handler_errors(
        self,
        handler_name: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get recent handler errors.
        
        Args:
            handler_name: Filter by handler name
            
        Returns:
            Dictionary of handler errors
        """
        if handler_name:
            return {handler_name: self._handler_errors.get(handler_name, [])}
        return dict(self._handler_errors)
    
    def clear_history(self) -> None:
        """Clear event history and error logs."""
        self._event_history.clear()
        self._handler_errors.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics.
        
        Returns:
            Dictionary with event bus statistics
        """
        handler_count = sum(len(handlers) for handlers in self._handlers.values())
        event_types = list(self._handlers.keys())
        
        return {
            "total_handlers": handler_count,
            "event_types": len(event_types),
            "event_type_list": event_types,
            "events_in_history": len(self._event_history),
            "handlers_with_errors": len(self._handler_errors),
            "active_handlers": len(self._active_handlers)
        }


# Global event bus instance
event_bus = EventBus()


# Decorator for easy handler registration
def on_event(
    event_types: Union[str, List[str]],
    priority: EventPriority = EventPriority.NORMAL,
    plugin_name: Optional[str] = None
):
    """Decorator to register a function as an event handler.
    
    Usage:
        @on_event("turn.started")
        async def handle_turn_start(event: Event):
            # Handle the event
            pass
    
    Args:
        event_types: Event type(s) to handle
        priority: Handler priority
        plugin_name: Name of the plugin (auto-detected if not provided)
    """
    def decorator(func: Callable) -> Callable:
        # Try to auto-detect plugin name from module
        if plugin_name is None:
            module = inspect.getmodule(func)
            if module and "features" in module.__name__:
                # Extract plugin name from module path
                parts = module.__name__.split(".")
                if len(parts) > 2:
                    detected_name = parts[2]  # e.g., features.ceo_system.xxx -> ceo_system
                else:
                    detected_name = None
            else:
                detected_name = None
        else:
            detected_name = plugin_name
        
        event_bus.register(event_types, func, priority, detected_name)
        return func
    
    return decorator 