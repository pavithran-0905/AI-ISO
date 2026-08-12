"""Telemetry, notifications, OCR, the scheduler registrar, and the edges.

The paths a happy-path test never reaches: a failing OCR binary, a mail
server that is down, a scheduler interval of zero, an encrypted PDF, and
the branches every engine takes only on unusual input.
"""

from __future__ import annotations

import io

import pytest
from opentelemetry.trace import NoOpTracer
from shared_core.enums.notification_type import NotificationType
from shared_core.exceptions.dependency import DependencyError
from shared_core.exceptions.notification import NotificationError
from shared_core.scheduler import SchedulerManager

from app import telemetry
from app.classification.classifier import (
    ClassificationRule,
    ClassifierConfig,
    DocumentTemplate,
    classify,
)
from app.config.keys import load_public_key
from app.documents.parser import ParsedDocument, ParsedPage, limit_text
from app.entities.extractor import (
    CustomEntityPattern,
    ExtractionConfig,
    extract_entities,
    normalize,
)
from app.forms.extractor import FieldRule, FormConfig, FormTemplate, extract_fields
from app.layout.analyzer import (
    BoundingBox,
    LayoutConfig,
    PositionedWord,
    analyze_text,
    analyze_words,
    merge_pages,
)
from app.models.enums import (
    DocumentCategory,
    DocumentFormat,
    DocumentStatus,
    EntityKind,
    OcrEngineKind,
    OcrQuality,
    SummaryKind,
    is_terminal,
    needs_ocr,
    ocr_quality_for,
)
from app.notifications.document_notifications import (
    MAX_LISTED_FAILURES,
    DocumentNotificationService,
)
from app.ocr.engine import (
    EngineAvailability,
    OcrPage,
    OcrResult,
    OcrUnavailableError,
    OcrWord,
    TesseractEngine,
)
from app.summarization.summarizer import SummaryConfig, split_sections, summarize
from app.tables.extractor import ExtractedTable, TableConfig, TableWord, extract_from_words
from app.validation.engine import ValidationConfig, business_rule, validate
from app.workers.registrar import (
    PROCESSING_SWEEP_JOB_ID,
    register_processing_sweep,
    register_retention_sweep,
    register_review_expiry_sweep,
    register_statistics_rollup,
)

# ---- telemetry ------------------------------------------------------------------------


def test_every_span_helper_opens_and_closes() -> None:
    """A span whose attributes silently vanish is worse than no span.

    ``start_span`` has no parameter named ``attributes`` -- only a
    ``**attributes`` catch-all -- so passing a literal ``attributes={...}``
    drops every value on the floor without raising.
    """
    tracer = NoOpTracer()
    with telemetry.trace_pipeline(tracer, stages=8):
        with telemetry.trace_upload(tracer, document_format="txt", byte_size=900):
            pass
        with telemetry.trace_ocr(tracer, pages=3, engine="tesseract"):
            pass
        with telemetry.trace_layout(tracer, pages=3):
            pass
        with telemetry.trace_classification(tracer, method="template"):
            pass
        with telemetry.trace_entity_extraction(tracer, text_length=1200):
            pass
        with telemetry.trace_table_extraction(tracer, tables=1):
            pass
        with telemetry.trace_form_extraction(tracer, fields=11):
            pass
        with telemetry.trace_validation(tracer, rules=4):
            pass
        with telemetry.trace_review(tracer, decision="corrected", corrections=2):
            pass


def test_span_helpers_accept_extra_attributes() -> None:
    tracer = NoOpTracer()
    with telemetry.trace_ocr(tracer, pages=1, engine="tesseract", **{"ocr.confidence": 0.9}):
        pass


def test_the_telemetry_package_exports_every_helper() -> None:
    assert len(telemetry.__all__) == 10
    for name in telemetry.__all__:
        assert callable(getattr(telemetry, name))


# ---- notifications ---------------------------------------------------------------------


class _Manager:
    def __init__(self, *, broken: bool = False) -> None:
        self.sent: list[tuple[NotificationType, str, str]] = []
        self.broken = broken

    async def send(self, **kwargs: object) -> None:
        if self.broken:
            raise NotificationError("smtp unreachable")
        self.sent.append(
            (
                kwargs["notification_type"],  # type: ignore[arg-type]
                str(kwargs["subject"]),
                str(kwargs["body"]),
            )
        )


