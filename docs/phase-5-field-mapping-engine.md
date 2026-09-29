# Phase 5 - Robust Field-Mapping Engine

Phase 5 turns the Phase 4 prototype field detection/mapping into a more reliable,
explainable, and testable field-mapping engine. It hardens and modularizes the
matching layer without changing the safety guarantees: automation still only
targets local sample forms, never submits, and never autofills sensitive/legal
fields.

## What Phase 5 adds

- A dedicated **field context builder** that enriches and normalizes each
  detected field.
- An evidence-based **classifier** that maps fields to known categories with a
  confidence score and explainable evidence.
- A standalone **sensitive-field detector** that aggressively flags
  legal/demographic/compensation fields.
- A **profile value resolver** that safely resolves values and produces redacted
  previews.
- A **redaction service** used everywhere previews are shown or stored.
- Local, user-controlled **mapping overrides** (stored as JSON) for reuse.
- A richer **frontend review experience** (grouped decisions + override editor).
- Three new **sample forms** covering edge cases, sensitive fields, and
  select/radio/checkbox controls.

## Pipeline

```
FormField (detector)
  -> FieldContext (field_context_builder)
  -> classify_field() + detect_sensitive() + override lookup
  -> resolve_profile_value() (redacted preview)
  -> FieldMapping (action: fill | suggest | manual_review | skip)
  -> FillPlan
```

Field mapping logic is isolated from Playwright. Playwright only consumes the
resulting `FillPlan`.

## Field context building

`app/services/field_context_builder.py` converts a raw `FormField` into a
`FieldContext`:

- `build_field_context(field)`
- `field_text` - a human-readable join of label, placeholder, aria-label, name,
  id, autocomplete, nearby text, and options.
- `normalized_text` - the lowercased, punctuation-normalized version used for
  matching.

No private profile values are stored in a `FieldContext`.

## Normalization

`normalize_field_text(text)`:

- splits `camelCase` / `PascalCase` boundaries (`firstName` -> `first name`),
- replaces underscores, hyphens, and other punctuation with spaces
  (`first_name`, `given-name` -> `first name`, `given name`),
- collapses repeated whitespace.

`tokenize_field_text(text)` returns deduplicated, order-preserving tokens.

## Field classification

`app/services/field_mapper.py` `classify_field(context)`:

- Each `ClassRule` votes for a `FieldCategory` with a *specificity* weight.
- Each evidence source has a reliability multiplier (label/aria/autocomplete are
  strongest; nearby text and option text are weakest).
- Multi-word keywords match as substrings; single words match whole tokens (so
  `age` does not match inside `manage`).
- Standardized HTML `autocomplete` tokens (`given-name`, `email`, `tel`, ...) are
  high-trust signals.

## Confidence scoring

Confidence is evidence-based, not static:

- Per-source evidence weight = `specificity * source_multiplier`.
- Category score combines evidence with a probabilistic OR
  (`1 - prod(1 - weight)`), clamped to `<= 0.99`.
- Multiple corroborating signals raise confidence; conflicting top categories
  set `ambiguous = true` and reduce confidence.

Thresholds:

- `confidence >= 0.90` and safe and value exists -> `fill`
- `0.60 <= confidence < 0.90` and value exists -> `suggest`
- `confidence < 0.60` -> `manual_review`

## Evidence

Each decision carries a list of `MatchEvidence` (`source`, `matched_text`,
`matched_rule`, `weight`). The frontend shows these in an expandable list so
every fill/suggest/skip is explainable.

## Profile value resolution

`app/services/field_value_resolver.py`:

- `resolve_profile_value(profile, category)` -> `ProfileValueResolution`
  (whether a value exists, the profile path, and a **redacted** preview).
- `resolve_raw_value(profile, profile_path)` -> the full value, used only by the
  runner at fill time and never stored.
- Identity, links, and skills resolve at fill grade; education/experience resolve
  at suggest grade.
