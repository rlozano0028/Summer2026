import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, getHealth } from "../api/client";

export type ConnectionState = "checking" | "online" | "offline";

// Checks GET /health on mount; `recheck` runs it again.
export function useBackendHealth(): [ConnectionState, () => void] {
  const [state, setState] = useState<ConnectionState>("checking");

  const recheck = useCallback(async () => {
    setState("checking");
    try {
      const health = await getHealth();
      setState(health.status === "ok" ? "online" : "offline");
    } catch {
      setState("offline");
    }
  }, []);

  useEffect(() => {
    void recheck();
  }, [recheck]);

  return [state, () => void recheck()];
}

// Only shown when the backend is unreachable, with the command that fixes it.
export function OfflineBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="notice notice-error banner" role="alert">
      <div>
        <strong>The local backend is not running.</strong> Nothing can be parsed,
        saved, or analyzed until it is. From the <code>backend</code> folder, run{" "}
        <code>uvicorn app.main:app --reload</code> (expected at{" "}
        <code>{API_BASE_URL}</code>).
      </div>
      <button type="button" className="secondary" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
