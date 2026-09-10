from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.agents import (
    DebateJudgeDraft,
    DebateJudgeRequest,
    DebateJudgeStreamDelta,
    DebateTurnDraft,
    DebateTurnRequest,
    DebateTurnStreamDelta,
    DebateTurnStreamUsage,
)
from app.providers.debate_agents import DebateStreamingJudgeProvider, DebateStreamingTurnProvider


class DebateTurnStreamError(RuntimeError):
    """A provider stream cannot safely become a canonical complete message."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
        usage: DebateTurnStreamUsage | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.usage = usage if isinstance(usage, DebateTurnStreamUsage) else None


@dataclass(frozen=True)
class CollectedDebateTurn:
    draft: DebateTurnDraft
    usage: DebateTurnStreamUsage
    delta_count: int


@dataclass(frozen=True)
class CollectedDebateJudge:
    draft: DebateJudgeDraft
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
    stream = provider.stream_turn(request)
    try:
        async for event in stream:
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
    except DebateTurnStreamError as exc:
        if completion is not None:
            exc.usage = completion.usage
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
            usage=completion.usage if completion is not None else getattr(exc, "usage", None),
        ) from exc

    finally:
        closer = getattr(stream, "aclose", None)
        if closer is not None:
            await closer()

    if completion is None:
        raise DebateTurnStreamError("Turn stream ended without a completion")
    if completion.finish_reason != "stop":
        raise DebateTurnStreamError("Turn stream did not finish normally", usage=completion.usage)
    if not deltas:
        raise DebateTurnStreamError("Turn stream completed without text deltas", usage=completion.usage)
    streamed_content = "".join(deltas)
    if streamed_content != completion.draft.content:
        raise DebateTurnStreamError("Turn stream text does not match its completed draft", usage=completion.usage)
    if len(completion.draft.content) > request.max_output_chars:
        raise DebateTurnStreamError("Completed turn exceeded its output bound", usage=completion.usage)
    if completion.draft.responds_to_message_id != request.rebuttal_target_message_id:
        raise DebateTurnStreamError("Completed turn used the wrong rebuttal target", usage=completion.usage)
    if any(
        evidence_id not in request.allowed_evidence_ids
        for evidence_id in completion.draft.evidence_ids
    ):
        raise DebateTurnStreamError("Completed turn cited evidence outside the snapshot", usage=completion.usage)
    return CollectedDebateTurn(
        draft=completion.draft,
        usage=completion.usage,
        delta_count=len(deltas),
    )


async def collect_debate_judge_stream(
    provider: DebateStreamingJudgeProvider,
    request: DebateJudgeRequest,
    *,
    on_delta: Callable[[DebateJudgeStreamDelta], Awaitable[None]] | None = None,
) -> CollectedDebateJudge:
    """Validate a Judge stream at the same persistence boundary as a turn stream."""

    deltas: list[str] = []
    expected_chunk_index = 1
    completion = None
    stream = provider.stream_judgement(request)
    try:
        async for event in stream:
            if completion is not None:
                raise DebateTurnStreamError("Judge stream emitted data after completion")
            if event.kind == "delta":
                if event.chunk_index != expected_chunk_index:
                    raise DebateTurnStreamError("Judge stream chunks are not contiguous")
                expected_chunk_index += 1
                deltas.append(event.delta)
                if sum(map(len, deltas)) > request.max_output_chars:
                    raise DebateTurnStreamError("Judge stream exceeded its output bound")
                if on_delta is not None:
                    await on_delta(event)
            else:
                completion = event
    except DebateTurnStreamError as exc:
        if completion is not None:
            exc.usage = completion.usage
        raise
    except Exception as exc:
        retryable = bool(getattr(exc, "retryable", False))
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if not (retryable and isinstance(retry_after_seconds, int) and not isinstance(retry_after_seconds, bool) and 1 <= retry_after_seconds <= 3600):
            retry_after_seconds = None
        raise DebateTurnStreamError(
            "Judge provider stream failed",
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
            usage=completion.usage if completion is not None else getattr(exc, "usage", None),
        ) from exc

    finally:
        closer = getattr(stream, "aclose", None)
        if closer is not None:
            await closer()

    if completion is None:
        raise DebateTurnStreamError("Judge stream ended without a completion")
    if completion.finish_reason != "stop":
        raise DebateTurnStreamError("Judge stream did not finish normally", usage=completion.usage)
    if not deltas:
        raise DebateTurnStreamError("Judge stream completed without text deltas", usage=completion.usage)
    if "".join(deltas) != completion.draft.summary:
        raise DebateTurnStreamError("Judge stream text does not match its completed draft", usage=completion.usage)
    if len(completion.draft.summary) > request.max_output_chars:
        raise DebateTurnStreamError("Completed Judge exceeded its output bound", usage=completion.usage)
    if any(evidence_id not in request.allowed_evidence_ids for evidence_id in completion.draft.evidence_ids):
        raise DebateTurnStreamError("Completed Judge cited evidence outside the snapshot", usage=completion.usage)
    return CollectedDebateJudge(completion.draft, completion.usage, len(deltas))
