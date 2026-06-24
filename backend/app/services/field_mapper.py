"""Explainable field-mapping engine (Phase 5).

This module turns enriched :class:`FieldContext` data into an explainable
mapping decision for each field. It is deterministic and rule-based - it does
NOT use AI and never guesses a value the profile does not contain.

Pipeline per field:
1. Skip submit/hidden/disabled/readonly controls.
2. Detect sensitive / legal fields (always manual review, never autofilled).
3. Classify the field into a :class:`FieldCategory` using weighted evidence.
4. Apply a local user override if one exists (sensitive force-fills are
   downgraded to manual review with a warning).
5. Resolve the profile value (redacted preview only).
6. Decide the action (fill / suggest / manual_review / skip) from evidence-based
   confidence and field type.

Public API (kept backward-compatible with Phase 4):
- :func:`map_field_to_profile` - decide what to do with a single field.
- :func:`build_fill_plan` - map every field and summarize the result.
- :func:`resolve_fill_value` - resolve the real value the runner should type.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FieldMapping,
    FillPlan,
    FormField,
)
from app.models.candidate_profile import CandidateProfile
from app.models.field_mapping import (
    SENSITIVE_CATEGORIES,
    FieldCategory,
    FieldClassification,
    FieldContext,
    MappingOverride,
    MatchEvidence,
)
from app.services import field_mapping_overrides
from app.services.field_context_builder import build_field_context, normalize_field_text
from app.services.field_value_resolver import (
    CATEGORY_TO_PROFILE_PATH,
    resolve_profile_value,
    resolve_raw_value,
)
from app.services.sensitive_field_detector import detect_sensitive

# Confidence thresholds (shared with the docs and frontend).
FILL_THRESHOLD = 0.90
SUGGEST_THRESHOLD = 0.60
# When two categories are this close, the decision is flagged ambiguous.
AMBIGUITY_MARGIN = 0.15

# Reliability multiplier per evidence source. Labels and aria-labels are the
# most trustworthy; nearby text and option text are the weakest.
SOURCE_WEIGHTS: dict[str, float] = {
    "label": 1.0,
    "aria_label": 1.0,
    "autocomplete": 1.0,
    "name": 0.98,
    "placeholder": 0.97,
    "id": 0.95,
    "nearby_text": 0.8,
    "option_text": 0.65,
}


class ClassRule:
    """A keyword rule that votes for a category with a given specificity."""

    def __init__(self, category: str, keywords: tuple[str, ...], specificity: float) -> None:
        self.category = category
        self.keywords = keywords
        self.specificity = specificity


# Ordered classification rules. Multiple rules may target the same category with
# different specificity (e.g. "portfolio" is stronger than "website").
CLASSIFICATION_RULES: list[ClassRule] = [
    # Identity.
    ClassRule(FieldCategory.IDENTITY_FIRST_NAME.value, ("first name", "given name", "firstname", "fname"), 0.95),
    ClassRule(FieldCategory.IDENTITY_LAST_NAME.value, ("last name", "family name", "surname", "lastname", "lname"), 0.95),
    ClassRule(FieldCategory.IDENTITY_FULL_NAME.value, ("full name", "fullname", "legal name", "complete name"), 0.9),
    ClassRule(FieldCategory.IDENTITY_EMAIL.value, ("email", "e mail", "email address"), 0.95),
    ClassRule(FieldCategory.IDENTITY_PHONE.value, ("phone", "telephone", "mobile", "phone number", "cell"), 0.93),
    ClassRule(FieldCategory.IDENTITY_CITY.value, ("city", "town"), 0.9),
    ClassRule(FieldCategory.IDENTITY_STATE.value, ("state", "province", "region"), 0.88),
    ClassRule(FieldCategory.IDENTITY_COUNTRY.value, ("country", "nation"), 0.9),
    # Links.
    ClassRule(FieldCategory.LINKS_LINKEDIN.value, ("linkedin",), 0.96),
    ClassRule(FieldCategory.LINKS_GITHUB.value, ("github",), 0.96),
    ClassRule(FieldCategory.LINKS_PORTFOLIO.value, ("portfolio", "personal website", "personal site"), 0.9),
    ClassRule(FieldCategory.LINKS_PORTFOLIO.value, ("website", "web site", "personal url", "url"), 0.65),
    # Skills (specific before combined).
    ClassRule(FieldCategory.SKILLS_PROGRAMMING_LANGUAGES.value, ("programming language", "programming languages", "coding languages"), 0.92),
    ClassRule(FieldCategory.SKILLS_FRAMEWORKS.value, ("framework", "frameworks", "library", "libraries"), 0.92),
    ClassRule(FieldCategory.SKILLS_DATABASES.value, ("database", "databases"), 0.92),
    ClassRule(FieldCategory.SKILLS_CLOUD.value, ("cloud", "cloud platform", "cloud platforms", "cloud provider"), 0.92),
    ClassRule(FieldCategory.SKILLS_TOOLS.value, ("tools", "tooling", "developer tools"), 0.9),
    ClassRule(FieldCategory.SKILLS_COMBINED.value, ("skills", "skill", "technical skills"), 0.9),
    # Education / experience: deliberately "suggest" grade (below fill).
    ClassRule(FieldCategory.EDUCATION_SCHOOL.value, ("school", "university", "college", "institution", "alma mater"), 0.7),
    ClassRule(FieldCategory.EDUCATION_DEGREE.value, ("degree",), 0.7),
    ClassRule(FieldCategory.EDUCATION_MAJOR.value, ("major", "field of study", "concentration", "area of study"), 0.7),
    ClassRule(FieldCategory.EXPERIENCE_COMPANY.value, ("company", "employer", "organization"), 0.7),
    ClassRule(FieldCategory.EXPERIENCE_TITLE.value, ("job title", "title", "position", "role"), 0.7),
]

# Standardized HTML autocomplete tokens -> (category, specificity).
AUTOCOMPLETE_TOKENS: dict[str, tuple[str, float]] = {
    "given-name": (FieldCategory.IDENTITY_FIRST_NAME.value, 0.97),
    "family-name": (FieldCategory.IDENTITY_LAST_NAME.value, 0.97),
    "name": (FieldCategory.IDENTITY_FULL_NAME.value, 0.9),
    "email": (FieldCategory.IDENTITY_EMAIL.value, 0.97),
    "tel": (FieldCategory.IDENTITY_PHONE.value, 0.95),
    "tel-national": (FieldCategory.IDENTITY_PHONE.value, 0.95),
    "address-level2": (FieldCategory.IDENTITY_CITY.value, 0.9),
    "address-level1": (FieldCategory.IDENTITY_STATE.value, 0.88),
    "country": (FieldCategory.IDENTITY_COUNTRY.value, 0.9),
    "country-name": (FieldCategory.IDENTITY_COUNTRY.value, 0.9),
    "url": (FieldCategory.LINKS_PORTFOLIO.value, 0.72),
}

# Keywords that mark a free-text custom answer (manual review).
_COVER_LETTER_KEYWORDS: tuple[str, ...] = ("cover letter",)
_SHORT_ANSWER_KEYWORDS: tuple[str, ...] = (
    "why interested",
    "why are you interested",
    "tell us about yourself",
    "about yourself",
    "motivation",
    "essay",
    "short answer",
    "additional information",
)
_RESUME_KEYWORDS: tuple[str, ...] = ("resume", "cv", "curriculum vitae")


def _matches(normalized_source: str, keyword: str) -> bool:
    """Phrase keywords match as substrings; single words match whole tokens."""

    if not normalized_source:
        return False
    if " " in keyword:
        return keyword in normalized_source
    return keyword in normalized_source.split(" ")


def _combine(weights: list[float]) -> float:
    """Probabilistic OR of evidence weights, clamped to <= 0.99."""

    product = 1.0
    for weight in weights:
        product *= 1.0 - max(0.0, min(1.0, weight))
    return min(0.99, 1.0 - product)


def _sources(context: FieldContext) -> list[tuple[str, str]]:
    """Return (source_name, normalized_text) pairs to scan for keywords."""

    pairs = [
        ("label", normalize_field_text(context.label_text or "")),
        ("placeholder", normalize_field_text(context.placeholder or "")),
        ("aria_label", normalize_field_text(context.aria_label or "")),
        ("name", normalize_field_text(context.name or "")),
        ("id", normalize_field_text(context.id_attribute or "")),
        ("nearby_text", normalize_field_text(context.nearby_text or "")),
    ]
    if context.options:
        option_text = normalize_field_text(" ".join(context.options))
        pairs.append(("option_text", option_text))
    return pairs


def classify_field(context: FieldContext) -> FieldClassification:
    """Classify a field into a category with evidence-based confidence."""

    # category -> list of (weight, evidence)
    scored: dict[str, list[MatchEvidence]] = {}

    def add(category: str, source: str, matched_text: str, specificity: float) -> None:
        weight = specificity * SOURCE_WEIGHTS.get(source, 0.5)
        scored.setdefault(category, []).append(
            MatchEvidence(
                source=source,
                matched_text=matched_text,
                matched_rule=category,
                weight=round(weight, 4),
            )
        )

    sources = _sources(context)
    for rule in CLASSIFICATION_RULES:
        for source_name, text in sources:
            if not text:
                continue
            for keyword in rule.keywords:
                if _matches(text, keyword):
                    add(rule.category, source_name, keyword, rule.specificity)
                    break  # one evidence per (rule, source)

    # Autocomplete is a standardized, high-trust signal.
    if context.autocomplete:
        token = context.autocomplete.strip().lower()
        if token in AUTOCOMPLETE_TOKENS:
            category, specificity = AUTOCOMPLETE_TOKENS[token]
            add(category, "autocomplete", token, specificity)

    if not scored:
        return FieldClassification(
            field_id=context.field_id, category=FieldCategory.UNKNOWN.value, confidence=0.0
        )

    category_scores: dict[str, float] = {
        cat: _combine([ev.weight for ev in evidence]) for cat, evidence in scored.items()
    }
    ranked = sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)
    top_category, top_score = ranked[0]

    ambiguous = False
    ambiguity_reason: Optional[str] = None
    if len(ranked) > 1:
        second_category, second_score = ranked[1]
        if second_score >= SUGGEST_THRESHOLD and (top_score - second_score) < AMBIGUITY_MARGIN:
            ambiguous = True
            ambiguity_reason = (
                f"Conflicting evidence between '{top_category}' and "
                f"'{second_category}'."
            )
            top_score *= 0.8  # reduce confidence on conflict

    return FieldClassification(
        field_id=context.field_id,
        category=top_category,
        confidence=round(min(0.99, top_score), 4),
        evidence=scored[top_category],
        ambiguous=ambiguous,
        ambiguity_reason=ambiguity_reason,
    )


# --- Backward-compatible value resolution -----------------------------------


def resolve_fill_value(profile: CandidateProfile, profile_path: Optional[str]) -> Optional[str]:
    """Resolve the real string value for a profile path (used by the runner)."""

    return resolve_raw_value(profile, profile_path)


# --- Mapping decision --------------------------------------------------------


def _label_for(field: FormField | FieldContext) -> str:
    return field.label_text or field.name or field.id_attribute or field.field_id


def _skip(field_id: str, selector: str, reason: str, category: str) -> FieldMapping:
    return FieldMapping(
        field_id=field_id, selector=selector, action=ACTION_SKIP, reason=reason, category=category
    )


def _apply_override(
    context: FieldContext,
    override: MappingOverride,
    profile: CandidateProfile,
    classification: FieldClassification,
) -> FieldMapping:
    """Apply a user override, refusing to autofill sensitive fields."""

    evidence = list(classification.evidence)
    evidence.append(
        MatchEvidence(
            source="override",
            matched_text=override.category,
            matched_rule="user override",
            weight=1.0,
        )
    )
    warnings: list[str] = []

    field_is_sensitive = classification.sensitive
    override_is_sensitive = override.category in SENSITIVE_CATEGORIES

    # Safety: never let an override force-fill a sensitive field.
    if (field_is_sensitive or override_is_sensitive) and override.action == ACTION_FILL:
        warnings.append(
            "Override requested autofill of a sensitive field; downgraded to "
            "manual review for safety."
        )
        return FieldMapping(
            field_id=context.field_id,
            selector=context.selector,
            category=override.category,
            action=ACTION_MANUAL_REVIEW,
            reason="Sensitive field - overrides cannot force autofill.",
            sensitive=True,
            evidence=evidence,
            warnings=warnings,
        )

    if override.action in (ACTION_SKIP, ACTION_MANUAL_REVIEW):
        return FieldMapping(
            field_id=context.field_id,
            selector=context.selector,
            category=override.category,
            profile_path=override.profile_path,
            action=override.action,
            reason=f"User override: {override.action}." + (f" {override.note}" if override.note else ""),
            sensitive=field_is_sensitive,
            evidence=evidence,
            warnings=warnings,
        )

    # fill / suggest: resolve a value first.
    resolution = resolve_profile_value(profile, override.category)
    if not resolution.value_exists:
        return FieldMapping(
            field_id=context.field_id,
            selector=context.selector,
            category=override.category,
            profile_path=resolution.profile_path or override.profile_path,
            action=ACTION_MANUAL_REVIEW,
            reason="Override set but profile has no value for this field.",
            missing_value=True,
            evidence=evidence,
            warnings=warnings,
        )

    return FieldMapping(
        field_id=context.field_id,
        selector=context.selector,
        category=override.category,
        profile_path=resolution.profile_path,
        value_preview=resolution.value_preview,
        confidence=max(classification.confidence, 0.9 if override.action == ACTION_FILL else 0.6),
        action=override.action,
        reason=f"User override: {override.action}." + (f" {override.note}" if override.note else ""),
        evidence=evidence,
        warnings=warnings,
    )


def _decide_text_action(confidence: float) -> tuple[str, str]:
    if confidence >= FILL_THRESHOLD:
        return ACTION_FILL, "High-confidence, non-sensitive match - will autofill."
    if confidence >= SUGGEST_THRESHOLD:
        return ACTION_SUGGEST, "Probable match - suggested for review before filling."
    return ACTION_MANUAL_REVIEW, "Low-confidence match - left for manual review."


def map_field_to_profile(
    field: FormField,
    profile: CandidateProfile,
    *,
    override: Optional[MappingOverride] = None,
) -> FieldMapping:
    """Decide how to handle a single detected field. Never guesses values."""

    context = build_field_context(field)

    # 1. Submit / button controls and hidden fields are skipped.
    if context.is_submit_control or context.tag_name == "button":
        return _skip(context.field_id, context.selector, "Submit / button control - never autofilled.", FieldCategory.UNKNOWN.value)
    if context.input_type == "hidden" or not context.visible:
        return _skip(context.field_id, context.selector, "Hidden field - skipped.", FieldCategory.UNKNOWN.value)
    # 2. Disabled / readonly fields cannot be filled.
    if context.disabled or context.readonly:
        return _skip(context.field_id, context.selector, "Field is disabled or readonly.", FieldCategory.UNKNOWN.value)

    # 3. Classify + sensitive detection.
    classification = classify_field(context)
    sensitive = detect_sensitive(context)
    if sensitive.sensitive:
        classification.sensitive = True
        classification.sensitive_reason = sensitive.reason
        classification.category = sensitive.category or classification.category

    # 4. Override (if any) wins next, with the sensitive safety guard inside.
    if override is not None:
        return _apply_override(context, override, profile, classification)

    # 5. Sensitive / legal fields: always manual review, never autofilled.
    if classification.sensitive:
        return FieldMapping(
            field_id=context.field_id,
            selector=context.selector,
            category=classification.category,
            action=ACTION_MANUAL_REVIEW,
            reason=f"Sensitive / legal field ({sensitive.reason}) - must be answered manually.",
            sensitive=True,
            confidence=classification.confidence,
            evidence=classification.evidence,
            warnings=[f"Sensitive field left for manual review: {_label_for(context)}"],
        )

    # 6. File uploads: need an explicit local file (handled by the runner).
    if context.is_file_upload:
        is_resume = any(_matches(context.normalized_text, kw) for kw in _RESUME_KEYWORDS)
        category = FieldCategory.RESUME_FILE.value if is_resume else FieldCategory.UNKNOWN.value
        reason = (
            "Resume upload: provide an explicit local resume file to attach; left for manual review."
            if is_resume
            else "File upload left for manual review."
        )
        return FieldMapping(
            field_id=context.field_id,
            selector=context.selector,
            category=category,
            action=ACTION_MANUAL_REVIEW,
            reason=reason,
            warnings=[f"File upload left for manual review: {_label_for(context)}"],
        )

    # 7. Free-text essays / cover letters require a custom answer.
    if any(_matches(context.normalized_text, kw) for kw in _COVER_LETTER_KEYWORDS):
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=FieldCategory.CUSTOM_COVER_LETTER.value, action=ACTION_MANUAL_REVIEW,
            reason="Cover letter requires a custom response - left for manual review.",
        )
    if context.is_textarea or any(_matches(context.normalized_text, kw) for kw in _SHORT_ANSWER_KEYWORDS):
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=FieldCategory.CUSTOM_SHORT_ANSWER.value, action=ACTION_MANUAL_REVIEW,
            reason="Free-text answer requires a custom response - left for manual review.",
        )

    # 8. Checkboxes / radios are conservative: manual review (non-sensitive).
    if context.is_checkbox or context.is_radio:
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=classification.category, action=ACTION_MANUAL_REVIEW,
            reason="Checkbox / radio choice left for manual review.",
            confidence=classification.confidence, evidence=classification.evidence,
        )

    # 9. Unknown category -> manual review.
    if classification.category == FieldCategory.UNKNOWN.value:
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=FieldCategory.UNKNOWN.value, action=ACTION_MANUAL_REVIEW,
            reason="No confident category for this field - left for manual review.",
        )

    # 10. Resolve the profile value.
    resolution = resolve_profile_value(profile, classification.category)
    if not resolution.value_exists:
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=classification.category, profile_path=resolution.profile_path,
            action=ACTION_MANUAL_REVIEW,
            reason=resolution.missing_reason or "Profile has no value for this field.",
            missing_value=True, confidence=classification.confidence,
            evidence=classification.evidence,
        )

    # 11. Select fields: only fill on an exact normalized option match.
    if context.is_select:
        raw_value = resolve_raw_value(profile, resolution.profile_path)
        normalized_options = {normalize_field_text(o) for o in context.options}
        exact = raw_value is not None and normalize_field_text(raw_value) in normalized_options
        if exact and classification.confidence >= FILL_THRESHOLD:
            action, reason = ACTION_FILL, "Exact option match - will select."
        elif classification.confidence >= SUGGEST_THRESHOLD:
            action, reason = ACTION_SUGGEST, "No exact option match - suggested for manual selection."
        else:
            action, reason = ACTION_MANUAL_REVIEW, "Low-confidence select - left for manual review."
        return FieldMapping(
            field_id=context.field_id, selector=context.selector,
            category=classification.category, profile_path=resolution.profile_path,
            value_preview=resolution.value_preview, confidence=classification.confidence,
            action=action, reason=reason, evidence=classification.evidence,
            warnings=_ambiguity_warnings(classification),
        )

    # 12. Text inputs: action from evidence-based confidence.
    action, reason = _decide_text_action(classification.confidence)
    return FieldMapping(
        field_id=context.field_id, selector=context.selector,
        category=classification.category, profile_path=resolution.profile_path,
        value_preview=resolution.value_preview, confidence=classification.confidence,
        action=action, reason=reason, evidence=classification.evidence,
        warnings=_ambiguity_warnings(classification),
    )


def _ambiguity_warnings(classification: FieldClassification) -> list[str]:
    if classification.ambiguous and classification.ambiguity_reason:
        return [classification.ambiguity_reason]
    return []


def build_fill_plan(
    form_name: str,
    form_url: str,
    fields: list[FormField],
    profile: CandidateProfile,
    *,
    use_overrides: bool = True,
) -> FillPlan:
    """Map every field and summarize the plan with action counts + warnings."""

    overrides_by_fp: dict[str, MappingOverride] = {}
    if use_overrides:
        try:
            for ov in field_mapping_overrides.load_overrides(form_name):
                overrides_by_fp[ov.field_fingerprint] = ov
        except Exception:  # noqa: BLE001 - corrupt/missing override store is non-fatal
            overrides_by_fp = {}

    mappings: list[FieldMapping] = []
    for field in fields:
        context = build_field_context(field)
        fingerprint = field_mapping_overrides.fingerprint_for_context(context)
        override = overrides_by_fp.get(fingerprint) if overrides_by_fp else None
        mapping = map_field_to_profile(field, profile, override=override)
        # Expose the fingerprint so the UI can save an override for this field.
        mapping.field_fingerprint = fingerprint
        mappings.append(mapping)

    counts: dict[str, int] = {
        ACTION_FILL: 0,
        ACTION_SUGGEST: 0,
        ACTION_MANUAL_REVIEW: 0,
        ACTION_SKIP: 0,
    }
    warnings: list[str] = []
    for mapping in mappings:
        counts[mapping.action] = counts.get(mapping.action, 0) + 1
        for warning in mapping.warnings:
            if warning not in warnings:
                warnings.append(warning)

    return FillPlan(
        form_name=form_name,
        form_url=form_url,
        generated_at=datetime.now(timezone.utc),
        mappings=mappings,
        warnings=warnings,
        fill_count=counts[ACTION_FILL],
        suggest_count=counts[ACTION_SUGGEST],
        manual_review_count=counts[ACTION_MANUAL_REVIEW],
        skip_count=counts[ACTION_SKIP],
    )