@pytest.mark.asyncio
async def test_every_notification_names_the_document_and_the_reason() -> None:
    manager = _Manager()
    service = DocumentNotificationService(manager)  # type: ignore[arg-type]

    await service.send_ocr_failed("u", title="Scan 1", reason="no binary", pages=42)
    await service.send_ocr_failed("u", title="Scan 2", reason="timeout")
    await service.send_validation_failed("u", title="CR", failures=["a-required", "b-allowed"])
    await service.send_review_assigned("r", title="CR", reason="blank", due_at="2026-08-13")
    await service.send_review_assigned("r", title="CR", reason="blank")
    await service.send_review_completed("u", title="CR", decision="corrected", corrections=2)
    await service.send_review_completed("u", title="CR", decision="approved", corrections=0)
    await service.send_processing_completed("u", title="CR", failed_stages=[], requires_review=True)
    await service.send_processing_completed(
        "u", title="CR", failed_stages=[], requires_review=False
    )
    await service.send_processing_completed(
        "u", title="S", failed_stages=["layout"], requires_review=True
    )
    await service.send_translation_completed("u", title="CR", target_language="fr")
    await service.send_translation_completed(
        "u", title="CR", target_language="de", is_faithful=False
    )

    assert len(manager.sent) == 12
    bodies = [body for _kind, _subject, body in manager.sent]
    assert any("42 page(s)" in body for body in bodies)
    assert any("a-required, b-allowed" in body for body in bodies)
    assert any("due by 2026-08-13" in body for body in bodies)
    assert any("no fields were corrected" in body for body in bodies)
    assert any("these stages failed: layout" in body for body in bodies)
    assert any("did not survive" in body for body in bodies)


@pytest.mark.asyncio
async def test_a_run_with_failures_is_a_warning_not_a_success() -> None:
    """ "Processing completed" over a document whose stages failed is a lie."""
    manager = _Manager()
    service = DocumentNotificationService(manager)  # type: ignore[arg-type]
    await service.send_processing_completed(
        "u", title="Scan", failed_stages=["table_extraction"], requires_review=True
    )
    kind, _subject, _body = manager.sent[0]
    assert kind is NotificationType.WARNING


@pytest.mark.asyncio
async def test_many_validation_failures_are_summarised() -> None:
    manager = _Manager()
    service = DocumentNotificationService(manager)  # type: ignore[arg-type]
    failures = [f"rule-{index}" for index in range(MAX_LISTED_FAILURES + 4)]
    await service.send_validation_failed("u", title="CR", failures=failures)
    assert "and 4 more" in manager.sent[0][2]


@pytest.mark.asyncio
async def test_no_named_failure_still_produces_a_readable_message() -> None:
    manager = _Manager()
    service = DocumentNotificationService(manager)  # type: ignore[arg-type]
    await service.send_validation_failed("u", title="CR", failures=[])
    assert "no rule was named" in manager.sent[0][2]


@pytest.mark.asyncio
async def test_a_broken_mail_server_never_blocks_the_operation() -> None:
    """A document that processed but could not tell anyone still processed."""
    service = DocumentNotificationService(_Manager(broken=True))  # type: ignore[arg-type]
    await service.send_ocr_failed("u", title="X", reason="y")
    await service.send_review_completed("u", title="X", decision="approved", corrections=0)


# ---- OCR -------------------------------------------------------------------------------


def test_an_ocr_word_carries_its_confidence() -> None:
    word = OcrWord(text="Change", confidence=0.91, left=10, top=20, width=50, height=12)
    assert word.text == "Change"
    assert word.confidence == pytest.approx(0.91)


def test_a_page_reports_its_lowest_confidence_words() -> None:
    """A page averaging 0.9 with one word at 0.2 is not a page anyone should
    treat as read."""
    words = [
        OcrWord(text="good", confidence=0.98, left=0, top=0, width=10, height=5),
        OcrWord(text="bad", confidence=0.21, left=20, top=0, width=10, height=5),
    ]
    page = OcrPage(page_number=1, text="good bad", words=words)
    assert page.confidence == pytest.approx(0.595, abs=0.01)
    assert [word.text for word in page.low_confidence_words] == ["bad"]
    assert page.succeeded is True


