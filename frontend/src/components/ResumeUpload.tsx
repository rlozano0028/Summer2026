import { useState } from "react";
import { parseResumeAndSave } from "../api/client";
import type { ResumeParseResult } from "../types/resume";

interface ResumeUploadProps {
  // Called after a successful parse so the parent can load the parsed profile
  // into the editor.
  onParsed: (result: ResumeParseResult) => void;
}

const ACCEPTED = ".pdf,.docx,.txt";

// Lets the user pick a resume and parse+save it via the backend.
export function ResumeUpload({ onParsed }: ResumeUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ResumeParseResult | null>(null);

  async function handleUpload() {
    if (!file) {
      setError("Please choose a resume file first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const parsed = await parseResumeAndSave(file);
      setResult(parsed);
      onParsed(parsed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      <header className="card-header">
        <span className="step">1</span>
        <div>
          <h2>Upload resume</h2>
          <p className="muted">
            PDF, DOCX, or TXT. The file is parsed on this computer and not kept; only
            the resulting profile is saved.
          </p>
        </div>
      </header>

      <div className="row">
        <input
          aria-label="Resume file"
          type="file"
          accept={ACCEPTED}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setError(null);
          }}
        />
        <button type="button" onClick={() => void handleUpload()} disabled={loading || !file}>
          {loading ? "Parsing…" : "Parse & save"}
        </button>
      </div>

      {error && <p className="notice notice-error">{error}</p>}

      {result && (
        <div className="parse-result">
          <p className="notice notice-warn">
            This is a first draft. Check every field in step 2 before you use it.
          </p>
          <p className="muted">
            Detected from <strong>{result.source_file_name}</strong> · confidence{" "}
            {(result.confidence * 100).toFixed(0)}%
          </p>

          {result.warnings.length > 0 && (
            <div>
              <h4>Warnings</h4>
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {result.missing_fields.length > 0 && (
            <div>
              <h4>Not found in the resume</h4>
              <ul className="chips">
                {result.missing_fields.map((m, i) => (
                  <li key={i} className="chip">
                    {m}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details>
            <summary>Extracted resume text preview</summary>
            <pre className="preview">{result.raw_text.slice(0, 2000) || "(no text)"}</pre>
          </details>
        </div>
      )}
    </section>
  );
}
