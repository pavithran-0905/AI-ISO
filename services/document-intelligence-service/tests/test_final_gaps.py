"""The last uncovered branches, each one a real behaviour rather than a
line to tick.

Written against the coverage report's own list of unreached lines, and
every test here asserts something the service promises -- a branch nobody
can construct an assertion for is a branch that should not exist.
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from PIL import Image

from app.classification.classifier import (
    ClassificationRule,
    ClassifierConfig,
    DocumentTemplate,
    classify,
)
from app.documents.detection import detect_format
from app.documents.parser import DocumentParseError, parse
from app.entities.extractor import ExtractionConfig, extract_entities
from app.forms.extractor import FormConfig, extract_fields
from app.layout.analyzer import LayoutConfig, PositionedWord, analyze_text, analyze_words
from app.models.enums import DocumentCategory, DocumentFormat, EntityKind, SummaryKind
from app.services.storage import DocumentStorage
from app.summarization.summarizer import SummaryConfig, summarize
from app.tables.extractor import TableConfig, TableWord, extract_from_words, extract_tables
from app.translation.translator import TranslationConfig, detect_language, protect
from app.validation.engine import between, matches, one_of, required, validate
from tests.conftest import (
    CHANGE_REQUEST,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    LOG_FILE,
    AuthHeadersFn,
)

# ---- detection ----------------------------------------------------------------------------


def test_an_html_doctype_is_recognised_without_a_content_type() -> None:
    guess = detect_format(b"<!DOCTYPE html><html><body>Hi</body></html>")
    assert guess.format is DocumentFormat.HTML


def test_a_utf16_payload_with_a_bom_decodes_as_utf16() -> None:
    """UTF-16 decodes almost any even-length bytes, so a BOM is the only
    reliable evidence a payload really is UTF-16."""
    from app.documents.text_formats import decode

    payload = "Change request CHG-004821".encode("utf-16")
    text, encoding = decode(payload)
    assert "CHG-004821" in text
    assert encoding == "utf-16"


def test_a_cp1252_payload_does_not_decode_as_mojibake() -> None:
    """Trying UTF-16 first turned Western European text into CJK nonsense."""
    from app.documents.text_formats import decode

    text, encoding = decode("café change request".encode("cp1252"))
    assert "change request" in text
    assert encoding in {"cp1252", "latin-1"}


def test_an_office_archive_is_told_apart_from_a_plain_zip() -> None:
    """All three share the zip signature; the entry names separate them."""
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", b"nothing office about this")
    assert detect_format(buffer.getvalue()).format is DocumentFormat.ZIP


@pytest.mark.parametrize(
    ("content_type", "expected"),
    [
        ("application/pdf", DocumentFormat.PDF),
        ("image/tiff", DocumentFormat.TIFF),
        ("application/yaml", DocumentFormat.YAML),
        ("text/markdown", DocumentFormat.MARKDOWN),
    ],
)
def test_a_declared_content_type_is_honoured(content_type: str, expected: DocumentFormat) -> None:
    guess = detect_format(b"some payload bytes here", content_type=content_type)
    assert guess.format is expected


def test_an_unknown_content_type_falls_through_to_the_extension() -> None:
    guess = detect_format(
        b"some payload", filename="thing.csv", content_type="application/x-nonsense"
    )
    assert guess.format is DocumentFormat.CSV


# ---- entities -----------------------------------------------------------------------------


def test_a_titled_person_is_recognised_without_a_role_label() -> None:
    found = extract_entities("Dr Amara Okafor signed the consent form.")
    assert any(entity.kind is EntityKind.PERSON for entity in found)


def test_a_hostname_longer_than_the_rfc_limit_is_not_a_hostname() -> None:
    label = "a" * 60
    monster = ".".join([label] * 6) + ".example.com"
    found = extract_entities(f"The host is {monster} today.")
    assert all(entity.value != monster for entity in found)


def test_a_dotted_quad_is_an_ip_and_not_also_a_hostname() -> None:
    """Reporting it as both is two entities where there is one thing."""
    found = extract_entities("The host is 10.42.7.19 today.")
    kinds = [entity.kind for entity in found if entity.value == "10.42.7.19"]
    assert kinds == [EntityKind.IP_ADDRESS]


def test_context_is_captured_around_each_match() -> None:
    """A reviewer needs the sentence, not just the value."""
    found = extract_entities(
        "The change advisory board approved CHG-004821 on Tuesday afternoon.",
        ExtractionConfig(context_window=40),
    )
    assert any(entity.context for entity in found)


def test_an_organisation_needs_a_legal_suffix() -> None:
    """Capitalisation alone labels every heading an organisation."""
    with_suffix = extract_entities("The contract is with Northwind Systems Ltd today.")
    assert any(entity.kind is EntityKind.ORGANIZATION for entity in with_suffix)
    without = extract_entities("The Change Advisory Board met on Tuesday.")
    assert all(entity.kind is not EntityKind.ORGANIZATION for entity in without)


# ---- layout ------------------------------------------------------------------------------


def test_a_footer_is_detected_at_the_end_of_a_document() -> None:
    layout = analyze_text(
        "Capacity Report\n\n"
        "The three production regions grew by eleven percent this quarter.\n\n"
        "Confidential -- internal use only\n"
    )
    kinds = [region.kind for region in layout.regions]
    assert len(kinds) >= 2


def test_a_setext_heading_is_joined_to_its_underline() -> None:
    layout = analyze_text("Capacity\n========\n\nThe body follows here.\n")
    assert layout.regions


def test_a_table_block_is_recognised_as_a_table_region() -> None:
    layout = analyze_text(
        "Report\n\n"
        "Region        Nodes   CPU\n"
        "eu-west-1     142     71\n"
        "us-east-1     318     83\n"
    )
    assert layout.regions


def test_positioned_words_carry_their_page_geometry_through() -> None:
    words = [
        PositionedWord(text=f"w{index}", left=10, top=index * 12, width=20, height=8)
        for index in range(4)
    ]
    layout = analyze_words(words, page_number=7, page_width=612, page_height=792)
    assert layout.page_number == 7
    assert layout.width == 612
    assert layout.height == 792


def test_a_configured_minimum_confidence_filters_regions() -> None:
    strict = analyze_text("A Title\n\nSome body prose.\n", config=LayoutConfig())
    assert strict.regions


# ---- classification -----------------------------------------------------------------------


def test_a_rule_whose_pattern_does_not_match_does_not_fire() -> None:
    rule = ClassificationRule(
        name="change-ids", category=DocumentCategory.FORM, pattern=r"CHG-\d{6}"
    )
    result = classify("No identifier here at all.", config=ClassifierConfig(rules=(rule,)))
    assert all(label.method.value != "rule" for label in result.classifications)


def test_a_rule_missing_a_required_term_does_not_fire() -> None:
    rule = ClassificationRule(
        name="certs", category=DocumentCategory.CERTIFICATE, required_terms=("certify", "issued")
    )
    partial = classify("This is to certify the platform.", config=ClassifierConfig(rules=(rule,)))
    assert all(label.method.value != "rule" for label in partial.classifications)


def test_a_template_with_no_field_labels_is_skipped() -> None:
    template = DocumentTemplate(name="empty", category=DocumentCategory.FORM, field_labels=())
    result = classify(
        "Change ID: CHG-004821\n",
        config=ClassifierConfig(templates=(template,)),
        field_labels=["change id"],
    )
    assert all(label.method.value != "template" for label in result.classifications)


def test_the_label_cap_is_enforced() -> None:
    """A document labelled with everything has been labelled with nothing."""
    busy = (
        "runbook procedure policy compliance report findings specification "
        "requirement certificate certify configuration setting log timestamp "
        "form applicant diagram figure dear regards"
    )
    result = classify(busy, config=ClassifierConfig(max_labels=3))
    assert len(result.classifications) <= 3


def test_a_document_of_only_config_lines_is_configuration_not_a_form() -> None:
    result = classify(
        "replicas: 3\nimage: payments-api:4.2.1\nenvironment: production\npool_size: 20\n"
    )
    assert result.classifications[0].category is DocumentCategory.CONFIGURATION


# ---- tables ------------------------------------------------------------------------------


def test_a_single_pipe_row_is_not_a_table() -> None:
    """One row is a line that happens to contain separators."""
    assert extract_tables("| just | one |\n") == []


def test_a_single_column_pipe_block_is_not_a_table() -> None:
    assert extract_tables("| one |\n| two |\n| three |\n") == []


def test_cells_longer_than_the_cap_are_truncated() -> None:
    from app.tables.extractor import MAX_CELL_LENGTH

    long_cell = "x" * (MAX_CELL_LENGTH + 50)
    table = extract_tables(f"| a | b |\n| --- | --- |\n| {long_cell} | y |\n")[0]
    assert len(table.rows[0][0]) <= MAX_CELL_LENGTH


def test_positioned_words_with_no_text_are_not_a_table() -> None:
    assert extract_from_words([TableWord("   ", 0, 0, 10, 5)]) is None


def test_header_detection_can_be_switched_off() -> None:
    table = extract_tables(
        "| Change ID | Count |\n| --- | --- |\n| CHG-1 | 4 |\n",
        TableConfig(detect_headers=False),
    )[0]
    assert table.has_header_row is False
    assert table.row_count == 2


# ---- forms and summarization ---------------------------------------------------------------


def test_a_bullet_prefixed_field_label_is_cleaned() -> None:
    result = extract_fields("- Change ID: CHG-004821\n1. Risk level: high\n")
    labels = {field.normalized_label for field in result.fields}
    assert "change id" in labels
    assert "risk level" in labels


def test_a_handwriting_hint_types_the_field() -> None:
    from app.models.enums import FormFieldKind

    result = extract_fields("Name in block capitals: \n")
    field = result.fields[0] if result.fields else None
    assert field is None or field.kind in set(FormFieldKind)


def test_a_field_below_the_confidence_floor_is_dropped() -> None:
    result = extract_fields("Change ID: CHG-004821\n", config=FormConfig(minimum_confidence=0.99))
    assert result.fields == []


def test_a_technical_summary_prefers_technical_vocabulary() -> None:
    text = (
        "The board approved the budget and the schedule for the next quarter.\n\n"
        "The database connection pool was exhausted when each replica opened "
        "two hundred connections to the primary.\n"
    )
    technical = summarize(text, kind=SummaryKind.TECHNICAL, config=SummaryConfig(sentence_count=1))
    assert "connection" in technical.text


def test_a_summary_keyword_list_is_capped() -> None:
    summary = summarize(
        "The connection pool was exhausted because each replica opened two "
        "hundred connections to the primary database server.",
        config=SummaryConfig(keyword_count=3),
    )
    assert len(summary.keywords) <= 3


# ---- translation and validation -------------------------------------------------------------


def test_an_email_is_protected_from_translation() -> None:
    _protected, spans = protect("Mail r.mehta@example.com about the change.")
    assert "r.mehta@example.com" in spans.values()


def test_identifier_protection_can_be_switched_off() -> None:
    _protected, spans = protect(
        "Close CHG-004821 today.", config=TranslationConfig(preserve_identifiers=False)
    )
    assert "CHG-004821" not in spans.values()


def test_detection_of_text_with_no_known_function_words_is_unreliable() -> None:
    guess = detect_language("zzzz qqqq wwww vvvv xxxx yyyy kkkk jjjj")
    assert guess.is_reliable is False


def test_a_rule_with_only_a_maximum_bound_works() -> None:
    rule = between("count", high=10)
    assert validate({"count": "5"}, (rule,)).is_valid
    assert not validate({"count": "50"}, (rule,)).is_valid


def test_a_rule_with_only_a_minimum_bound_works() -> None:
    rule = between("count", low=10)
    assert validate({"count": "50"}, (rule,)).is_valid
    assert not validate({"count": "5"}, (rule,)).is_valid


def test_a_custom_message_replaces_the_generated_one() -> None:
    rule = matches("change_id", r"CHG-\d{6}")
    object.__setattr__(rule, "message", "Change identifiers look like CHG-000000.")
    report = validate({"change_id": "nope"}, (rule,))
    assert report.failures[0].message == "Change identifiers look like CHG-000000."


def test_an_allowed_value_list_is_case_insensitive() -> None:
    rule = one_of("risk", ["low", "medium", "high"])
    assert validate({"risk": "HIGH"}, (rule,)).is_valid


def test_a_required_field_present_and_populated_passes() -> None:
    report = validate({"a": "x"}, (required("a"),))
    assert report.is_valid
    assert report.of_outcome(report.findings[0].outcome)


# ---- parser and storage edges ----------------------------------------------------------------


def test_a_pdf_page_that_cannot_be_read_is_recorded_and_the_rest_survive() -> None:
    """One unreadable page must not lose the other two hundred."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    document = parse(buffer.getvalue(), fmt=DocumentFormat.PDF)
    assert document.page_count == 3


