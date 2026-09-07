from __future__ import annotations

from app.domain.agents import (
    DebateJudgeDraft,
    DebateJudgeRequest,
    DebateTurnDraft,
    DebateTurnRequest,
)


class DeterministicDebateProvider:
    """Credential-free provider that exercises the real multi-turn contracts."""

    name = "deterministic-debate"
    version = "v1"

    def generate_turn(self, request: DebateTurnRequest) -> DebateTurnDraft:
        evidence_ids = tuple(sorted(request.allowed_evidence_ids))[:2]
        role_label = request.role.capitalize()
        factor_count = len(request.factor_snapshot.observations)
        if request.rebuttal_target_message_id is None:
            content = (
                f"{role_label} opening for {request.ticker}: the frozen snapshot contains "
                f"{factor_count} normalized factor observations. This is one conditional, "
                "educational interpretation rather than a prediction or trading instruction."
            )
            rebuttal_point = None
        else:
            opponent = "Bear" if request.role == "bull" else "Bull"
            latest_opponent = next(
                message
                for message in reversed(request.transcript)
                if message.id == request.rebuttal_target_message_id
            )
            intervention = (
                f" The user's challenge is: {request.user_intervention}"
                if request.user_intervention
                else ""
            )
            content = (
                f"{role_label} rebuttal to the latest {opponent} message: "
                f"“{latest_opponent.content[:180]}” The same dated snapshot can support a "
                "different interpretation because the signals are conditional and incomplete."
                f"{intervention}"
            )
            rebuttal_point = "The opponent's interpretation is not the only reading of the snapshot."

        return DebateTurnDraft(
            content=content,
            interpretation=(
                f"The {role_label} view assigns conditional "
                f"{'supportive' if request.role == 'bull' else 'cautionary'} meaning to the "
                "frozen evidence and factor snapshot."
            ),
            evidence_ids=evidence_ids,
            responds_to_message_id=request.rebuttal_target_message_id,
            rebuttal_point=rebuttal_point,
            confidence="low" if not evidence_ids else "medium",
            signal_strength="weak" if factor_count == 0 else "medium",
            risk_meaning=(
                "The evidence is incomplete and may become stale; this argument does not imply "
                "a future return or a suitable action."
            ),
            terms=("factor snapshot", "signal strength"),
        )

    def generate_judgement(self, request: DebateJudgeRequest) -> DebateJudgeDraft:
        evidence_ids = tuple(sorted(request.allowed_evidence_ids))[:4]
        bull_count = sum(message.role == "bull" for message in request.transcript)
        bear_count = sum(message.role == "bear" for message in request.transcript)
        phase_label = "Interim" if request.phase == "interim" else "Final"
        return DebateJudgeDraft(
            summary=(
                f"{phase_label} Judge summary: the active branch contains {bull_count} Bull and "
                f"{bear_count} Bear messages grounded in one frozen snapshot. The arguments "
                "remain competing interpretations, not proof of causation or investment advice."
            ),
            interpretation=(
                "The neutral assessment weighs the two competing readings without treating "
                "either side as proof of a future outcome."
            ),
            agreements=("Both sides rely on the same dated analysis snapshot.",),
            disagreements=("The sides assign different meaning and weight to the same signals.",),
            missing_evidence=("Future information and unsupported causal claims remain unknown.",),
            evidence_ids=evidence_ids,
            evidence_strength="weak" if not evidence_ids else "medium",
            uncertainty=(
                "The snapshot is bounded and cannot establish what will happen next; new filings, "
                "prices, or macro observations may change the interpretation."
            ),
            risk_level="medium",
        )
