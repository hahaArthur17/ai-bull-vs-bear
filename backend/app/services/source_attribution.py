"""Conservative checks for source, historical-performance, and numeric claims.

An evidence alias proves that an excerpt was supplied, not that arbitrary prose is
in that excerpt. Direct source descriptions and measured performance claims need
a short verbatim quote. Conditional interpretations remain available.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping


_ALIAS = re.compile(r"\[E[1-9][0-9]?\]")
_QUOTE = re.compile(r'["“]([^"”]{20,})["”]')
_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+|\n{2,}")
_SOURCE = re.compile(
    r"\b(?:10[-‑–—]?q|filing|article|report|document|excerpt|source|evidence|"
    r"risk disclosures)\b",
    re.IGNORECASE,
)
_ASSERTION = re.compile(
    r"\b(?:says?|states?|notes?|warns?|cautions?|reports?|confirms?|shows?|"
    r"highlights?|acknowledg(?:es|ements?)|discuss(?:es|ed)|provides?|"
    r"documents?|mentions?|contains?|indicates?|establishes?|supplies?|"
    r"announc(?:es|ing)|stresses?)\b",
    re.IGNORECASE,
)
_ATTRIBUTED_NOUN = re.compile(
    r"\b(?:statement|acknowledg(?:e)?ment|disclosure|assertion|claim)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(?:do not|does not|did not|is not|was not|cannot|can't|no)\b",
    re.IGNORECASE,
)
_HISTORICAL_PERFORMANCE = re.compile(
    r"\b(?:historical(?:ly)?|past|prior|previous|earlier)\b.{0,130}"
    r"\b(?:correlat\w*|sales|revenue|demand|earnings|performance|lift|growth|"
    r"increas\w*|surge)\b",
    re.IGNORECASE,
)
_METRIC = re.compile(
    r"\b\d+(?:[.,]\d+)?[\s-]*(?:%|percent\b|mp\b|million\b|billion\b|"
    r"bps\b|basis points\b)",
    re.IGNORECASE,
)
_HYPOTHETICAL_PREFIX = re.compile(
    r"^\s*(?:\[E[1-9][0-9]?\]\s*)*(?:if|suppose|assume|hypothetically)\b",
    re.IGNORECASE,
)
_PRONOUN_SOURCE_ASSERTION = re.compile(
    r"^\s*(?:\[E[1-9][0-9]?\]\s*)*(?:it|they|this)\s+"
    r"(?:[a-z]+\s+){0,2}"
    r"(?:says?|states?|notes?|reports?|confirms?|shows?|warns?|cautions?)\b",
    re.IGNORECASE,
)
_DEBATE_QUOTE = re.compile(r"\b(?:bull|bear|judge|opponent|debate agent)\b", re.IGNORECASE)
_BOLD_LABEL = re.compile(r"\*\*([^*\n]{1,60})\*\*")
_WRAPPER_WORDS = frozenset(
    "the this a an linked cited supplied apple apples sec 10 q filing article report "
    "document excerpt source evidence item 2 according to in from of says states "
    "reads notes reports that".split()
)
_SAFE_REPLACEMENT = "The supplied excerpt does not verify that source-specific claim."
_HISTORICAL_REPLACEMENT = "The supplied evidence does not verify that historical performance claim."
_METRIC_REPLACEMENT = "The supplied evidence does not verify that numerical claim."


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("’", "'").replace("‑", "-").replace("–", "-")
    return " ".join(value.split())


def _claims_source_support(sentence: str) -> bool:
    if _SAFE_REPLACEMENT in sentence:
        return False
    for source in _SOURCE.finditer(sentence):
        for assertion in _ASSERTION.finditer(sentence):
            if assertion.start() < source.end() and source.start() < assertion.end():
                continue
            if abs(assertion.start() - source.start()) > 160:
                continue
            between = sentence[min(source.end(), assertion.end()) : max(source.start(), assertion.start())]
            if not _NEGATION.search(between[-25:]):
                return True
        for noun in _ATTRIBUTED_NOUN.finditer(sentence, source.end()):
            between = sentence[source.end() : noun.start()]
            if noun.start() - source.end() <= 90 and not _NEGATION.search(between[-40:]):
                return True
    return False


def _has_supported_quote(sentence: str, excerpts: Mapping[str, str]) -> bool:
    aliases = {match.group(0) for match in _ALIAS.finditer(sentence)}
    if not aliases:
        return False
    quotes = list(_QUOTE.finditer(sentence))
    if len(quotes) != 1:
        return False
    quote = quotes[0]
    if len(quote.group(1).split()) < 4:
        return False
    prefix = _ALIAS.sub("", sentence[: quote.start()])
    suffix = _ALIAS.sub("", sentence[quote.end() :])
    if any(word not in _WRAPPER_WORDS for word in re.findall(r"[a-z0-9]+", prefix.casefold())):
        return False
    if re.sub(r"[\s.!?。！？,:;()\-]", "", suffix):
        return False
    quoted = _normalized(quote.group(1))
    return all(quoted in _normalized(excerpts.get(alias, "")) for alias in aliases)


def sanitize_source_sentence(
    sentence: str,
    excerpts: Mapping[str, str],
    *,
    source_context: bool = False,
) -> tuple[str, bool]:
    """Replace a claim that lacks a matching quote before it reaches the client."""

    if any(
        replacement in sentence
        for replacement in (_SAFE_REPLACEMENT, _HISTORICAL_REPLACEMENT, _METRIC_REPLACEMENT)
    ):
        return sentence, False
    historical = _HISTORICAL_PERFORMANCE.search(sentence)
    historical_claim = historical is not None and not _NEGATION.search(
        sentence[max(0, historical.start() - 25) : historical.start()]
    )
    source_claim = _claims_source_support(sentence) or bool(
        source_context and _PRONOUN_SOURCE_ASSERTION.search(sentence)
    )
    quoted_claim = bool(
        _ALIAS.search(sentence)
        and _QUOTE.search(sentence)
        and not _DEBATE_QUOTE.search(sentence)
    )
    metric_claim = bool(_METRIC.search(sentence)) and not _HYPOTHETICAL_PREFIX.search(sentence)
    if not (source_claim or historical_claim or metric_claim or quoted_claim) or _has_supported_quote(sentence, excerpts):
        return sentence, False
    leading = re.match(r"\s*(?:\[E[1-9][0-9]?\]\s*)*", sentence)
    assert leading is not None
    prefix = leading.group(0)
    if not _ALIAS.search(prefix):
        aliases = tuple(dict.fromkeys(_ALIAS.findall(sentence)))
        if aliases:
            prefix = f"{prefix}{' '.join(aliases)} "
    trailing = sentence[len(sentence.rstrip()) :]
    if source_claim or quoted_claim:
        replacement = _SAFE_REPLACEMENT
    elif historical_claim:
        replacement = _HISTORICAL_REPLACEMENT
    else:
        replacement = _METRIC_REPLACEMENT
    return f"{prefix}{replacement}{trailing}", True


class SourceAttributionBuffer:
    """Hold a partial sentence until its evidence claims can be checked."""

    def __init__(self, excerpts: Mapping[str, str]) -> None:
        self.excerpts = excerpts
        self.pending = ""
        self.replacements = 0
        self._warned_aliases: set[str] = set()
        self._warned_any = False
        self._previous_mentions_source = False

    def _process(self, sentence: str) -> str:
        safe, changed = sanitize_source_sentence(
            sentence,
            self.excerpts,
            source_context=self._previous_mentions_source,
        )
        self._previous_mentions_source = bool(
            _SOURCE.search(sentence) or _PRONOUN_SOURCE_ASSERTION.search(sentence)
        )
        if not changed:
            return _BOLD_LABEL.sub(r"\1", safe)
        self.replacements += 1
        aliases = set(_ALIAS.findall(safe))
        if (aliases and aliases <= self._warned_aliases) or (not aliases and self._warned_any):
            return "\n\n" if "\n\n" in sentence else ""
        self._warned_aliases.update(aliases)
        self._warned_any = True
        return safe

    def push(self, delta: str) -> str:
        self.pending += delta
        output = ""
        while match := _BOUNDARY.search(self.pending):
            sentence, self.pending = self.pending[: match.end()], self.pending[match.end() :]
            output += self._process(sentence)
        return output

    def finish(self) -> str:
        safe = self._process(self.pending)
        self.pending = ""
        return safe


class CanonicalStreamBuffer:
    """Emit stable text while retaining whitespace a canonical model would strip."""

    def __init__(self) -> None:
        self._pending_whitespace = ""
        self._started = False

    def push(self, segment: str) -> str:
        combined = self._pending_whitespace + segment
        if not self._started:
            combined = combined.lstrip()
        stable = combined.rstrip()
        self._pending_whitespace = combined[len(stable) :]
        if stable:
            self._started = True
        return stable


def sanitize_context_text(text: str, excerpts: Mapping[str, str]) -> str:
    """Keep an old agent's unsupported source claim out of a new model prompt."""

    buffer = SourceAttributionBuffer(excerpts)
    return buffer.push(text) + buffer.finish()
