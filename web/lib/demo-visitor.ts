// Per-visitor id for the public demo.
//
// DeepTutor is single-user by design, so in DEMO the backend serves one
// shared in-memory session store to every anonymous visitor. To keep each
// visitor's chat history private, the browser mints a random id once, persists
// it in localStorage, and sends it on every request (the `X-Demo-Visitor`
// header via `apiFetch`, and the `visitor` query param on the chat WebSocket).
// The backend keys its ephemeral store by this id.
//
// This is isolation, not authentication: the id is opaque and only partitions
// the demo's ephemeral store. An incognito window has its own localStorage, so
// it naturally gets a distinct id (and distinct history). Non-demo backends
// ignore the id entirely, so sending it unconditionally is harmless.

const STORAGE_KEY = "deeptutor-demo-visitor-id";

/**
 * Return this browser's demo visitor id, creating and persisting one on first
 * use. Returns "" during SSR or when storage is unavailable (private-mode
 * quotas, disabled storage) — the backend then falls back to a shared bucket,
 * which is no worse than the pre-isolation behaviour.
 */
export function getDemoVisitorId(): string {
  if (typeof window === "undefined") return "";
  try {
    let id = window.localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `v-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
      window.localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    return "";
  }
}
