from __future__ import annotations

import threading
import time

from eng_loop.tools.cli_events import PipelineEvent, node_completed, node_started
from eng_loop.tools.event_bus import EventBus


class TestEventBus:
    def test_emit_and_receive(self):
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(handler)
        event = node_started("g-1", "init")
        bus.emit(event)

        assert len(received) == 1
        assert received[0] is event

    def test_multiple_subscribers(self):
        bus = EventBus()
        received_a = []
        received_b = []

        bus.subscribe(lambda e: received_a.append(e))
        bus.subscribe(lambda e: received_b.append(e))

        event = node_started("g-1", "init")
        bus.emit(event)

        assert len(received_a) == 1
        assert len(received_b) == 1

    def test_get_events(self):
        bus = EventBus()
        e1 = node_started("g-1", "init")
        e2 = node_completed("g-1", "init")
        bus.emit(e1)
        bus.emit(e2)

        events = bus.get_events()
        assert len(events) == 2
        assert events[0] is e1
        assert events[1] is e2

    def test_get_events_since_index(self):
        bus = EventBus()
        bus.emit(node_started("g-1", "init"))
        bus.emit(node_started("g-1", "impl.code"))
        e3 = node_completed("g-1", "init")
        bus.emit(e3)

        events = bus.get_events(since_index=2)
        assert len(events) == 1
        assert events[0] is e3

    def test_event_count(self):
        bus = EventBus()
        assert bus.event_count == 0
        bus.emit(node_started("g-1", "init"))
        assert bus.event_count == 1
        bus.emit(node_completed("g-1", "init"))
        assert bus.event_count == 2

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)

        bus.subscribe(handler)
        bus.emit(node_started("g-1", "init"))
        bus.unsubscribe(handler)
        bus.emit(node_completed("g-1", "init"))

        assert len(received) == 1

    def test_clear(self):
        bus = EventBus()
        received = []
        bus.subscribe(lambda e: received.append(e))
        bus.emit(node_started("g-1", "init"))
        bus.clear()

        assert bus.event_count == 0
        bus.emit(node_completed("g-1", "init"))
        assert len(received) == 1  # subscriber removed by clear

    def test_subscriber_exception_doesnt_crash(self):
        bus = EventBus()
        results = []

        def bad_handler(event):
            raise ValueError("boom")

        def good_handler(event):
            results.append(event)

        bus.subscribe(bad_handler)
        bus.subscribe(good_handler)

        event = node_started("g-1", "init")
        bus.emit(event)  # Should not raise

        assert len(results) == 1

    def test_thread_safety(self):
        bus = EventBus()
        received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                received.append(event)

        bus.subscribe(handler)

        def emit_events():
            for i in range(50):
                bus.emit(node_started("g-1", f"node-{i}"))

        threads = [threading.Thread(target=emit_events) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(received) == 200
