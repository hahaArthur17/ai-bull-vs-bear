from app.services.source_attribution import SourceAttributionBuffer, sanitize_source_sentence


EXCERPTS = {
    "[E1]": "A dated article announces a new camera feature without reporting sales.",
    "[E4]": (
        "This Form 10-Q contains forward-looking statements that involve risks and "
        "uncertainties. The statements concern macroeconomic conditions and tariffs."
    ),
}


def test_false_filing_attribution_is_replaced_without_losing_its_alias() -> None:
    sentence = (
        "[E4] The 10-Q states that Apple's ecosystem strategy historically amplified "
        "revenue from camera upgrades. "
    )

    safe, changed = sanitize_source_sentence(sentence, EXCERPTS)

    assert changed is True
    assert safe == "[E4] The supplied excerpt does not verify that source-specific claim. "
    assert "ecosystem" not in safe


def test_alias_at_the_end_is_retained_for_the_evidence_limitation() -> None:
    safe, changed = sanitize_source_sentence(
        "The filing states that camera revenue rose [E4].", EXCERPTS
    )

    assert changed is True
    assert safe == "[E4] The supplied excerpt does not verify that source-specific claim."


def test_exact_quote_must_match_the_cited_excerpt() -> None:
    supported = (
        '[E4] The filing states: "forward-looking statements that involve risks and '
        'uncertainties". '
    )
    wrong_alias = supported.replace("[E4]", "[E1]")
    extra_wrong_alias = supported.replace("[E4]", "[E1] [E4]")

    assert sanitize_source_sentence(supported, EXCERPTS) == (supported, False)
    assert sanitize_source_sentence(wrong_alias, EXCERPTS)[1] is True
    assert sanitize_source_sentence(extra_wrong_alias, EXCERPTS)[1] is True


def test_quote_does_not_authorize_an_extra_unsupported_claim() -> None:
    sentence = (
        '[E4] The filing states that camera revenue rose and notes: '
        '"forward-looking statements that involve risks and uncertainties". '
    )

    safe, changed = sanitize_source_sentence(sentence, EXCERPTS)

    assert changed is True
    assert "camera revenue rose" not in safe


def test_alias_does_not_authorize_an_unverified_quotation_without_source_noun() -> None:
    sentence = '[E1] The creator update “further enhanced the creative suite” for users.'

    safe, changed = sanitize_source_sentence(sentence, EXCERPTS)

    assert changed is True
    assert 'further enhanced the creative suite' not in safe


def test_rebuttal_may_quote_the_opponent_without_claiming_a_source_quote() -> None:
    sentence = '[E1] The Bull claimed “higher creator demand will lift hardware sales”, but that remains unmeasured.'

    assert sanitize_source_sentence(sentence, EXCERPTS) == (sentence, False)


def test_negated_first_clause_does_not_hide_a_later_positive_attribution() -> None:
    sentence = (
        "[E4] The 10-Q does not merely warn of uncertainty; it also notes that "
        "camera upgrades amplified revenue."
    )

    assert sanitize_source_sentence(sentence, EXCERPTS)[1] is True


def test_attributed_statement_noun_is_not_treated_as_evidence() -> None:
    sentence = "The outcome is grounded in the 10-Q's ecosystem statement [E4]."

    assert sanitize_source_sentence(sentence, EXCERPTS)[1] is True


def test_unsupported_historical_sales_pattern_is_not_repeated() -> None:
    sentence = (
        "[E1] Past camera upgrades correlated with accessory and App Store revenue growth."
    )

    safe, changed = sanitize_source_sentence(sentence, EXCERPTS)

    assert changed is True
    assert "correlated" not in safe
    assert "historical performance claim" in safe


def test_missing_historical_data_is_allowed_as_a_limitation() -> None:
    sentence = "[E1] No historical revenue data are supplied here."

    assert sanitize_source_sentence(sentence, EXCERPTS) == (sentence, False)


def test_unsourced_measured_number_is_replaced_but_conditional_number_remains() -> None:
    observed = "[E1] The 12-MP upgrade increased sales by 5%."
    conditional = "[E1] If shipments rose 5%, revenue could improve."

    safe, changed = sanitize_source_sentence(observed, EXCERPTS)

    assert changed is True
    assert "12-MP" not in safe
    assert "numerical claim" in safe
    assert sanitize_source_sentence(conditional, EXCERPTS) == (conditional, False)


def test_inference_and_missing_evidence_statements_remain_available() -> None:
    inference = "[E1] The feature might lift demand, but the outcome is uncertain. "
    limitation = "The cited excerpt does not show a revenue increase. "

    assert sanitize_source_sentence(inference, EXCERPTS) == (inference, False)
    assert sanitize_source_sentence(limitation, EXCERPTS) == (limitation, False)


def test_stream_buffer_holds_an_unverified_attribution_across_chunks() -> None:
    buffer = SourceAttributionBuffer(EXCERPTS)

    assert buffer.push("[E4] The 10-Q states that camera ") == ""
    assert buffer.push("sales rose. A separate inference ") == (
        "[E4] The supplied excerpt does not verify that source-specific claim. "
    )
    assert buffer.finish() == "A separate inference "
    assert buffer.replacements == 1


def test_repeated_warning_for_the_same_evidence_is_shown_once() -> None:
    buffer = SourceAttributionBuffer(EXCERPTS)
    output = buffer.push(
        "[E4] The filing states that camera sales rose. "
        "[E4] The filing notes that valuation also rose. "
        "Demand remains uncertain. "
    ) + buffer.finish()

    assert output.count("does not verify") == 1
    assert "Demand remains uncertain" in output
    assert buffer.replacements == 2


def test_unattributed_warning_is_not_repeated_after_an_evidence_warning() -> None:
    buffer = SourceAttributionBuffer(EXCERPTS)
    output = buffer.push(
        "[E4] The filing states that camera sales rose. "
        "The document says valuation rose too. "
    ) + buffer.finish()

    assert output.count("does not verify") == 1
    assert buffer.replacements == 2


def test_pronoun_cannot_attribute_a_debate_quote_to_the_previous_excerpt() -> None:
    buffer = SourceAttributionBuffer(EXCERPTS)
    output = buffer.push(
        'The excerpt does not report camera sales. It merely states that "camera sales rose". '
    ) + buffer.finish()

    assert 'It merely states' not in output
    assert 'camera sales rose"' not in output
    assert buffer.replacements == 1


def test_stream_removes_literal_markdown_bold_labels_from_plain_prose() -> None:
    buffer = SourceAttributionBuffer(EXCERPTS)

    output = buffer.push("[E1] **Bull claim** – Demand may improve. ") + buffer.finish()

    assert output == "[E1] Bull claim – Demand may improve. "
