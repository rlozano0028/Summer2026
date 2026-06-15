"""CLI demo for the local autofill prototype (Phase 4).

Examples (run from the ``backend`` directory with the venv activated)::

    python -m app.scripts.run_local_autofill_demo --form basic --dry-run
    python -m app.scripts.run_local_autofill_demo --form basic --headful
    python -m app.scripts.run_local_autofill_demo --form engineering --headful
    python -m app.scripts.run_local_autofill_demo --form engineering --headful \
        --resume-file "path/to/resume.pdf"

The demo only ever opens the approved local sample forms. It never submits and
never targets real job sites.
"""

from __future__ import annotations

import argparse
import sys

from app.models.automation import AutomationRequest
from app.services import profile_storage, sample_forms
from app.services.playwright_autofill import (
    PlaywrightSetupError,
    run_local_autofill,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_local_autofill_demo",
        description="Autofill a local sample job-application form from your saved profile.",
    )
    parser.add_argument(
        "--form",
        required=True,
        choices=sample_forms.list_sample_forms(),
        help="Which approved local sample form to use.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and plan only; do not type anything into the form.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Show the browser window (default is headless).",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep the browser open after filling for manual inspection (headful only).",
    )
    parser.add_argument(
        "--resume-file",
        default=None,
        help="Optional local resume file to attach to a clear resume upload field.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # 1. Load the saved (reviewed) profile from Phase 3.
    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        print(f"Could not read saved profile: {exc}", file=sys.stderr)
        return 1
    if profile is None:
        print(
            "No saved profile found.\n"
            "Upload a resume and review/save a profile first (use the local "
            "dashboard or the /resume and /profile API), then re-run this demo.",
            file=sys.stderr,
        )
        return 1

    # 2. Resolve the form name to an approved local file.
    try:
        form_path = sample_forms.resolve_sample_form(args.form)
    except (sample_forms.UnknownSampleFormError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    request = AutomationRequest(
        form_name=args.form,
        headless=not args.headful,
        dry_run=args.dry_run,
        resume_file_path=args.resume_file,
        keep_browser_open=args.keep_open,
    )

    # 3. Run autofill (or dry run).
    try:
        result = run_local_autofill(form_path, profile, request)
    except PlaywrightSetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # 4. Print a concise summary.
    print("\n=== Autofill demo summary ===")
    print(f"Form used:        {result.form_name}")
    print(f"Mode:             {'dry run' if args.dry_run else 'fill'}")
    print(f"Filled:           {len(result.filled_fields)}")
    print(f"Suggested:        {len(result.suggested_fields)}")
    print(f"Manual review:    {len(result.manual_review_fields)}")
    print(f"Skipped:          {len(result.skipped_fields)}")
    if result.warnings:
        print(f"Warnings:         {len(result.warnings)}")
        for warning in result.warnings:
            print(f"  - {warning}")
    print(f"Report (redacted): {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
