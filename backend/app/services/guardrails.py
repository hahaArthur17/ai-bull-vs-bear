from __future__ import annotations

import re


DISCLAIMER = "This analysis is for educational purposes only and does not constitute financial advice."

REWRITES: dict[str, str] = {
    "you should buy": "you may wish to research",
    "you should sell": "you may wish to review",
    "you should hold": "you may wish to monitor",
    "strong buy": "strong positive signal",
    "guaranteed profit": "unverified outcome claim",
    "safe investment": "investment with uncertainty",
    "this is financial advice": "this is educational information",
}


def apply_guardrails(text: str) -> tuple[str, str, list[str]]:
    safe_text = text
    rewritten: list[str] = []
    for phrase, replacement in REWRITES.items():
        pattern = re.compile(re.escape(phrase), flags=re.IGNORECASE)
        if pattern.search(safe_text):
            rewritten.append(phrase)
            safe_text = pattern.sub(replacement, safe_text)
    status = "rewritten" if rewritten else "passed"
    if DISCLAIMER.lower() not in safe_text.lower():
        safe_text = f"{safe_text.rstrip()}\n\n{DISCLAIMER}"
    return safe_text, status, rewritten