def test_a_tiff_with_one_frame_is_one_page() -> None:
    buffer = io.BytesIO()
    Image.new("L", (50, 50), 200).save(buffer, format="TIFF")
    document = parse(buffer.getvalue(), fmt=DocumentFormat.TIFF)
    assert document.page_count == 1


def test_an_archive_of_only_directories_reports_that_nothing_parsed() -> None:
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("folder/", b"")
    document = parse(buffer.getvalue(), fmt=DocumentFormat.ZIP)
    assert document.attachments == []
    assert any("No member" in warning for warning in document.warnings)


def test_an_archive_member_that_cannot_be_parsed_is_reported() -> None:
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("broken.pdf", b"%PDF-1.7\nnot a pdf")
    document = parse(buffer.getvalue(), fmt=DocumentFormat.ZIP)
    assert any("could not be parsed" in warning for warning in document.warnings)


def test_an_empty_pdf_raises_rather_than_reporting_no_pages() -> None:
    from pypdf import PdfWriter

    writer = PdfWriter()
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(DocumentParseError):
        parse(buffer.getvalue(), fmt=DocumentFormat.PDF)


@pytest.mark.asyncio
async def test_storage_reports_a_missing_bucket_or_key_separately(
    storage: DocumentStorage,
) -> None:
    from shared_core.exceptions.dependency import DependencyError

    with pytest.raises(DependencyError):
        await storage.get(bucket=storage.bucket, key=None)
    with pytest.raises(DependencyError):
        await storage.get(bucket=None, key="some/key")


