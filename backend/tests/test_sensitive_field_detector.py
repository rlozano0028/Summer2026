"""Tests for the Phase 5 sensitive-field detector."""

from __future__ import annotations

from app.models.automation import FormField
from app.models.field_mapping import FieldCategory
from app.services.field_context_builder import build_field_context
from app.services.sensitive_field_detector import detect_sensitive


def _context(**kwargs):
    defaults = dict(field_id="f0", selector="#f0", tag_name="input", input_type="text")
    defaults.update(kwargs)
    return build_field_context(FormField(**defaults))


def test_detects_work_authorization() -> None:
    match = detect_sensitive(_context(label_text="Are you legally authorized to work?"))
    assert match.sensitive is True
    assert match.category == FieldCategory.SENSITIVE_WORK_AUTHORIZATION.value


def test_detects_sponsorship() -> None:
    match = detect_sensitive(_context(label_text="Will you require visa sponsorship?"))
    assert match.sensitive is True
    assert match.category == FieldCategory.SENSITIVE_SPONSORSHIP.value


def test_detects_salary() -> None:
    match = detect_sensitive(_context(label_text="Desired salary"))
    assert match.sensitive is True
    assert match.category == FieldCategory.SENSITIVE_SALARY.value


def test_detects_demographic() -> None:
    match = detect_sensitive(_context(label_text="Race / Ethnicity"))
    assert match.sensitive is True
    assert match.category == FieldCategory.SENSITIVE_DEMOGRAPHIC.value
    gender = detect_sensitive(_context(label_text="Gender"))
    assert gender.sensitive is True


def test_detects_disability_and_veteran() -> None:
    disability = detect_sensitive(_context(label_text="Disability status"))
    assert disability.sensitive is True
    assert disability.category == FieldCategory.SENSITIVE_DISABILITY.value
    veteran = detect_sensitive(_context(label_text="Protected veteran status"))
    assert veteran.sensitive is True
    assert veteran.category == FieldCategory.SENSITIVE_VETERAN.value


def test_detects_legal_acknowledgment() -> None:
    match = detect_sensitive(
        _context(label_text="I certify the information is accurate and I agree to the terms")
    )
    assert match.sensitive is True
    assert match.category == FieldCategory.SENSITIVE_LEGAL_ACKNOWLEDGMENT.value


def test_detects_government_id_and_dob() -> None:
    ssn = detect_sensitive(_context(label_text="Social Security Number"))
    assert ssn.sensitive is True
    dob = detect_sensitive(_context(label_text="Date of birth"))
    assert dob.sensitive is True


def test_does_not_flag_normal_fields() -> None:
    assert detect_sensitive(_context(label_text="Email address")).sensitive is False
    assert detect_sensitive(_context(label_text="First name")).sensitive is False
    assert detect_sensitive(_context(label_text="City")).sensitive is False