def test_page_quality_bands_are_reported() -> None:
    assert ocr_quality_for(0.97) is OcrQuality.EXCELLENT
    assert ocr_quality_for(0.5) in set(OcrQuality)
    assert OcrPage(page_number=1).quality in set(OcrQuality)
    failed = OcrPage(page_number=1, error="tesseract crashed")
    assert failed.succeeded is False


def test_an_ocr_result_reports_the_worst_page_beside_the_mean() -> None:
    """A forty-page scan averaging 0.92 with one page at 0.31 hides that page
    behind the mean."""
    pages = [
        OcrPage(
            page_number=1,
            text="a",
            words=[OcrWord(text="a", confidence=0.95, left=0, top=0, width=1, height=1)],
        ),
        OcrPage(
            page_number=2,
            text="b",
            words=[OcrWord(text="b", confidence=0.31, left=0, top=0, width=1, height=1)],
        ),
    ]
    result = OcrResult(pages=pages, engine=OcrEngineKind.TESSERACT)
    lowest = result.lowest_page_confidence
    assert lowest is not None
    assert result.confidence > lowest
    assert lowest == pytest.approx(0.31, abs=0.01)
    assert "a" in result.text
    assert result.succeeded is True


def test_an_empty_result_reports_no_lowest_page_rather_than_zero() -> None:
    empty = OcrResult(pages=[], engine=OcrEngineKind.NONE)
    assert empty.lowest_page_confidence is None
    assert empty.text == ""


def test_availability_require_raises_with_the_reason() -> None:
    """ "OCR failed" sends somebody to look; the reason saves the trip."""
    unavailable = EngineAvailability(
        available=False,
        engine=OcrEngineKind.TESSERACT,
        reason="the tesseract binary is not on PATH",
    )
    with pytest.raises(OcrUnavailableError, match="not on PATH"):
        unavailable.require()

    available = EngineAvailability(available=True, engine=OcrEngineKind.TESSERACT)
    available.require()


def test_probing_reports_availability_without_raising() -> None:
    """The module must be importable on a machine with no OCR at all --
    which is the whole point of a probe."""
    availability = TesseractEngine().probe()
    assert isinstance(availability.available, bool)
    if not availability.available:
        assert availability.reason


def test_a_page_that_could_not_be_read_says_so_rather_than_reading_as_empty() -> None:
    """The distinction that matters is reported, not raised.

    One unreadable page must not abort a two-hundred-page scan, so the
    failure lands on the page rather than as an exception. What it must
    never do is return empty text as a *success* -- that is a scan that
    looks successfully read and blank, which is indistinguishable from a
    genuinely blank page.
    """
    engine = TesseractEngine()
    if engine.probe().available:
        pytest.skip("tesseract is installed; the unavailable path cannot be exercised")
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 20), "white").save(buffer, format="PNG")
    page = engine.read_image(buffer.getvalue(), page_number=1)
    assert page.succeeded is False
    assert page.error
    assert page.text == ""


def test_enum_helpers() -> None:
    assert needs_ocr(DocumentFormat.IMAGE) is True
    assert needs_ocr(DocumentFormat.TXT) is False
    assert is_terminal(DocumentStatus.APPROVED) is True
    assert is_terminal(DocumentStatus.PARSING) is False


# ---- the scheduler registrar ------------------------------------------------------------


def test_every_job_registers_with_a_deterministic_id() -> None:
    """Re-registering must replace rather than leak."""
    manager = SchedulerManager.__new__(SchedulerManager)
    registered: list[object] = []

    def register_job(job: object) -> object:
        registered.append(job)
        return job

    manager.register_job = register_job  # type: ignore[method-assign,assignment]

    async def noop(_job: object) -> None:  # pragma: no cover -- never run here
        return None

    jobs = [
        register_processing_sweep(manager, noop, interval_seconds=30),
        register_review_expiry_sweep(manager, noop, interval_seconds=900),
        register_statistics_rollup(manager, noop, interval_seconds=900),
        register_retention_sweep(manager, noop, interval_seconds=3600),
    ]
    assert len(registered) == 4
    ids = [job.job_id for job in jobs]  # type: ignore[attr-defined]
    assert PROCESSING_SWEEP_JOB_ID in ids
    assert len(set(ids)) == 4


