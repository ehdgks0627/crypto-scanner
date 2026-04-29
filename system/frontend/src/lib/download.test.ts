import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadText } from "./download";

describe("downloadText", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("creates a temporary object URL and revokes it after click", () => {
    vi.useFakeTimers();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: () => "blob:test-url" });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: () => undefined });
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test-url");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadText("report.md", "# report", "text/markdown;charset=utf-8");

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(revokeObjectURL).not.toHaveBeenCalled();

    vi.runOnlyPendingTimers();

    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test-url");
  });
});
