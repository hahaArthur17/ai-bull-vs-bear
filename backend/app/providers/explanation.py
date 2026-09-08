from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.explanations import ExplanationAgentRequest, ExplanationDraft


@runtime_checkable
class ExplanationProvider(Protocol):
    name: str
    version: str

    def generate_explanation(
        self,
        request: ExplanationAgentRequest,
    ) -> ExplanationDraft:
        ...

    def close(self) -> None:
        ...


class DeterministicExplanationProvider:
    """Credential-free provider for the first Explanation service boundary."""

    name = "deterministic-explainer"
    version = "v1"

    def close(self) -> None:
        """Keep the provider lifecycle uniform without allocating a client."""

    def generate_explanation(
        self,
        request: ExplanationAgentRequest,
    ) -> ExplanationDraft:
        role = request.source_message.role.capitalize()
        evidence_note = (
            "The source message links to frozen evidence, but that evidence remains dated "
            "and incomplete."
            if request.allowed_evidence_ids
            else "The source message has no linked evidence, so this explanation is limited."
        )
        return ExplanationDraft(
            content=(
                f'Here, "{request.selected_text}" appears in a complete {role} message. '
                "Read it only within that message and the session's frozen factor/evidence "
                "snapshot; it does not establish causation or predict a future return. "
                f"{evidence_note} The user's question was: {request.question}"
            ),
            evidence_ids=tuple(sorted(request.allowed_evidence_ids)),
            terms=(request.selected_text,) if len(request.selected_text) <= 100 else (),
        )