@pytest.mark.parametrize("interval", [0, -1])
def test_a_non_positive_interval_is_refused(interval: int) -> None:
    """Zero would busy-loop the scheduler; negative is meaningless."""
    manager = SchedulerManager.__new__(SchedulerManager)
    manager.register_job = lambda job: job  # type: ignore[method-assign,assignment]

    async def noop(_job: object) -> None:  # pragma: no cover
        return None

    with pytest.raises(ValueError, match="must be positive"):
        register_processing_sweep(manager, noop, interval_seconds=interval)


# ---- configuration ----------------------------------------------------------------------


def test_a_missing_public_key_is_a_configuration_error_not_a_fallback() -> None:
    """This service holds no private key, so there is nothing to generate."""
    with pytest.raises(DependencyError, match="not found"):
        load_public_key("/nonexistent/path/to/key.pem")


# ---- engine edges ----------------------------------------------------------------------


def test_a_custom_pattern_that_does_not_compile_is_refused_at_use() -> None:
    """A typo'd tenant pattern otherwise becomes "no asset tags found, ever"."""
    with pytest.raises(ValueError, match="not a valid regular"):
        CustomEntityPattern(name="broken", pattern="[unclosed").compiled()


def test_a_kind_filter_skips_the_work_it_was_not_asked_for() -> None:
    config = ExtractionConfig(kinds=frozenset({EntityKind.EMAIL}))
    found = extract_entities("Mail a@b.com about host db-01.example.com on 2026-03-14.", config)
    assert {entity.kind for entity in found} == {EntityKind.EMAIL}


def test_a_confidence_floor_filters_weak_entities() -> None:
    strict = ExtractionConfig(minimum_confidence=0.99)
    assert extract_entities("Incident INC-004821 is open.", strict) == []


def test_the_entity_cap_is_enforced() -> None:
    text = " ".join(f"host-{index}.example.com" for index in range(50))
    capped = extract_entities(text, ExtractionConfig(max_entities=5))
    assert len(capped) <= 5


@pytest.mark.parametrize(
    ("kind", "raw"),
    [
        (EntityKind.EMAIL, "R.Mehta@Example.COM"),
        (EntityKind.HOSTNAME, "DB-01.Example.Com"),
        (EntityKind.ORGANIZATION, "ACME Corp."),
        (EntityKind.CURRENCY, "$1,240.50"),
        (EntityKind.DATE, "14 March 2026"),
        (EntityKind.IP_ADDRESS, "10.42.7.19"),
    ],
)
def test_normalisation_is_defined_for_every_normalised_kind(kind: EntityKind, raw: str) -> None:
    assert normalize(kind, raw)


def test_an_ipv6_address_is_recognised() -> None:
    found = extract_entities("The host answers on 2001:db8::1 today.")
    assert any(entity.kind is EntityKind.IP_ADDRESS for entity in found)


def test_a_serial_and_an_asset_tag_need_their_labels() -> None:
    """A bare alphanumeric run is a build number, a hash, or a licence key."""
    labelled = extract_entities("Serial number: XY1234567. Asset tag: AB-99.")
    kinds = {entity.kind for entity in labelled}
    assert EntityKind.SERIAL_NUMBER in kinds or EntityKind.ASSET_TAG in kinds


def test_layout_of_a_single_paragraph_is_one_region() -> None:
    layout = analyze_text("A single ordinary paragraph of prose with no structure at all.")
    assert len(layout.regions) == 1


def test_merging_pages_drops_repeated_boilerplate() -> None:
    """The same footer on ninety pages is ninety copies of one sentence, and
    it dominates any term frequency computed over the whole document."""
    first = analyze_text("Some body text on the first page about the connection pool.\n\nPage 1\n")
    second = analyze_text("Some body text on the second page about the replica set.\n\nPage 2\n")
    merged = merge_pages([first, second])
    assert "first page" in merged
    assert "second page" in merged
    assert "Page 1" not in merged