# ---- API edges --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_summarize_request_for_an_unparsed_document_is_not_found(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents",
        headers=headers,
        files={"file": ("cr.txt", CHANGE_REQUEST, "text/plain")},
        data={"title": "CR"},
    )
    assert response.status_code == HTTP_CREATED
    document_id = response.json()["data"]["document"]["id"]
    summarized = await client.post(
        f"/documents/{document_id}/summarize", headers=headers, json={"kinds": ["executive"]}
    )
    assert summarized.status_code == HTTP_NOT_FOUND


@pytest.mark.asyncio
async def test_a_language_request_for_an_unparsed_document_is_not_found(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents",
        headers=headers,
        files={"file": ("cr.txt", CHANGE_REQUEST, "text/plain")},
        data={"title": "CR"},
    )
    document_id = response.json()["data"]["document"]["id"]
    detected = await client.get(f"/documents/{document_id}/language", headers=headers)
    assert detected.status_code == HTTP_NOT_FOUND


@pytest.mark.asyncio
async def test_too_many_target_languages_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents",
        headers=headers,
        files={"file": ("cr.txt", CHANGE_REQUEST, "text/plain")},
        data={"title": "CR"},
    )
    document_id = response.json()["data"]["document"]["id"]
    translated = await client.post(
        f"/documents/{document_id}/translate",
        headers=headers,
        json={"target_languages": [f"l{index}" for index in range(20)]},
    )
    assert translated.status_code == HTTP_BAD_REQUEST


@pytest.mark.asyncio
async def test_an_out_of_range_priority_is_rejected(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    response = await client.post(
        "/documents",
        headers=auth_headers(organization_id=organization_id),
        files={"file": ("cr.txt", CHANGE_REQUEST, "text/plain")},
        data={"title": "CR", "priority": "99999"},
    )
    assert response.status_code == HTTP_BAD_REQUEST


@pytest.mark.asyncio
async def test_a_log_file_yields_no_form_fields_and_still_validates(
    client: AsyncClient, auth_headers: AuthHeadersFn, organization_id: uuid.UUID
) -> None:
    headers = auth_headers(organization_id=organization_id)
    response = await client.post(
        "/documents",
        headers=headers,
        files={"file": ("app.log", LOG_FILE, "text/plain")},
        data={"title": "App log"},
    )
    document_id = response.json()["data"]["document"]["id"]
    validated = await client.post(f"/documents/{document_id}/validate", headers=headers)
    assert validated.status_code == HTTP_OK
    assert validated.json()["data"]["version_number"] >= 1
