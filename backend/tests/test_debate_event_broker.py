from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Thread
from uuid import UUID

import pytest

from app.services.debate_event_broker import (
    DebateEventCursorExpired,
    InMemoryDebateEventBroker,
    format_debate_sse,
)


SESSION_A = UUID("00000000-0000-4000-8000-000000000401")
SESSION_B = UUID("00000000-0000-4000-8000-000000000402")
SESSION_C = UUID("00000000-0000-4000-8000-000000000403")


class DeterministicValues:
    def __init__(self) -> None:
        self.index = 0

    def clock(self) -> datetime:
        self.index += 1
        return datetime(2026, 8, 28, tzinfo=timezone.utc) + timedelta(
            seconds=self.index
        )

    def identifier(self) -> UUID:
        self.index += 1
        return UUID(int=self.index)


def build_broker(**overrides: object) -> InMemoryDebateEventBroker:
    values = DeterministicValues()
    return InMemoryDebateEventBroker(
        clock=values.clock,
        id_factory=values.identifier,
        **overrides,
    )


def test_publish_assigns_monotonic_per_session_sequences_and_replays_after_cursor() -> None:
    broker = build_broker()
    created = broker.publish(SESSION_A, "session.created", payload={"ticker": "AAPL"})
    queued = broker.publish(SESSION_A, "job.queued", payload={"job_id": "job-1"})
    other = broker.publish(SESSION_B, "session.created", payload={"ticker": "GOOG"})

    assert (created.sequence, queued.sequence, other.sequence) == (1, 2, 1)
    assert broker.replay(SESSION_A, after_sequence=1) == (queued,)
    assert broker.latest_sequence(SESSION_A) == 2


def test_event_buffers_are_bounded_and_report_an_expired_cursor() -> None:
    broker = build_broker(max_events_per_session=2)
    broker.publish(SESSION_A, "session.created")
    second = broker.publish(SESSION_A, "job.queued")
    third = broker.publish(SESSION_A, "job.started")

    with pytest.raises(DebateEventCursorExpired, match="predates"):
        broker.replay(SESSION_A, after_sequence=0)
    assert broker.replay(SESSION_A, after_sequence=1) == (second, third)


def test_wait_for_events_unblocks_when_an_event_is_published() -> None:
    broker = build_broker()
    received: list[object] = []

    waiter = Thread(
        target=lambda: received.extend(
            broker.wait_for_events(SESSION_A, after_sequence=0, timeout=1.0)
        )
    )
    waiter.start()
    published = broker.publish(SESSION_A, "turn.started", payload={"role": "bull"})
    waiter.join(timeout=1.0)

    assert not waiter.is_alive()
    assert received == [published]


def test_heartbeat_is_unbuffered_and_does_not_advance_resume_cursor() -> None:
    broker = build_broker()
    broker.publish(SESSION_A, "session.created")

    heartbeat = broker.heartbeat(SESSION_A)

    assert heartbeat.type == "heartbeat"
    assert heartbeat.sequence == 1
    assert broker.latest_sequence(SESSION_A) == 1
    assert len(broker.replay(SESSION_A)) == 1
    frame = format_debate_sse(heartbeat)
    assert frame.startswith("event: heartbeat\n")
    assert "id:" not in frame


def test_sse_frame_uses_sequence_as_resume_id_and_embeds_versioned_json() -> None:
    broker = build_broker()
    event = broker.publish(
        SESSION_A,
        "turn.delta",
        payload={"generation_id": "generation-1", "delta": "bounded text"},
    )

    frame = format_debate_sse(event)

    assert frame.startswith("id: 1\nevent: turn.delta\ndata: ")
    assert '"version":1' in frame
    assert '"delta":"bounded text"' in frame
    assert frame.endswith("\n\n")


def test_session_capacity_evicts_the_least_recently_used_buffer() -> None:
    broker = build_broker(max_sessions=2)
    broker.publish(SESSION_A, "session.created")
    broker.publish(SESSION_B, "session.created")
    broker.replay(SESSION_A)
    broker.publish(SESSION_C, "session.created")

    assert broker.replay(SESSION_A)
    assert broker.replay(SESSION_B) == ()
    assert broker.replay(SESSION_C)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_events_per_session": 0}, "capacity per session"),
        ({"max_sessions": 0}, "session capacity"),
    ],
)
def test_broker_rejects_unbounded_invalid_capacities(
    kwargs: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_broker(**kwargs)
