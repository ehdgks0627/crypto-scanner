import { describe, expect, it, vi, afterEach } from "vitest";

import { isDynamicImportError, loadRouteModule } from "./lazyRoute";

function TestPage() {
  return null;
}

describe("lazy route loading", () => {
  afterEach(() => {
    window.sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("maps a named page export to a lazy default export", async () => {
    await expect(loadRouteModule(async () => ({ TestPage }), "TestPage")).resolves.toEqual({ default: TestPage });
  });

  it("detects dynamic import chunk loading errors", () => {
    expect(isDynamicImportError(new TypeError("Failed to fetch dynamically imported module: /assets/SnapshotDetailPage.js"))).toBe(true);
    expect(isDynamicImportError(new Error("Loading chunk 12 failed."))).toBe(true);
    expect(isDynamicImportError(new Error("Request failed with status code 500"))).toBe(false);
  });

  it("reloads once for a dynamic import failure and then lets repeat failures surface", async () => {
    const reloadPage = vi.fn();
    const chunkError = new TypeError("Failed to fetch dynamically imported module: /assets/SnapshotDetailPage.js");

    void loadRouteModule(async () => {
      throw chunkError;
    }, "TestPage", reloadPage);

    await vi.waitFor(() => expect(reloadPage).toHaveBeenCalledOnce());

    await expect(
      loadRouteModule(async () => {
        throw chunkError;
      }, "TestPage", reloadPage)
    ).rejects.toBe(chunkError);
    expect(reloadPage).toHaveBeenCalledOnce();
  });
});
