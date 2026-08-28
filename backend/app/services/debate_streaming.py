from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.agents import (
    DebateTurnDraft,
    DebateTurnRequest,
    DebateTurnStreamDelta,
    DebateTurnStreamUsage,
)
from app.providers.debate_agents import DebateStreamingTurnProvider


class DebateTurnStreamError(RuntimeError):
    """A provider stream cannot safely become a canonical complete message."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class CollectedDebateTurn:
    draft: DebateTurnDraft
    usage: DebateTurnStreamUsage
    delta_count: int


async def collect_debate_turn_stream(
    provider: DebateStreamingTurnProvider,
    request: DebateTurnRequest,
    *,
    on_delta: Callable[[DebateTurnStreamDelta], Awaitable[None]] | None = None,
) -> CollectedDebateTurn:
    """Validate one async provider stream before canonical persistence."""

    deltas: list[str] = []
    expected_chunk_index = 1
    completion = None
    try:
        async for event in provider.stream_turn(request):
            if completion is not None:
                raise DebateTurnStreamError("Turn stream emitted data after completion")
            if event.kind == "delta":
                if event.chunk_index != expected_chunk_index:
                    raise DebateTurnStreamError("Turn stream chunks are not contiguous")
                expected_chunk_index += 1
                deltas.append(event.delta)
                if sum(len(delta) for delta in deltas) > request.max_output_chars:
                    raise DebateTurnStreamError("Turn stream exceeded its output bound")
                if on_delta is not None:
                    await on_delta(event)
            else:
                completion = event
    except DebateTurnStreamError:
        raise
    except Exception as exc:
        retryable = bool(getattr(exc, "retryable", False))
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if (
            not retryable
            or not isinstance(retry_after_seconds, int)
            or isinstance(retry_after_seconds, bool)
            or not 1 <= retry_after_seconds <= 3600
        ):
            retry_after_seconds = None
        raise DebateTurnStreamError(
            "Turn provider stream failed",
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
        ) from exc

    if completion is None:
        raise DebateTurnStreamError("Turn stream ended without a completion")
    if completion.finish_reason != "stop":
        raise DebateTurnStreamError("Turn stream did not finish normally")
    if not deltas:
        raise DebateTurnStreamError("Turn stream completed without text deltas")
    streamed_content = "".join(deltas)
    if streamed_content != completion.draft.content:
        raise DebateTurnStreamError("Turn stream text does not match its completed draft")
    if len(completion.draft.content) > request.max_output_chars:
        raise DebateTurnStreamError("Completed turn exceeded its output bound")
    if completion.draft.responds_to_message_id != request.rebuttal_target_message_id:
        raise DebateTurnStreamError("Completed turn used the wrong rebuttal target")
    if any(
        evidence_id not in request.allowed_evidence_ids
        for evidence_id in completion.draft.evidence_ids
    ):
        raise DebateTurnStreamError("Completed turn cited evidence outside the snapshot")
    return CollectedDebateTurn(
        draft=completion.draft,
        usage=completion.usage,
        delta_count=len(deltas),
    )