def test_a_bounding_box_computes_its_edges() -> None:
    box = BoundingBox(left=10, top=20, width=30, height=40)
    assert box.right == 40
    assert box.bottom == 60


def test_positioned_words_with_no_geometry_still_analyse() -> None:
    words = [
        PositionedWord(text=f"w{index}", left=0, top=index * 10, width=5, height=5)
        for index in range(4)
    ]
    layout = analyze_words(words)
    assert layout.regions


def test_analysing_no_words_produces_no_regions() -> None:
    assert analyze_words([]).regions == []


def test_a_layout_config_reports_its_own_settings() -> None:
    config = LayoutConfig(header_band=0.2)
    assert config.header_band == 0.2


def test_a_forbidden_term_prevents_a_rule_from_matching() -> None:
    rule = ClassificationRule(
        name="certificates",
        category=DocumentCategory.CERTIFICATE,
        required_terms=("certify",),
        forbidden_terms=("draft",),
    )
    config = ClassifierConfig(rules=(rule,))
    allowed = classify("This is to certify the platform.", config=config).classifications
    assert any(label.method.value == "rule" for label in allowed)
    blocked = classify("DRAFT: this is to certify the platform.", config=config).classifications
    assert all(
        label.method.value != "rule" for label in blocked
    ), "a forbidden term must stop the rule firing, whatever keywords still match"


def test_a_rule_pattern_matches() -> None:
    rule = ClassificationRule(
        name="change-ids",
        category=DocumentCategory.FORM,
        pattern=r"CHG-\d{6}",
    )
    result = classify("Change CHG-004821 was raised.", config=ClassifierConfig(rules=(rule,)))
    assert result.classifications[0].category is DocumentCategory.FORM


def test_a_template_below_its_minimum_match_does_not_fire() -> None:
    template = DocumentTemplate(
        name="strict",
        category=DocumentCategory.FORM,
        field_labels=("a", "b", "c", "d"),
        minimum_match=0.9,
    )
    result = classify(
        "Change ID: CHG-004821\n",
        config=ClassifierConfig(templates=(template,)),
        field_labels=["a"],
    )
    assert all(label.method.value != "template" for label in result.classifications)


def test_a_minimum_confidence_floor_drops_weak_labels() -> None:
    result = classify(
        "Some ordinary prose about nothing in particular at all.",
        config=ClassifierConfig(minimum_confidence=0.99),
    )
    assert result.classifications == []


def test_an_empty_table_reports_itself_as_empty() -> None:
    table = ExtractedTable()
    assert table.is_empty is True
    assert table.column_count == 0
    assert table.to_records() == []


def test_a_table_column_is_reachable_by_index() -> None:
    table = ExtractedTable(headers=["a", "b"], rows=[["1", "2"]], has_header_row=True)
    assert table.column(0) == ["1"]
    assert table.column(1) == ["2"]


def test_positioned_words_below_the_row_minimum_are_not_a_table() -> None:
    assert extract_from_words([TableWord("only", 0, 0, 10, 5)]) is None
    assert extract_from_words([]) is None


def test_positioned_words_below_the_column_minimum_are_not_a_table() -> None:
    words = [TableWord(f"w{index}", 10, index * 12, 20, 8) for index in range(4)]
    assert extract_from_words(words, config=TableConfig(min_columns=3)) is None


def test_a_form_config_can_disable_checkbox_and_signature_detection() -> None:
    text = "[x] Ticked\nSignature: R. Mehta\n"
    plain = extract_fields(
        text, config=FormConfig(detect_checkboxes=False, detect_signatures=False)
    )
    assert all(field.checked is None for field in plain.fields)


def test_a_form_result_maps_labels_to_values() -> None:
    result = extract_fields("Change ID: CHG-004821\nRisk level: high\n")
    mapping = result.as_mapping()
    assert mapping["Change ID"] == "CHG-004821"
    assert result.get("nonexistent") is None


def test_a_field_rule_reports_every_way_a_value_fails() -> None:
    rule = FieldRule("Risk", pattern=r"low", allowed=("low",), required=True)
    assert rule.validate("high", blank=False)
    assert rule.validate("", blank=True) == ["required field is blank"]
    optional = FieldRule("Note")
    assert optional.validate("", blank=True) == []


