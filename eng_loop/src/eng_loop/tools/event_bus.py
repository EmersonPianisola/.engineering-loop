from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from eng_loop.tools.trace_logger import trace as _trace

if TYPE_CHECKING:
    from eng_loop.tools.cli_events import PipelineEvent


def _event_bus_trace_handler(event: PipelineEvent) -> None:
    """Subscribe to event bus and forward events to trace logger.

    NOTE: stage_enter is now emitted only by trace_node (the handler decorator).
    The event bus no longer emits stage_enter to avoid duplicate ENTER events.
    """
    event_type = event.event_type
    if event_type.startswith("node."):
        _trace.system_event(
            event_type,
            node_id=event.node_id,
            message=event.message,
            status=event.status,
        )
    elif event_type.startswith("planning."):
        _trace.system_event(event_type, message=event.message, metadata=event.metadata)
    elif event_type.startswith("pipeline."):
        _trace.system_event(event_type, message=event.message)
    elif event_type.startswith("gate."):
        _trace.system_event(event_type, node_id=event.node_id, message=event.message)
    elif event_type.startswith("checkpoint."):
        _trace.system_event(event_type, message=event.message, metadata=event.metadata)
    elif event_type.startswith("diagnostic."):
        severity = event.status
        if severity in ("error", "fatal"):
            _trace.system_event(event_type, node_id=event.node_id, message=event.message)


class EventBus:
    """Lightweight, thread-safe pub-sub event bus.

    Events are stored in-memory and delivered to subscribers synchronously.
    Subscribers are expected to be non-blocking.
    """

    def __init__(self) -> None:
        self._events: list[PipelineEvent] = []
        self._subscribers: list[Callable[[PipelineEvent], None]] = [_event_bus_trace_handler]
        self._lock = threading.RLock()

    def emit(self, event: PipelineEvent) -> None:
        """Publish an event. Stored and delivered to all subscribers."""
        with self._lock:
            self._events.append(event)
            for subscriber in self._subscribers:
                try:
                    subscriber(event)
                except Exception:
                    # Subscribers must not crash the pipeline
                    pass

    def subscribe(self, handler: Callable[[PipelineEvent], None]) -> None:
        """Register a callback for all future events."""
        with self._lock:
            self._subscribers.append(handler)

    def unsubscribe(self, handler: Callable[[PipelineEvent], None]) -> None:
        """Remove a previously registered handler."""
        with self._lock:
            if handler in self._subscribers:
                self._subscribers.remove(handler)

    def get_events(self, since_index: int = 0) -> list[PipelineEvent]:
        """Return events published since the given index."""
        with self._lock:
            return list(self._events[since_index:])

    def get_all_events(self) -> list[PipelineEvent]:
        """Return all published events."""
        with self._lock:
            return list(self._events)

    @property
    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def clear(self) -> None:
        """Clear all stored events (for testing)."""
        with self._lock:
            self._events.clear()
            if self._subscribers and self._subscribers[0] is _event_bus_trace_handler:
                self._subscribers = []
            else:
                self._subscribers.clear()
