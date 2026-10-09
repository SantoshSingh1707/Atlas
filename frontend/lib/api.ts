import type { CapabilityResult, RunEvent, RunSummary } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let detail = "";
    try {
      detail = await response.text();
    } catch {
      detail = "";
    }
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }
  return (await response.json()) as T;
}

export function startRun(
  capability: string,
  question: string,
): Promise<{ run_id: string }> {
  return request<{ run_id: string }>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ capability, question }),
  });
}

export function getResult(runId: string): Promise<CapabilityResult> {
  return request<CapabilityResult>(`/api/runs/${runId}`);
}

export function listRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/api/runs");
}

export interface StreamHandlers {
  onEvent?: (event: RunEvent) => void;
  onResult?: (result: CapabilityResult) => void;
  onError?: (error: unknown) => void;
}

export type EventSourceFactory = (url: string) => EventSource;

const STEPS = ["plan", "search", "read", "write", "done", "error"] as const;

export function streamRun(
  runId: string,
  handlers: StreamHandlers = {},
  eventSourceFactory?: EventSourceFactory,
): EventSource {
  const factory = eventSourceFactory ?? ((url: string) => new EventSource(url));
  const source = factory(`${API_BASE}/api/runs/${runId}/stream`);

  for (const step of STEPS) {
    source.addEventListener(step, (event) => {
      const data = (event as MessageEvent).data;
      // Native transport errors also fire on the "error" listener; skip non-message events.
      if (typeof data !== "string") return;
      try {
        handlers.onEvent?.(JSON.parse(data) as RunEvent);
      } catch (error) {
        handlers.onError?.(error);
      }
    });
  }

  source.addEventListener("result", (event) => {
    const data = (event as MessageEvent).data;
    try {
      handlers.onResult?.(JSON.parse(data) as CapabilityResult);
    } catch (error) {
      handlers.onError?.(error);
    } finally {
      // Terminal: close so the browser does not auto-reconnect to a finished run.
      source.close();
    }
  });

  source.onerror = (error) => {
    handlers.onError?.(error);
    source.close();
  };
  return source;
}
