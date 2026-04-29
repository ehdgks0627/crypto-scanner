import { describe, expect, it } from "vitest";

import { canCancelJob, isActiveJobStatus, pageHasActiveJob } from "./jobStatus";

describe("jobStatus helpers", () => {
  it("detects active job statuses", () => {
    expect(isActiveJobStatus("PENDING")).toBe(true);
    expect(isActiveJobStatus("RUNNING")).toBe(true);
    expect(isActiveJobStatus("COMPLETED")).toBe(false);
    expect(pageHasActiveJob([{ status: "COMPLETED" }, { status: "RUNNING" }])).toBe(true);
  });

  it("matches backend cancellation policy", () => {
    expect(canCancelJob({ kind: "recompute", status: "PENDING", cancel_requested_at: null })).toBe(true);
    expect(canCancelJob({ kind: "recompute", status: "RUNNING", cancel_requested_at: null })).toBe(false);
    expect(canCancelJob({ kind: "scan_job", status: "RUNNING", cancel_requested_at: null })).toBe(true);
    expect(canCancelJob({ kind: "discovery", status: "RUNNING", cancel_requested_at: "2026-04-29T00:00:00Z" })).toBe(false);
  });
});
