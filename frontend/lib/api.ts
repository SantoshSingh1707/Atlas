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
      try {
        handlers.onEvent?.(JSON.parse((event as MessageEvent).data) as RunEvent);
      } catch (error) {
        handlers.onError?.(error);
      }
    });
  }

  source.addEventListener("result", (event) => {
    try {
      handlers.onResult?.(JSON.parse((event as MessageEvent).data) as CapabilityResult);
    } catch (error) {
      handlers.onError?.(error);
    }
  });

  source.onerror = (error) => handlers.onError?.(error);
  return source;
}
