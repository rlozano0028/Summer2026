# Phase 1 - Candidate Profile Schema

## Purpose

Phase 1 defines a single, structured representation of a job candidate that
every later phase (resume parsing, autofill, optional AI extraction) reads from
and writes to. Centralizing the shape of candidate data keeps the project
consistent and makes the privacy/review rules enforceable in one place.

The models live in [`backend/app/models/candidate_profile.py`](../backend/app/models/candidate_profile.py)
and are implemented with Pydantic v2.

## Top-level structure

`CandidateProfile` is composed of:

- `identity` - name and contact details
- `links` - LinkedIn, GitHub, portfolio, other links
- `education` - list of `EducationItem`
- `experience` - list of `ExperienceItem`
- `projects` - list of `ProjectItem`
- `skills` - grouped skill lists
- `work_authorization` - sensitive legal fields
- `preferences` - location/remote/start-date/salary preferences
- `metadata` - bookkeeping (source file, timestamps, review flags)

## How unknown fields are represented

Unknown is deliberately distinct from a negative answer:

- Scalar fields (strings, numbers, booleans) default to `None` when unknown.
- Collection fields (lists) default to an empty list `[]`, meaning "nothing
  detected", not "this person has none".

This distinction matters for autofill: a field that is `None` should prompt the
user, whereas a field that is `False` is a deliberate answer.

## Why sensitive fields default to `None`

`WorkAuthorization.authorized_to_work_us`, `WorkAuthorization.requires_sponsorship`,
and `Preferences.salary_expectation` all default to `None`. The assistant must
never assume or auto-answer legally sensitive questions. Leaving them `None`
forces an explicit, user-confirmed value before they could ever be used to fill
an application.

## Example JSON profile

```json
{
  "identity": {
    "first_name": "Jane",
    "last_name": "Doe",
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "(555) 123-4567",
    "city": null,
    "state": null,
    "country": null
  },
  "links": {
    "linkedin": "https://linkedin.com/in/janedoe",
    "github": "https://github.com/janedoe",
    "portfolio": null,
    "other_links": []
  },
  "education": [],
  "experience": [],
  "projects": [],
  "skills": {
    "programming_languages": ["Python", "TypeScript"],
    "frameworks": ["FastAPI", "React"],
    "tools": ["Docker"],
    "databases": ["PostgreSQL"],
    "cloud": [],
    "other": []
  },
  "work_authorization": {
    "authorized_to_work_us": null,
    "requires_sponsorship": null,
    "notes": null
  },
  "preferences": {
    "preferred_locations": [],
    "remote_preference": null,
    "start_date": null,
    "salary_expectation": null
  },
  "metadata": {
    "source_file_name": "resume.txt",
    "source_file_type": "txt",
    "extracted_at": "2026-06-01T18:00:00Z",
    "parser_version": "0.1.0",
    "needs_review": true,
    "review_notes": [
      "Name 'Jane Doe' was guessed from the top of the resume; please verify."
    ]
  }
}
```

## What should require manual review later

The following must always be confirmed by the user before being used to fill an
application, and should never be auto-submitted:

- Work authorization and sponsorship status
- Salary expectations
- Demographic / EEO questions (race, gender, etc.)
- Veteran status
- Disability status
- Criminal-history questions
- Any legal acknowledgments or certifications

In addition, anything the deterministic parser only guessed (for example the
candidate name) is added to `metadata.review_notes` and the profile is flagged
with `metadata.needs_review = true`.
