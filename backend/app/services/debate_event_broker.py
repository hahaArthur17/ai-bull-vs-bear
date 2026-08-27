from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Condition, RLock
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from pydantic import JsonValue

from app.domain.events import DebateEvent, DebateEventType


class DebateEventCursorExpired(ValueError):
    """The requested transient cursor predates the bounded in-memory buffer."""


@runtime_checkable
class DebateEventPublisher(Protocol):
    def publish(
        self,
        session_id: UUID,
        event_type: DebateEventType,
        *,
        payload: dict[str, JsonValue] | None = None,
        timestamp: datetime | None = None,
    ) -> DebateEvent:
        ...


class InMemoryDebateEventBroker:
    """Thread-safe, bounded event fan-out for one API process.

    Complete messages remain canonical in the Debate repository. This broker is
    intentionally transient and can be replaced by another process-local
    implementation without changing the orchestrator event contract.
    """

    def __init__(
        self,
        *,
        max_events_per_session: int = 256,
        max_sessions: int = 128,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        if max_events_per_session < 1:
            raise ValueError("Event capacity per session must be positive")
        if max_sessions < 1:
            raise ValueError("Event session capacity must be positive")
        self.max_events_per_session = max_events_per_session
        self.max_sessions = max_sessions
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or uuid4
        self._events: dict[UUID, deque[DebateEvent]] = {}
        self._next_sequences: dict[UUID, int] = {}
        self._session_lru: OrderedDict[UUID, None] = OrderedDict()
        self._condition = Condition(RLock())

    def publish(
        self,
        session_id: UUID,
        event_type: DebateEventType,
        *,
        payload: dict[str, JsonValue] | None = None,
        timestamp: datetime | None = None,
    ) -> DebateEvent:
        with self._condition:
            self._ensure_session(session_id)
            sequence = self._next_sequences[session_id]
            event = DebateEvent(
                event_id=self.id_factory(),
                session_id=session_id,
                sequence=sequence,
                type=event_type,
                timestamp=timestamp or self.clock(),
                payload=payload or {},
            )
            self._events[session_id].append(event)
            self._next_sequences[session_id] = sequence + 1
            self._touch(session_id)
            self._condition.notify_all()
            return event

    def replay(
        self,
        session_id: UUID,
        *,
        after_sequence: int = 0,
    ) -> tuple[DebateEvent, ...]:
        if after_sequence < 0:
            raise ValueError("Event cursor cannot be negative")
        with self._condition:
            return self._replay_locked(session_id, after_sequence)

    def wait_for_events(
        self,
        session_id: UUID,
        *,
        after_sequence: int,
        timeout: float,
    ) -> tuple[DebateEvent, ...]:
        if timeout < 0:
            raise ValueError("Event wait timeout cannot be negative")
        if after_sequence < 0:
            raise ValueError("Event cursor cannot be negative")
        with self._condition:
            available = self._replay_locked(session_id, after_sequence)
            if available or timeout == 0:
                return available
            self._condition.wait_for(
                lambda: self._has_event_after(session_id, after_sequence),
                timeout=timeout,
            )
            return self._replay_locked(session_id, after_sequence)

    def heartbeat(self, session_id: UUID) -> DebateEvent:
        """Create an unbuffered control event without advancing the cursor."""

        with self._condition:
            latest_sequence = self._next_sequences.get(session_id, 1) - 1
            return DebateEvent(
                event_id=self.id_factory(),
                session_id=session_id,
                sequence=latest_sequence,
                type="heartbeat",
                timestamp=self.clock(),
                payload={"latest_sequence": latest_sequence},
            )

    def latest_sequence(self, session_id: UUID) -> int:
        with self._condition:
            return self._next_sequences.get(session_id, 1) - 1

    def _ensure_session(self, session_id: UUID) -> None:
        if session_id in self._events:
            return
        while len(self._events) >= self.max_sessions:
            evicted_session_id, _ = self._session_lru.popitem(last=False)
            self._events.pop(evicted_session_id, None)
            self._next_sequences.pop(evicted_session_id, None)
        self._events[session_id] = deque(maxlen=self.max_events_per_session)
        self._next_sequences[session_id] = 1
        self._session_lru[session_id] = None

    def _touch(self, session_id: UUID) -> None:
        if session_id in self._session_lru:
            self._session_lru.move_to_end(session_id)

    def _replay_locked(
        self,
        session_id: UUID,
        after_sequence: int,
    ) -> tuple[DebateEvent, ...]:
        events = self._events.get(session_id)
        if not events:
            return ()
        oldest_sequence = events[0].sequence
        if after_sequence < oldest_sequence - 1:
            raise DebateEventCursorExpired(
                "Event cursor predates the transient replay buffer"
            )
        self._touch(session_id)
        return tuple(event for event in events if event.sequence > after_sequence)

    def _has_event_after(self, session_id: UUID, after_sequence: int) -> bool:
        events = self._events.get(session_id)
        return bool(events and events[-1].sequence > after_sequence)


def format_debate_sse(event: DebateEvent) -> str:
    """Encode one versioned event as a standards-compatible SSE frame."""

    event_id = "" if event.type == "heartbeat" else f"id: {event.sequence}\n"
    return (
        f"{event_id}event: {event.type}\n"
        f"data: {event.model_dump_json()}\n\n"
    )
