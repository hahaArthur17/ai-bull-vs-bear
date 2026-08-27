from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.agents import (
    DebateJudgeDraft,
    DebateJudgeRequest,
    DebateTurnDraft,
    DebateTurnRequest,
)


@runtime_checkable
class DebateTurnProvider(Protocol):
    name: str
    version: str

    def generate_turn(self, request: DebateTurnRequest) -> DebateTurnDraft:
        """Generate one bounded turn; streaming support is added in Phase 4."""

        ...


@runtime_checkable
class DebateJudgeProvider(Protocol):
    name: str
    version: str

    def generate_judgement(self, request: DebateJudgeRequest) -> DebateJudgeDraft:
        ...