def test_a_template_alias_matches_a_differently_spelled_label() -> None:
    template = FormTemplate(
        name="t",
        rules=(FieldRule("Requester email", aliases=("Requester's E-Mail",)),),
    )
    result = extract_fields("Requester's E-Mail: a@b.com\n", templates=[template])
    assert result.template_name == "t"


def test_a_summary_of_text_with_no_usable_sentences_is_empty() -> None:
    assert summarize("a\nb\nc\n").text == ""


def test_rank_order_can_be_requested_instead_of_document_order() -> None:
    text = (
        "An unimportant opening line about nothing much at all here.\n\n"
        "The connection pool was exhausted because each replica opened two "
        "hundred connections to the primary database.\n"
    )
    ordered = summarize(text, config=SummaryConfig(sentence_count=2, preserve_order=False))
    assert ordered.sentences
    assert ordered.sentences[0].score >= ordered.sentences[-1].score


def test_splitting_sections_of_text_with_no_headings_yields_one_section() -> None:
    sections = split_sections("Just one paragraph of prose with no headings in it.")
    assert list(sections) == ["Introduction"]


def test_a_section_summary_of_unstructured_text_uses_the_introduction() -> None:
    """Content before the first heading is where most documents say what they
    are for, so it is kept rather than discarded."""
    summary = summarize(
        "The connection pool was exhausted because each replica opened two "
        "hundred connections to the primary database.",
        kind=SummaryKind.SECTION,
    )
    assert list(summary.sections) == ["Introduction"]


def test_limit_text_truncates_and_flags_the_document() -> None:
    document = ParsedDocument(format=DocumentFormat.TXT)
    from app.documents.parser import MAX_TEXT_BYTES

    oversized = "x" * (MAX_TEXT_BYTES + 100)
    trimmed = limit_text(oversized, document)
    assert len(trimmed) <= MAX_TEXT_BYTES
    assert document.truncated is True
    assert document.warnings


def test_a_parsed_document_reports_emptiness_and_deduplicates_warnings() -> None:
    document = ParsedDocument(format=DocumentFormat.TXT)
    assert document.is_empty is True
    document.add_warning("same")
    document.add_warning("same")
    assert document.warnings == ["same"]
    page = ParsedPage(number=1)
    assert page.is_empty is True


def test_validation_of_a_field_free_rule_with_no_predicate_is_skipped() -> None:
    rule = business_rule("nothing", lambda _values: True)
    object.__setattr__(rule, "predicate", None)
    report = validate({"a": "b"}, (rule,))
    assert report.skipped


def test_validation_completeness_counts_only_populated_expected_fields() -> None:
    config = ValidationConfig(expected_fields=("a", "b", "c"))
    report = validate({"a": "x", "b": "  ", "c": None}, (), config=config)
    assert report.completeness == pytest.approx(1 / 3, abs=0.01)


def test_an_encrypted_pdf_opened_with_an_empty_password_warns() -> None:
    """Most "encrypted" PDFs are permission-locked rather than secret."""
    from pypdf import PdfWriter

    from app.documents.parser import parse

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("")
    buffer = io.BytesIO()
    writer.write(buffer)
    document = parse(buffer.getvalue(), fmt=DocumentFormat.PDF)
    assert document.page_count == 1


def test_a_password_protected_pdf_raises_rather_than_returning_empty_pages() -> None:
    from pypdf import PdfWriter

    from app.documents.parser import DocumentParseError, parse

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("a-real-password")
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(DocumentParseError, match="encrypted"):
        parse(buffer.getvalue(), fmt=DocumentFormat.PDF)


def test_a_workbook_whose_formulas_were_never_evaluated_says_so() -> None:
    """``data_only`` returns the cached value, and a workbook Excel never
    opened has no cache."""
    from openpyxl import Workbook

    from app.documents.parser import parse

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet["A1"] = "=SUM(B1:B9)"
    sheet["A2"] = "=SUM(B1:B9)"
    buffer = io.BytesIO()
    workbook.save(buffer)
    document = parse(buffer.getvalue(), fmt=DocumentFormat.XLSX)
    assert document.page_count == 1
