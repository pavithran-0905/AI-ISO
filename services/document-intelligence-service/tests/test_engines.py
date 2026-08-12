"""Tests for the pure analysis engines.

No infrastructure: these are deterministic functions over text, which is
what makes them the fastest and densest tests in the suite.

**Several tests here name a specific defect.** Each was found by
hand-verifying the engine against a real document before any test existed,
and each names what went wrong so a future change that reintroduces it
fails against a stated reason rather than an opaque assertion.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.classification.classifier import (
    MIN_CONFIDENT_TERMS,
    ClassificationRule,
    ClassifierConfig,
    DocumentTemplate,
    classify,
    term_weight,
)
from app.entities.extractor import (
    CustomEntityPattern,
    ExtractionConfig,
    ExtractionSummary,
    distinct_values,
    extract_entities,
    group_by_kind,
    normalize,
)
from app.forms.extractor import (
    FieldRule,
    FormConfig,
    FormTemplate,
    extract_fields,
    extract_key_values,
    merge_pages,
    normalize_label,
)
from app.layout.analyzer import LayoutConfig, PositionedWord, analyze_text, analyze_words
from app.models.enums import (
    DocumentCategory,
    EntityKind,
    FormFieldKind,
    LayoutRegionKind,
    SummaryKind,
    TableExportFormat,
    ValidationOutcome,
)
from app.summarization.summarizer import (
    Summary,
    SummaryConfig,
    split_sections,
    summarize,
    summarize_many,
    top_terms,
)
from app.tables.extractor import (
    TableConfig,
    TableWord,
    export,
    extract_from_words,
    extract_tables,
    merge_continuation,
)
from app.translation.translator import (
    Glossary,
    GlossaryEntry,
    TranslationConfig,
    TranslationUnavailableError,
    detect_language,
    protect,
    restore,
    translate,
    translate_many,
)
from app.validation.engine import (
    Rule,
    ValidationConfig,
    ValidationReport,
    between,
    business_rule,
    completeness,
    dates_in_order,
    find_duplicate,
    matches,
    one_of,
    parse_date,
    required,
    shingles,
    similarity,
    validate,
    validate_many,
)

# ---- entity extraction -----------------------------------------------------------------


DOCUMENT = (
    "Incident Report INC-004821 was raised by Jane Okafor on 2026-03-14.\n"
    "Prepared for the change advisory board.\n"
    "Reach the on-call rota on +44 20 7946 0018 or at ops@example.com.\n"
    "The affected host is db-01.eu-west-1.internal at 10.42.7.19.\n"
    "The runbook lives at https://wiki.example.com/runbooks/payments.\n"
    "Spend was 240,000 dollars and the config is /etc/payments/pool.yaml.\n"
)


def test_entities_of_every_expected_kind_are_found() -> None:
    kinds = {entity.kind for entity in extract_entities(DOCUMENT)}
    for expected in (
        EntityKind.IDENTIFIER,
        EntityKind.PERSON,
        EntityKind.DATE,
        EntityKind.PHONE,
        EntityKind.EMAIL,
        EntityKind.HOSTNAME,
        EntityKind.IP_ADDRESS,
        EntityKind.URL,
    ):
        assert expected in kinds, f"{expected!s} was not extracted"


def test_a_phone_ending_a_sentence_is_still_a_phone() -> None:
    """The trailing guard once rejected every phone before a full stop.

    ``(?![\\w.])`` excluded the sentence's own period, so a document whose
    phone number ended a sentence yielded no phone at all -- which is most
    documents.
    """
    found = extract_entities("Call the rota on +44 20 7946 0018.")
    assert [e.kind for e in found].count(EntityKind.PHONE) == 1


def test_a_person_name_does_not_run_across_a_line_break() -> None:
    """``\\s`` matched newlines, producing "Jane Okafor\\nPrepared"."""
    people = [e.value for e in extract_entities(DOCUMENT) if e.kind is EntityKind.PERSON]
    assert people
    assert all("\n" not in name for name in people)


def test_a_bare_identifier_is_found_without_an_adjacent_label() -> None:
    """ "Incident Report INC-004821" has no ``ID:`` label before the code."""
    found = extract_entities("Incident Report INC-004821 is closed.")
    assert any(e.kind is EntityKind.IDENTIFIER and e.value == "INC-004821" for e in found)


def test_overlapping_matches_resolve_to_one_entity() -> None:
    """A URL contains a hostname; only the URL should survive."""
    found = extract_entities("See https://wiki.example.com/runbooks/payments today.")
    spans = [(e.start, e.end) for e in found]
    for left in spans:
        for right in spans:
            if left is not right:
                assert not (left[0] < right[1] and right[0] < left[1]), "spans overlap"


def test_normalize_strips_a_phone_to_its_digits() -> None:
    """Two renderings of the *same* international number collide.

    A national number and an international one are deliberately *not*
    collapsed: "(020) 7946 0018" is only the same number as
    "+44 20 7946 0018" if you already know the country, and this service is
    given no default region. Claiming they match would merge two tenants'
    unrelated numbers in :meth:`find_by_value`.
    """
    assert normalize(EntityKind.PHONE, "+44 20 7946 0018") == normalize(
        EntityKind.PHONE, "+44-20-7946-0018"
    )
    assert normalize(EntityKind.PHONE, "(020) 7946 0018") != normalize(
        EntityKind.PHONE, "+44 20 7946 0018"
    )


def test_distinct_values_deduplicates_on_the_normalised_form() -> None:
    text = "Hosts db-01.example.com and db-01.example.com and db-02.example.com."
    found = extract_entities(text)
    assert len(distinct_values(found, EntityKind.HOSTNAME)) == 2


def test_group_by_kind_buckets_in_document_order() -> None:
    grouped = group_by_kind(extract_entities(DOCUMENT))
    assert grouped
    for entities in grouped.values():
        assert [e.start for e in entities] == sorted(e.start for e in entities)


def test_a_configured_custom_pattern_outranks_the_built_in_guess() -> None:
    """The generic identifier pattern matched the same span at 0.86.

    Ranking overlaps on confidence alone therefore discarded the tenant's
    own configuration in favour of a built-in guess.
    """
    config = ExtractionConfig(
        custom_patterns=(CustomEntityPattern(name="ticket", pattern=r"TCK-\d{4}"),)
    )
    found = extract_entities("Ticket TCK-9182 is open.", config)
    assert any(e.custom_kind == "ticket" and e.value == "TCK-9182" for e in found)
    assert not any(e.kind is EntityKind.IDENTIFIER and e.value == "TCK-9182" for e in found)


def test_extraction_summary_reports_none_confidence_when_nothing_was_found() -> None:
    """0.0 would read as an extractor that found things and doubted them."""
    assert ExtractionSummary().mean_confidence is None
    assert ExtractionSummary(entities=list(extract_entities(DOCUMENT))).mean_confidence


def test_no_entities_in_empty_text() -> None:
    assert extract_entities("") == []
    assert extract_entities("   \n  ") == []


# ---- layout ------------------------------------------------------------------------


REPORT = (
    "Quarterly Capacity Report\n\n"
    "## Summary\n\n"
    "Capacity grew by eleven percent across the three production regions.\n\n"
    "Region        Nodes   CPU %\n"
    "eu-west-1     142     71\n"
    "us-east-1     318     83\n\n"
    "Figure 1: node counts by region.\n\n"
    "Signed: R. Mehta\n\n"
    "Page 4\n"
)


def test_layout_finds_a_title_heading_and_page_number() -> None:
    layout = analyze_text(REPORT)
    kinds = {region.kind for region in layout.regions}
    assert LayoutRegionKind.TITLE in kinds
    assert LayoutRegionKind.HEADING in kinds
    assert LayoutRegionKind.PAGE_NUMBER in kinds


def test_layout_regions_are_in_reading_order() -> None:
    layout = analyze_text(REPORT)
    orders = [region.reading_order for region in layout.regions]
    assert orders == sorted(orders)


def test_layout_detects_a_caption_and_a_signature() -> None:
    layout = analyze_text(REPORT)
    kinds = {region.kind for region in layout.regions}
    assert LayoutRegionKind.CAPTION in kinds
    assert LayoutRegionKind.SIGNATURE in kinds


def test_positioned_words_resolve_into_two_columns() -> None:
    """Each column needs ``min_column_words`` words to count as one.

    A page holding a dozen words is not a two-column layout; it is a page
    with a marginal note, and treating that as a column reorders the whole
    page around it.
    """
    words = [
        PositionedWord(text=f"left{index}", left=10.0, top=10.0 + index * 12, width=40, height=8)
        for index in range(10)
    ] + [
        PositionedWord(text=f"right{index}", left=320.0, top=10.0 + index * 12, width=40, height=8)
        for index in range(10)
    ]
    layout = analyze_words(words, page_number=1, page_width=600, page_height=800)
    assert layout.column_count == 2


def test_too_few_words_is_one_column_not_two() -> None:
    words = [
        PositionedWord(
            text=f"w{index}",
            left=10.0 + (index % 2) * 310,
            top=10.0 + index * 12,
            width=40,
            height=8,
        )
        for index in range(6)
    ]
    assert analyze_words(words, page_number=1, page_width=600, page_height=800).column_count == 1


def test_layout_of_empty_text_has_no_regions() -> None:
    assert analyze_text("").regions == []


def test_a_custom_band_configuration_is_honoured() -> None:
    tight = analyze_text(REPORT, config=LayoutConfig(header_band=0.01, footer_band=0.01))
    assert tight.regions


# ---- classification ------------------------------------------------------------------


CHANGE_FORM = (
    "CHANGE REQUEST FORM\n\n"
    "Change ID: CHG-004821\n"
    "Requested by: R. Mehta\n"
    "Target system: payments-api\n"
    "Risk level: high\n"
    "Rollback tested: yes\n\n"
    "[x] Customer-facing downtime expected\n"
    "[ ] Data migration required\n"
)

RUNBOOK = (
    "Payments API failover runbook\n\n"
    "Prerequisites\n"
    "You have the snapshot id and the on-call escalation path.\n\n"
    "Procedure\n"
    "1. Confirm the primary is unreachable from two availability zones.\n"
    "2. Promote the standby replica and verify the connection pool drains.\n"
    "3. If latency does not recover, escalate to the platform lead.\n\n"
    "Rollback\n"
    "Restore the previous container image and re-run the troubleshooting steps.\n"
)

LOG_TEXT = (
    "2024-03-11 04:21:11 INFO  starting payments-api 4.2.1\n"
    "2024-03-11 04:21:44 WARN  p99 latency 1841ms above threshold\n"
    "2024-03-11 04:22:02 ERROR PoolExhaustedException: no connections\n"
    "2024-03-11 04:22:19 INFO  rolling back to 4.2.0\n"
)

POLICY = (
    "Information Handling Policy\n\n"
    "1. Scope\n"
    "1.1 This policy shall apply to all personnel and contractors.\n"
    "1.2 Adherence is mandatory and enforcement is delegated to security.\n\n"
    "2. Requirements\n"
    "2.1 Confidential material must not be stored on personal devices.\n"
    "2.2 Any exception shall be recorded with the compliance function.\n"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (CHANGE_FORM, DocumentCategory.FORM),
        (RUNBOOK, DocumentCategory.RUNBOOK),
        (LOG_TEXT, DocumentCategory.LOG),
        (POLICY, DocumentCategory.POLICY),
    ],
)
def test_the_primary_category_is_correct(text: str, expected: DocumentCategory) -> None:
    result = classify(text)
    assert result.classifications
    assert result.classifications[0].category is expected
    assert result.classifications[0].is_primary is True


def test_log_lines_do_not_classify_as_a_form() -> None:
    """A timestamp reads as ``label: value`` without the digit guard."""
    labels = {c.category for c in classify(LOG_TEXT).classifications}
    assert DocumentCategory.FORM not in labels


def test_a_prose_sentence_with_a_colon_does_not_make_a_runbook_a_form() -> None:
    """ "Prerequisite: you have the snapshot id and the on-call path." once did."""
    labels = {c.category for c in classify(RUNBOOK).classifications}
    assert DocumentCategory.FORM not in labels


def test_one_generic_keyword_hit_is_not_confident() -> None:
    """ "Risk level" matched the single log term "level" at the 0.88 ceiling.

    It led on relative score because nothing else scored, and outranked the
    correct structural reading of the document as a form.
    """
    result = classify("The risk level of this change is acceptable to the board.")
    assert result.classifications
    assert all(c.confidence < 0.6 for c in result.classifications)
    assert MIN_CONFIDENT_TERMS > 1


def test_a_rule_outranks_every_other_method() -> None:
    rule = ClassificationRule(
        name="certificates",
        category=DocumentCategory.CERTIFICATE,
        required_terms=("certify",),
        route_to="compliance-queue",
    )
    result = classify(
        "This is to certify that the platform was assessed.",
        config=ClassifierConfig(rules=(rule,)),
    )
    assert result.classifications[0].category is DocumentCategory.CERTIFICATE
    assert "compliance-queue" in result.routes


def test_a_template_match_needs_the_field_labels() -> None:
    """Template matching cannot work without them, which is why the pipeline
    runs form extraction first."""
    template = DocumentTemplate(
        name="change-request",
        category=DocumentCategory.FORM,
        field_labels=("change id", "requested by", "risk level"),
        route_to="cab-queue",
    )
    without = classify(CHANGE_FORM, config=ClassifierConfig(templates=(template,)))
    assert "cab-queue" not in without.routes

    with_labels = classify(
        CHANGE_FORM,
        config=ClassifierConfig(templates=(template,)),
        field_labels=["change id", "requested by", "risk level"],
    )
    assert "cab-queue" in with_labels.routes
    assert with_labels.classifications[0].confidence > 0.9


def test_single_label_mode_returns_one_label() -> None:
    result = classify(CHANGE_FORM, config=ClassifierConfig(multi_label=False))
    assert len(result.classifications) == 1


def test_every_label_carries_its_rationale() -> None:
    for label in classify(RUNBOOK).classifications:
        assert label.rationale


def test_a_term_shared_between_two_categories_is_worth_less() -> None:
    """Computed from the table rather than hand-assigned."""
    assert term_weight("exception") < term_weight("runbook")


def test_empty_text_classifies_as_nothing() -> None:
    assert classify("").classifications == []


# ---- tables -------------------------------------------------------------------------


MARKDOWN_TABLE = (
    "| Change ID | System | Risk |\n"
    "| --------- | ------ | ---- |\n"
    "| CHG-004821 | payments-api | high |\n"
    "| CHG-004822 | billing-worker | medium |\n"
)

ALIGNED_TABLE = (
    "Region        Nodes   CPU %\n" "eu-west-1     142     71\n" "us-east-1     318     83\n"
)

PROSE_WITH_GAP = (
    "This is ordinary prose  with a stray double space in it.\n"
    "It continues for another line  and then stops.\n"
)


def test_a_markdown_table_is_extracted_with_its_header() -> None:
    tables = extract_tables(MARKDOWN_TABLE)
    assert len(tables) == 1
    assert tables[0].headers == ["Change ID", "System", "Risk"]
    assert tables[0].row_count == 2
    assert tables[0].has_header_row is True


def test_a_whitespace_aligned_table_is_extracted() -> None:
    tables = extract_tables(ALIGNED_TABLE)
    assert len(tables) == 1
    assert tables[0].headers == ["Region", "Nodes", "CPU %"]


def test_prose_with_a_stray_double_space_is_not_a_table() -> None:
    """Counting fields per line passed this; column offsets do not."""
    assert extract_tables(PROSE_WITH_GAP) == []


def test_a_merged_cell_at_the_end_of_a_row_is_detected() -> None:
    """Stopping at the last populated cell missed the commonest merge."""
    text = (
        "| Team | Service | On-call |\n"
        "| ---- | ------- | ------- |\n"
        "| Platform | gateway | R. Mehta |\n"
        "| Platform |  |  |\n"
    )
    assert extract_tables(text)[0].has_merged_cells is True


def test_a_ragged_table_is_kept_and_the_raggedness_reported() -> None:
    text = (
        "| Host | Role | Notes |\n"
        "| ---- | ---- | ----- |\n"
        "| db-01 | primary | tested |\n"
        "| db-02 | replica |\n"
    )
    table = extract_tables(text)[0]
    assert table.row_count == 2
    assert table.warnings


def test_a_table_of_only_data_has_no_header_row() -> None:
    text = "| 2024-01-01 | 1420 |\n| 2024-01-02 | 1655 |\n"
    table = extract_tables(text)[0]
    assert table.has_header_row is False
    assert table.to_records() == []


def test_records_are_keyed_by_header() -> None:
    records = extract_tables(MARKDOWN_TABLE)[0].to_records()
    assert records[0]["Change ID"] == "CHG-004821"


def test_a_named_column_that_does_not_exist_raises() -> None:
    table = extract_tables(MARKDOWN_TABLE)[0]
    assert table.column("system") == ["payments-api", "billing-worker"]
    with pytest.raises(KeyError):
        table.column("nonexistent")


@pytest.mark.parametrize(
    "fmt",
    [
        TableExportFormat.CSV,
        TableExportFormat.JSON,
        TableExportFormat.MARKDOWN,
        TableExportFormat.XLSX,
    ],
)
def test_every_export_format_renders(fmt: TableExportFormat) -> None:
    rendered = export(extract_tables(MARKDOWN_TABLE)[0], fmt)
    assert "CHG-004821" in rendered


def test_a_table_from_positioned_words_carries_cell_confidences() -> None:
    words = [
        TableWord("Region", 10, 10, 40, 8, 0.98),
        TableWord("Nodes", 120, 10, 30, 8, 0.97),
        TableWord("eu-west-1", 10, 30, 45, 8, 0.93),
        TableWord("142", 120, 30, 18, 8, 0.91),
        TableWord("us-east-1", 10, 50, 45, 8, 0.94),
        TableWord("318", 120, 50, 18, 8, 0.90),
    ]
    table = extract_from_words(words, page_number=3)
    assert table is not None
    assert table.page_number == 3
    assert table.cell_confidences
    assert table.headers == ["Region", "Nodes"]


def test_a_continuation_merges_and_a_mismatch_does_not() -> None:
    first = extract_tables(MARKDOWN_TABLE)[0]
    first.page_number = 4
    second = extract_tables(
        "| Change ID | System | Risk |\n| --- | --- | --- |\n| CHG-004901 | search | low |\n"
    )[0]
    second.page_number = 5
    merged = merge_continuation(first, second)
    assert merged is not None
    assert merged.row_count == 3
    assert merged.spans_pages is True
    assert merged.first_page_number == 4
    assert merged.last_page_number == 5

    unrelated = extract_tables(ALIGNED_TABLE)[0]
    assert merge_continuation(first, unrelated) is None


def test_a_confidence_floor_filters_weak_tables() -> None:
    assert extract_tables(ALIGNED_TABLE, TableConfig(minimum_confidence=0.99)) == []


def test_no_tables_in_empty_text() -> None:
    assert extract_tables("") == []


# ---- forms --------------------------------------------------------------------------


FORM = (
    "CHANGE REQUEST FORM\n\n"
    "Change ID: CHG-004821\n"
    "Requested by: R. Mehta\n"
    "Requester's E-Mail: r.mehta@example.com\n"
    "Risk level: high\n"
    "Planned start: 2026-03-14\n"
    "Rollback tested: yes\n\n"
    "[x] Customer-facing downtime expected\n"
    "[ ] Data migration required\n\n"
    "Approved by: ______________________\n"
)


def test_form_fields_are_extracted_with_their_kinds() -> None:
    result = extract_fields(FORM)
    by_label = {field.normalized_label: field for field in result.fields}
    assert by_label["planned start"].kind is FormFieldKind.DATE
    assert by_label["rollback tested"].kind is FormFieldKind.SELECTION
    assert by_label["approved by"].kind is FormFieldKind.SIGNATURE


def test_an_id_label_with_a_text_value_is_text_not_a_number() -> None:
    """ "Change ID: CHG-004821" typed as NUMBER because the label says ID."""
    field = extract_fields(FORM).get("change id")
    assert field is not None
    assert field.kind is FormFieldKind.TEXT


def test_a_clock_reading_is_not_a_form_field() -> None:
    """ "The incident began at 09:14 and..." split at that colon."""
    result = extract_fields("The incident began at 09:14 and systems failed.")
    assert result.fields == []


def test_a_blank_ruled_field_is_kept_as_a_finding() -> None:
    field = extract_fields(FORM).get("approved by")
    assert field is not None
    assert field.is_blank is True
    assert field.value == ""


def test_blank_fields_can_be_dropped_when_asked() -> None:
    result = extract_fields(FORM, config=FormConfig(keep_blank_fields=False))
    assert result.blank_count == 0


def test_checkboxes_report_state_not_meaning() -> None:
    result = extract_fields(FORM)
    ticked = result.get("customer-facing downtime expected")
    unticked = result.get("data migration required")
    assert ticked is not None and ticked.checked is True
    assert unticked is not None and unticked.checked is False


def test_a_glyph_checkbox_is_read() -> None:
    result = extract_fields("☑ I consent\n☐ I decline\n")
    assert [field.checked for field in result.fields] == [True, False]


def test_a_non_box_field_reports_checked_as_none() -> None:
    """Tri-state on purpose: None is not the same claim as unticked."""
    field = extract_fields(FORM).get("risk level")
    assert field is not None
    assert field.checked is None


def test_template_matching_validates_and_flags_a_missing_required_field() -> None:
    template = FormTemplate(
        name="change-request-v2",
        identifiers=("CHANGE REQUEST FORM",),
        rules=(
            FieldRule("Change ID", required=True, pattern=r"CHG-\d{6}"),
            FieldRule("Requested by", required=True),
            FieldRule("Risk level", allowed=("low", "medium", "high"), required=True),
            FieldRule("Approved by", kind=FormFieldKind.SIGNATURE, required=True),
            FieldRule("Emergency justification"),
        ),
    )
    result = extract_fields(FORM, templates=[template])
    assert result.template_name == "change-request-v2"
    assert result.is_complete is False
    errors = result.errors()
    assert any("Approved by" in message for message in errors)


def test_a_rule_with_a_closed_value_list_types_the_field_as_a_selection() -> None:
    template = FormTemplate(
        name="t",
        rules=(
            FieldRule("Risk level", allowed=("low", "medium", "high")),
            FieldRule("Change ID"),
        ),
    )
    result = extract_fields(FORM, templates=[template])
    field = result.get("risk level")
    assert field is not None
    assert field.kind is FormFieldKind.SELECTION
    assert field.options == ["low", "medium", "high"]


def test_a_pattern_violation_is_reported() -> None:
    template = FormTemplate(
        name="t", rules=(FieldRule("Change ID", pattern=r"INC-\d{6}"), FieldRule("Risk level"))
    )
    result = extract_fields(FORM, templates=[template])
    assert any("does not match" in message for message in result.errors())


def test_normalize_label_folds_accents_and_punctuation() -> None:
    assert normalize_label("Requester's E-Mail") == "requester s e mail"
    assert normalize_label("Café Naïve") == "cafe naive"


def test_extract_key_values_returns_only_populated_fields() -> None:
    values = extract_key_values(FORM)
    assert values["Change ID"] == "CHG-004821"
    assert "Approved by" not in values


def test_a_long_value_is_not_a_field() -> None:
    text = "Notes: the team confirmed that the rollback path restores the image\n"
    assert extract_fields(text, config=FormConfig(max_value_words=5)).fields == []


def test_merge_pages_keeps_a_value_a_reprint_left_blank() -> None:
    """A continuation page reprinting a header field must not erase it."""
    first = extract_fields("Change ID: CHG-004821\nApproved by: ______\n")
    second = extract_fields("Change ID: \nApproved by: A. Novak\n")
    merged = merge_pages([first, second])
    values = {field.normalized_label: field.value for field in merged.fields}
    assert values["change id"] == "CHG-004821"
    assert values["approved by"] == "A. Novak"


def test_a_missing_required_field_lowers_the_result_confidence() -> None:
    template = FormTemplate(
        name="t",
        rules=(FieldRule("Change ID"), FieldRule("Absent field", required=True)),
    )
    with_missing = extract_fields(FORM, templates=[template])
    assert with_missing.unmatched_required == ["Absent field"]
    assert with_missing.confidence < extract_fields(FORM).confidence


def test_no_fields_in_empty_text() -> None:
    assert extract_fields("").fields == []


# ---- summarization ------------------------------------------------------------------


POSTMORTEM = (
    "Payments API outage postmortem\n\n"
    "Overview\n"
    "On 14 March the payments API was unavailable for 41 minutes, and roughly\n"
    "18,000 customer transactions failed during that window. The estimated\n"
    "revenue impact is 240,000 dollars and the incident triggered a review by\n"
    "the change advisory board.\n\n"
    "Root cause\n"
    "The new release changed the database connection pool configuration so\n"
    "that each service replica opened 200 connections instead of 20. The\n"
    "PostgreSQL primary reached its connection limit and refused new\n"
    "connections, which the API surfaced as timeout errors to every caller.\n\n"
    "Remediation\n"
    "We have capped the connection pool in the deployment schema and added a\n"
    "readiness probe that fails when the pool is saturated.\n"
)


def test_a_hard_wrapped_sentence_is_not_cut_at_the_line_break() -> None:
    """Splitting on newlines turned every sentence into two fragments."""
    summary = summarize(POSTMORTEM, config=SummaryConfig(sentence_count=2))
    assert "roughly 18,000 customer transactions failed" in summary.text


def test_executive_and_technical_summaries_differ() -> None:
    """Unnormalised salience drowned the audience bonus and made them equal."""
    config = SummaryConfig(sentence_count=2)
    executive = summarize(POSTMORTEM, kind=SummaryKind.EXECUTIVE, config=config)
    technical = summarize(POSTMORTEM, kind=SummaryKind.TECHNICAL, config=config)
    assert executive.text != technical.text


def test_a_markdown_table_row_is_never_selected_as_a_sentence() -> None:
    """A divider row read as "| --- | --- |" in an executive summary."""
    text = POSTMORTEM + "\n| System | Risk |\n| --- | --- |\n| payments-api | high |\n"
    summary = summarize(text, config=SummaryConfig(sentence_count=5))
    assert "---" not in summary.text
    assert "|" not in summary.text


def test_a_bullet_summary_is_a_bullet_list() -> None:
    summary = summarize(POSTMORTEM, kind=SummaryKind.BULLET, config=SummaryConfig(sentence_count=3))
    assert summary.text.startswith("- ")
    assert summary.text.count("\n- ") == 2


def test_a_section_summary_is_keyed_by_heading() -> None:
    summary = summarize(
        POSTMORTEM, kind=SummaryKind.SECTION, config=SummaryConfig(sentence_count=6)
    )
    assert set(summary.sections) >= {"Overview", "Root cause", "Remediation"}


def test_split_sections_keeps_the_preamble() -> None:
    sections = split_sections("Some preamble text here.\n\nHeading\n\nBody text follows.\n")
    assert "Introduction" in sections


def test_an_abstractive_request_without_a_backend_falls_back_and_says_so() -> None:
    summary = summarize(POSTMORTEM, kind=SummaryKind.ABSTRACTIVE)
    assert summary.fallback_used is True
    assert summary.text


def test_a_working_backend_is_used_and_not_flagged_as_a_fallback() -> None:
    class Backend:
        def summarize(self, text: str, *, max_words: int, kind: SummaryKind) -> str:
            return "A generated summary."

    summary = summarize(POSTMORTEM, kind=SummaryKind.ABSTRACTIVE, backend=Backend())
    assert summary.fallback_used is False
    assert summary.text == "A generated summary."


def test_a_broken_backend_degrades_rather_than_failing_the_document() -> None:
    class Broken:
        def summarize(self, text: str, *, max_words: int, kind: SummaryKind) -> str:
            raise RuntimeError("model unavailable")

    summary = summarize(POSTMORTEM, kind=SummaryKind.ABSTRACTIVE, backend=Broken())
    assert summary.fallback_used is True
    assert summary.text


def test_an_empty_backend_response_falls_back() -> None:
    class Empty:
        def summarize(self, text: str, *, max_words: int, kind: SummaryKind) -> str:
            return "   "

    assert summarize(POSTMORTEM, kind=SummaryKind.ABSTRACTIVE, backend=Empty()).fallback_used


def test_summarize_many_produces_one_summary_per_kind() -> None:
    produced = summarize_many(POSTMORTEM, [SummaryKind.EXECUTIVE, SummaryKind.BULLET])
    assert set(produced) == {SummaryKind.EXECUTIVE, SummaryKind.BULLET}


def test_the_word_limit_is_enforced() -> None:
    summary = summarize(POSTMORTEM, config=SummaryConfig(sentence_count=5, max_words=12))
    assert len(summary.text.split()) <= 13  # 12 words plus the ellipsis


def test_top_terms_is_stable_across_runs() -> None:
    weights = {"alpha": 1.0, "beta": 1.0, "gamma": 2.0}
    assert top_terms(weights, 3) == ["gamma", "alpha", "beta"]


def test_compression_ratio_is_zero_for_an_empty_source() -> None:
    assert Summary(kind=SummaryKind.EXTRACTIVE).compression_ratio == 0.0


def test_summarizing_nothing_produces_nothing() -> None:
    summary = summarize("")
    assert summary.text == ""
    assert summary.confidence == 0.0


# ---- translation -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The change request was approved by the board and the release is set.", "en"),
        ("El equipo de operaciones ha revisado el informe y los cambios.", "es"),
        ("Le rapport a ete examine par le comite et les modifications.", "fr"),
        ("Отчет был рассмотрен комитетом.", "ru"),
    ],
)
def test_language_detection(text: str, expected: str) -> None:
    assert detect_language(text).language == expected


def test_detection_of_too_little_text_is_unreliable_rather_than_wrong() -> None:
    guess = detect_language("OK")
    assert guess.is_reliable is False
    assert guess.confidence == 0.0


def test_digits_alone_detect_nothing_reliable() -> None:
    assert detect_language("2026 03 14 09:14:22 500 404").is_reliable is False


PROTECTED = (
    "Restart payments-api on db-01.eu-west-1.internal and close CHG-004821. "
    "The runbook is at https://wiki.example.com/runbooks and the config is "
    "/etc/payments/pool.yaml. Version 4.2.1 is affected. Mail r.mehta@example.com. "
    "Set `pool_size` to 20."
)


def test_protect_and_restore_round_trip_exactly() -> None:
    protected, spans = protect(PROTECTED)
    assert spans
    restored, lost = restore(protected, spans)
    assert restored == PROTECTED
    assert lost == []


def test_a_path_does_not_swallow_the_sentence_full_stop() -> None:
    _protected, spans = protect(PROTECTED)
    assert "/etc/payments/pool.yaml" in spans.values()
    assert "/etc/payments/pool.yaml." not in spans.values()


def test_a_url_is_protected_whole_rather_than_carved_up() -> None:
    _protected, spans = protect("See https://wiki.example.com/runbooks/payments now.")
    assert "https://wiki.example.com/runbooks/payments" in spans.values()


def test_protection_can_be_switched_off_per_category() -> None:
    _protected, spans = protect(
        PROTECTED, config=TranslationConfig(preserve_urls=False, preserve_code=False)
    )
    assert not any(value.startswith("https://") for value in spans.values())


class _Faithful:
    def translate(self, text: str, *, source: str, target: str) -> str:
        return f"[{target}] {text}"


class _Loses:
    """Drops the last placeholder, as a real backend sometimes does."""

    def translate(self, text: str, *, source: str, target: str) -> str:
        tokens = sorted(token for token in (f"{index}" for index in range(40)) if token in text)
        return text.replace(tokens[-1], "") if tokens else text


def test_translation_preserves_untranslatable_terms() -> None:
    result = translate(PROTECTED, target="fr", backend=_Faithful())
    assert "payments-api" in result.text
    assert "CHG-004821" in result.text
    assert result.is_faithful is True
    assert result.preserved_terms
    assert all("" not in term for term in result.preserved_terms)


def test_a_lost_protected_term_is_reported_and_lowers_confidence() -> None:
    faithful = translate(PROTECTED, target="fr", backend=_Faithful())
    lossy = translate(PROTECTED, target="fr", backend=_Loses())
    assert lossy.is_faithful is False
    assert lossy.lost_placeholders
    assert lossy.confidence < faithful.confidence
    assert lossy.warnings


def test_an_invented_placeholder_is_stripped_from_the_output() -> None:
    class Invents:
        def translate(self, text: str, *, source: str, target: str) -> str:
            return text + " 99"

    result = translate("Restart the service now please.", target="fr", backend=Invents())
    assert "" not in result.text


def test_no_backend_refuses_rather_than_returning_the_source() -> None:
    with pytest.raises(TranslationUnavailableError):
        translate(PROTECTED, target="fr")


def test_the_same_language_returns_unchanged_with_a_warning() -> None:
    text = "The change request was approved by the board and released."
    result = translate(text, target="en", backend=_Faithful())
    assert result.text == text
    assert result.warnings


def test_a_glossary_forces_a_rendering_longest_term_first() -> None:
    glossary = Glossary(
        entries=[
            GlossaryEntry("change request", translations={"fr": "demande de changement"}),
            GlossaryEntry("change", translations={"fr": "modification"}),
            GlossaryEntry("AI-IOS", preserve=True),
        ]
    )
    result = translate(
        "The change request for AI-IOS was approved.",
        target="fr",
        backend=_Faithful(),
        glossary=glossary,
    )
    assert "demande de changement" in result.text
    assert "AI-IOS" in result.text
    assert result.glossary_applied == ["change request"]


def test_a_glossary_entry_is_usable_as_a_dict_key() -> None:
    """A frozen dataclass holding a mapping is not hashable by value."""
    entry = GlossaryEntry("term", translations={"fr": "terme"})
    assert {entry: 1}[entry] == 1


def test_translate_many_detects_the_source_once() -> None:
    results = translate_many(PROTECTED, ["fr", "de"], backend=_Faithful())
    assert set(results) == {"fr", "de"}
    assert len({result.source_language for result in results.values()}) == 1


def test_an_unreliable_detection_warns_the_caller() -> None:
    result = translate("Data 2026 status ok fine", target="fr", backend=_Faithful())
    assert result.warnings


def test_translating_nothing_produces_nothing() -> None:
    result = translate("", target="fr", backend=_Faithful())
    assert result.text == ""
    assert result.confidence == 0.0


# ---- validation --------------------------------------------------------------------


RULES: tuple[Rule, ...] = (
    required("change_id"),
    matches("change_id", r"CHG-\d{6}"),
    required("requested_by"),
    one_of("risk_level", ["low", "medium", "high"], required_field=True),
    between("duration_minutes", low=1, high=480),
    required("rollback_plan"),
    dates_in_order("planned_start", "planned_end"),
    business_rule(
        "high-risk-needs-approver",
        lambda values: values.get("risk_level") != "high" or bool(values.get("approved_by")),
        message="A high-risk change must name an approver.",
    ),
)

CONFIG = ValidationConfig(
    expected_fields=(
        "change_id",
        "requested_by",
        "risk_level",
        "duration_minutes",
        "rollback_plan",
        "planned_start",
        "planned_end",
        "approved_by",
    )
)

GOOD = {
    "change_id": "CHG-004821",
    "requested_by": "R. Mehta",
    "risk_level": "high",
    "duration_minutes": "45",
    "rollback_plan": "Redeploy 4.2.0",
    "planned_start": "2026-03-14",
    "planned_end": "2026-03-14",
    "approved_by": "A. Novak",
}


def test_a_complete_document_passes_every_rule() -> None:
    report = validate(GOOD, RULES, config=CONFIG)
    assert report.is_valid is True
    assert report.is_complete is True
    assert report.completeness == 1.0
    assert report.requires_review is False


def test_each_kind_of_violation_is_reported() -> None:
    bad = {
        "change_id": "CHG-48",
        "requested_by": "  ",
        "risk_level": "critical",
        "duration_minutes": "many",
        "planned_start": "2026-03-20",
        "planned_end": "2026-03-14",
    }
    report = validate(bad, RULES, config=CONFIG)
    assert report.is_valid is False
    names = {finding.rule for finding in report.failures}
    assert "change_id-format" in names
    assert "requested_by-required" in names
    assert "risk_level-allowed" in names
    assert "duration_minutes-range" in names
    assert "rollback_plan-required" in names
    assert "planned_start-before-planned_end" in names


def test_a_rule_that_could_not_run_is_skipped_not_passed() -> None:
    """Folding a skip into PASSED is how an incomplete document is approved."""
    partial = {"change_id": "CHG-004900", "requested_by": "S. Oyelaran", "risk_level": "low"}
    report = validate(partial, RULES, config=CONFIG)
    assert report.skipped
    assert report.is_complete is False
    assert report.requires_review is True


def test_a_non_numeric_value_fails_a_range_rule() -> None:
    """Skipping the comparison would let "many" pass "must be under ten"."""
    report = validate({"duration_minutes": "many"}, (between("duration_minutes", high=10),))
    assert report.failures


def test_a_predicate_that_raises_is_skipped_not_passed() -> None:
    report = validate({"a": 1}, (business_rule("boom", lambda values: values["missing"] == 1),))
    assert report.skipped
    assert report.is_complete is False


def test_a_rule_that_checks_nothing_is_refused_at_construction() -> None:
    with pytest.raises(ValueError, match="checks nothing"):
        Rule(name="empty", kind=RULES[0].kind, field_name="x")


def test_a_warning_severity_does_not_block() -> None:
    rule = business_rule("weekend", lambda values: False, severity=ValidationOutcome.WARNING)
    report = validate({"a": "b"}, (rule,))
    assert report.is_valid is True
    assert report.warnings


def test_low_confidence_fields_are_flagged_for_review() -> None:
    report = validate(
        GOOD, RULES, config=CONFIG, confidences={"risk_level": 0.42, "change_id": 0.98}
    )
    flagged = [finding.field_name for finding in report.warnings if finding.confidence]
    assert "risk_level" in flagged
    assert "change_id" not in flagged


def test_completeness_of_an_empty_expectation_is_zero_not_one() -> None:
    """100% complete because nothing was expected reads as reassurance."""
    assert completeness({"a": "b"}, ()) == 0.0


def test_a_re_scan_with_one_ocr_error_is_still_a_near_duplicate() -> None:
    """Five-word shingles capped this at 0.68, below any sane threshold."""
    original = (
        "Change request CHG-004821 for the payments API. The team will redeploy "
        "version 4.2.0 if the rollout fails and the on-call rota has been informed."
    )
    rescan = original.replace("payments API", "payments AP1")
    assert similarity(original, rescan) >= 0.75
    assert find_duplicate(rescan, {"doc-1": original}, 0.75) is not None


def test_two_forms_sharing_a_template_are_not_duplicates() -> None:
    first = "Change Request Form. Change ID: CHG-004821. Requested by: R. Mehta."
    second = "Change Request Form. Change ID: CHG-005190. Requested by: S. Oyelaran."
    assert find_duplicate(second, {"a": first}, 0.75) is None


def test_a_duplicate_is_a_warning_not_a_failure() -> None:
    original = "Change request CHG-004821 for the payments API team review."
    report = validate(GOOD, RULES, config=CONFIG, text=original, known_documents={"a": original})
    assert report.is_valid is True
    assert any(finding.rule == "duplicate-detection" for finding in report.warnings)


def test_shingles_of_short_text_still_produce_something() -> None:
    assert shingles("two words")
    assert shingles("") == frozenset()


@pytest.mark.parametrize(
    "raw",
    ["2026-03-14", "14/03/2026", "14 March 2026", "March 14, 2026"],
)
def test_dates_parse_in_every_supported_format(raw: str) -> None:
    parsed = parse_date(raw)
    assert parsed is not None
    assert parsed.year == 2026


def test_an_unparseable_date_is_none() -> None:
    assert parse_date("not a date") is None
    assert parse_date(None) is None
    assert parse_date("") is None


def test_bounds_accept_decimals() -> None:
    rule = between("amount", low=Decimal("1.5"), high=Decimal("2.5"))
    assert validate({"amount": "2.0"}, (rule,)).is_valid
    assert not validate({"amount": "3.0"}, (rule,)).is_valid


def test_validate_many_keys_reports_by_document() -> None:
    reports = validate_many([("a", GOOD), ("b", {})], RULES, config=CONFIG)
    assert set(reports) == {"a", "b"}
    assert reports["a"].is_valid
    assert not reports["b"].is_valid


def test_an_empty_report_summarises_every_outcome() -> None:
    summary = ValidationReport().summary()
    assert set(summary) == {str(outcome) for outcome in ValidationOutcome}
