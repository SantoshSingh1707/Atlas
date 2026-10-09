import { describe, expect, it, vi } from "vitest";

import { getResult, startRun } from "@/lib/api";

describe("api client", () => {
  it("posts capability + question and returns run_id", async () => {
    const f = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ run_id: "r1" }) });
    vi.stubGlobal("fetch", f);

    const out = await startRun("research", "hello");

    expect(out.run_id).toBe("r1");
    const [url, init] = f.mock.calls[0];
    expect(url).toContain("/api/runs");
    expect(JSON.parse(init.body)).toEqual({ capability: "research", question: "hello" });
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, text: async () => "boom" }),
    );
    await expect(getResult("r1")).rejects.toThrow();
  });
});
