import type { CaseProgressEvent } from "./types";

export const API_PREFIX = "/api/v1";
export const TOKEN_KEY = "wathiq.token";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly code: string;

  constructor(status: number, detail: string, code: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage blocked — the session simply will not persist */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

/** Absolute-ish URL for direct browser navigation (iframe previews, CSV export). */
export function apiUrl(path: string): string {
  return `${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Adds the session token to an already-built URL.
 *
 * An `<iframe src>`, an `EventSource` and a download link cannot send an Authorization header.
 * The backend accepts `?token=` on exactly three GET endpoints for this reason (document preview,
 * audit export, case event stream). Never use this for anything that writes.
 */
export function withToken(url: string): string {
  const token = getToken();
  if (!token) return url;
  return `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`;
}

function redirectToLogin() {
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = res.statusText || "Request failed";
  let code = `HTTP_${res.status}`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object") {
      const rec = body as Record<string, unknown>;
      if (typeof rec.detail === "string") detail = rec.detail;
      if (typeof rec.code === "string") code = rec.code;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, detail, code);
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const res = await fetch(apiUrl(path), { ...init, headers });

  if (res.status === 401) {
    clearToken();
    redirectToLogin();
    throw new ApiError(401, "Your session has expired. Please sign in again.", "UNAUTHORIZED");
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export function buildQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      for (const v of value) if (v !== undefined && v !== null && v !== "") sp.append(key, String(v));
    } else {
      sp.append(key, String(value));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export interface CaseEventHandlers {
  onProgress?: (event: CaseProgressEvent) => void;
  onDone?: () => void;
  onError?: (error: Event) => void;
}

/**
 * SSE subscription for the live pipeline stepper. EventSource cannot carry an
 * Authorization header, so the token rides as a query parameter; the backend
 * accepts either. Returns an unsubscribe function.
 */
export function subscribeToCaseEvents(caseId: string, handlers: CaseEventHandlers): () => void {
  const token = getToken();
  const url = apiUrl(`/cases/${caseId}/events${token ? `?token=${encodeURIComponent(token)}` : ""}`);

  let source: EventSource;
  try {
    source = new EventSource(url);
  } catch {
    handlers.onDone?.();
    return () => {};
  }

  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    source.close();
  };

  source.addEventListener("progress", (event) => {
    try {
      handlers.onProgress?.(JSON.parse((event as MessageEvent<string>).data) as CaseProgressEvent);
    } catch {
      /* ignore malformed frame */
    }
  });

  source.addEventListener("done", () => {
    handlers.onDone?.();
    close();
  });

  source.onerror = (event) => {
    // A closed stream reaches us as an error too; treat that as a clean finish.
    if (source.readyState === EventSource.CLOSED) {
      handlers.onDone?.();
    } else {
      handlers.onError?.(event);
    }
    close();
  };

  return close;
}
