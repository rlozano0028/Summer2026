# Sample Resumes

Drop local test resumes here (`.pdf`, `.docx`, `.txt`) to try the extraction and
parsing endpoints.

## Privacy

- Do **not** commit real personal resumes to the repository.
- This folder is intended for local, throwaway test files.
- The backend never stores uploaded resumes permanently; files sent to the API
  are processed in a temporary location and deleted immediately afterward.

## Suggested `.gitignore`

To keep real resumes out of version control while still tracking this README,
add the following to your `.gitignore`:

```gitignore
sample-resumes/*
!sample-resumes/README.md
```

## Quick test

You can create a tiny text resume and parse it:

```bash
# from the backend directory, with the API running
curl.exe -X POST http://127.0.0.1:8000/resume/parse -F "file=@..\sample-resumes\example.txt"
```
