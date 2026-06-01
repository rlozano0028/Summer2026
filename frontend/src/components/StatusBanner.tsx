import { useEffect, useState } from "react";
import { API_BASE_URL, getHealth } from "../api/client";

type ConnectionState = "checking" | "online" | "offline";

// Checks GET /health on mount and shows whether the backend is reachable.
export function StatusBanner() {
  const [state, setState] = useState<ConnectionState>("checking");

  async function check() {
    setState("checking");
    try {
      const health = await getHealth();
      setState(health.status === "ok" ? "online" : "offline");
    } catch {
      setState("offline");
    }
  }

  useEffect(() => {
    void check();
  }, []);

  return (
    <div className={`status-banner status-${state}`}>
      {state === "checking" && <span>Checking backend connection…</span>}
      {state === "online" && (
        <span>Backend connected at {API_BASE_URL}</span>
      )}
      {state === "offline" && (
        <span>
          Backend is not reachable. Start it with:{" "}
          <code>uvicorn app.main:app --reload</code> (from the <code>backend</code>{" "}
          folder).
        </span>
      )}
      <button type="button" className="link-button" onClick={() => void check()}>
        Retry
      </button>
    </div>
  );
}