- Sensitive categories and free-text/upload categories never resolve a value.

## Redaction

`app/services/redaction.py`:

- `redact_email("ada@example.com")` -> `a***@example.com`
- `redact_phone("555-123-4567")` -> `***4567`
- `shorten_value(value, max_length=80)` truncates with an ellipsis
- `redact_profile_value(profile_path, value)` chooses the right strategy

All previews in fill plans and automation reports are redacted.

## Sensitive field detection

`app/services/sensitive_field_detector.py` `detect_sensitive(context)` flags:
work authorization, sponsorship/visa, citizenship-for-eligibility, salary/
compensation, race/ethnicity, gender, sexual orientation, disability, veteran
status, criminal history/background check, legal acknowledgments/consent/
certification, EEO/demographic questions, date of birth, and SSN/government ID.

### Why sensitive/legal fields cannot be autofilled

These answers are legally meaningful, frequently change, and must reflect the
candidate's deliberate choice. Phase 5 never fills them - they are always
`manual_review`, even if the profile contains a related value and even if a user
override tries to force a fill (such overrides are downgraded with a warning).

## Local mapping overrides

`app/services/field_mapping_overrides.py` stores overrides as JSON under
`backend/app/data/mapping-overrides/` (git-ignored; `.gitkeep` retained).

- Matched by `form_name` + a stable `field_fingerprint`.
- The fingerprint is derived only from non-private metadata (label, name, id,
  placeholder, input type, tag name). **No profile values are stored.**
- API: `GET /mapping-overrides`, `POST /mapping-overrides`,
  `DELETE /mapping-overrides/{override_id}`,
  `POST /mapping-overrides/apply-to-plan`.
- Overrides are local-only and user-controlled. Sensitive force-fills are always
  downgraded to manual review.

## What data is and is not stored

- Stored locally: the reviewed `profile.json`, redacted automation reports, and
  mapping overrides (metadata + chosen category/action only).
- Never stored: full resume text, full field values, or any private value in a
  plan/report. No cloud storage, no analytics, no third-party calls.

## How to run the tests

From `backend/` with the virtual environment active:

```bash
pytest
```

Playwright-dependent tests skip cleanly if Chromium is not installed
(`python -m playwright install chromium`).

## How to run the local sample-form demos

```bash
python -m app.scripts.run_local_autofill_demo --form basic --dry-run
python -m app.scripts.run_local_autofill_demo --form sensitive-fields --dry-run
python -m app.scripts.run_local_autofill_demo --form select-radio-checkboxes --headful
```

Or via the API (browser stays short-lived, never submits):

```bash
curl -X POST http://127.0.0.1:8000/automation/analyze -H "Content-Type: application/json" -d '{"form_name":"edge-case-labels"}'
```

## How to use the frontend mapping review panel

1. Start the backend and frontend, save a reviewed profile.
2. In the automation panel, pick a sample form and click **Analyze form**.
3. Review decisions grouped into Will fill / Suggestions / Needs manual review /
   Skipped. Expand any field to see its evidence.
4. Use **Add a local mapping override** to pin a field's category/action; the
   plan re-analyzes with the override applied. Sensitive fields cannot be forced
   to fill.

## Known limitations

- Classification is deterministic and keyword/heuristic-based (no AI, no fuzzy
  ML). Unusual labels may fall to `manual_review`.
- Education/experience resolve only from the first entry and stay suggest-grade.
- Checkboxes/radios are always conservative (manual review).
- Selects fill only on an exact normalized option match.
- Index-based selectors assume the DOM is stable between detect and fill (true
  for local sample forms).

## What should come next in Phase 6

- A browser extension (still local-first, still no auto-submit) to apply plans on
  a page the user is actively viewing, with explicit per-field confirmation.
- Smarter multi-entry education/experience handling and richer option matching
  for selects.
- Optional, clearly-gated assisted answers for custom questions (never for
  sensitive/legal fields), with user review required.
