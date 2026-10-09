import { describe, expect, it, vi } from "vitest";

import { streamRun } from "@/lib/api";
import type { CapabilityResult } from "@/lib/types";

class FakeEventSource {
  listeners: Record<string, ((event: { data: string }) => void)[]> = {};
  closed = false;
  onerror: ((error: unknown) => void) | null = null;
  constructor(public url: string) {}
  addEventListener(type: string, cb: (event: { data: string }) => void) {
    (this.listeners[type] ||= []).push(cb);
  }
  close() {
    this.closed = true;
  }
  emit(type: string, payload: unknown) {
    for (const cb of this.listeners[type] ?? []) {
      cb({ data: JSON.stringify(payload) });
    }
  }
}

describe("streamRun", () => {
  it("delivers events and result, then closes the source on result", () => {
    const source = new FakeEventSource("http://x");
    const onEvent = vi.fn();
    const onResult = vi.fn();
    const result: CapabilityResult = {
      run_id: "r1",
      capability_id: "research",
      status: "finished",
      report_markdown: "",
      citations: [],
      sources: [],
      tokens: 0,
      cost: 0,
      duration_ms: 0,
    };

    streamRun("r1", { onEvent, onResult }, () => source as unknown as EventSource);
    source.emit("plan", { run_id: "r1", step: "plan", status: "started" });
    source.emit("result", result);

    expect(onEvent).toHaveBeenCalledWith({ run_id: "r1", step: "plan", status: "started" });
    expect(onResult).toHaveBeenCalledWith(result);
    expect(source.closed).toBe(true);
  });
});
