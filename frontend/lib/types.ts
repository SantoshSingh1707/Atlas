export type RunStatus = "pending" | "running" | "finished" | "failed";

export type RunStep = "plan" | "search" | "read" | "write" | "done" | "error";

export interface RunEvent {
  run_id: string;
  step: RunStep;
  status: string;
  detail?: string | null;
  token?: string | null;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet?: string;
  provider?: string;
}

export interface Citation {
  index: number;
  title: string;
  url: string;
  snippet?: string;
}

export interface CapabilityResult {
  run_id: string;
  capability_id: string;
  status: RunStatus;
  report_markdown: string;
  citations: Citation[];
  sources: SearchResult[];
  tokens: number;
  cost: number;
  duration_ms: number;
  error?: string | null;
}

export interface RunSummary {
  id: string;
  capability_id: string;
  question: string;
  status: RunStatus;
  created_at: string;
  tokens?: number;
  cost?: number;
  duration_ms?: number;
}
