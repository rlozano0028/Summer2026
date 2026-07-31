/**
 * The confirmation gate for real application pages (Phase 7).
 *
 * Two jobs, and the order is deliberate: state plainly what the extension will and
 * will not do, then ask for consent. The checkbox is unchecked every time the popup
 * opens - consent is not remembered, because "I agreed once" is not the same as "I
 * want this to happen on this page".
 *
 * The backend enforces the same requirement independently, so unchecking this is not
 * merely a UI courtesy: without it, the analysis request is refused with a 400.
 */

export interface RealPageWarningProps {
  platformLabel: string;
  /** Extra notes from the backend's safety decision, shown verbatim. */
  warnings: string[];
  confirmed: boolean;
  onConfirmedChange: (confirmed: boolean) => void;
  disabled?: boolean;
}

export function RealPageWarning({
  platformLabel,
  warnings,
  confirmed,
  onConfirmedChange,
  disabled = false,
}: RealPageWarningProps) {
  return (
    <section>
      <h2>Real application page</h2>
      <div className="notice warn">
        <p className="notice-lead">
          You are on a real <strong>{platformLabel}</strong> application page. Before
          anything happens here:
        </p>
        <ul>
          <li>Only plain contact and profile fields are filled.</li>
          <li>
            Sensitive, legal, demographic, salary, and sponsorship questions are never
            filled - you answer those.
          </li>
          <li>No file is attached, no password is read, no button is clicked.</li>
          <li>
            Nothing is submitted. You review the whole form and submit it yourself.
          </li>
        </ul>
        {warnings.length > 0 && (
          <ul className="platform-notes">
            {warnings.map((warning, index) => (
              <li key={`${index}-${warning}`}>{warning}</li>
            ))}
          </ul>
        )}
      </div>
      <label className="confirm">
        <input
          type="checkbox"
          checked={confirmed}
          disabled={disabled}
          onChange={(event) => onConfirmedChange(event.target.checked)}
        />
        <span>
          I opened this page myself and I want the extension to analyze it. I will
          review every field before submitting.
        </span>
      </label>
    </section>
  );
}
