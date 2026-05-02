import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import { renderWithApp } from "../../test/test-utils";
import { SettingsView } from "./SettingsView";

const defaultWeights = {
  wA: 1,
  wD: 1,
  wE: 1,
  wL: 1,
  wC: 1,
  updated_at: "2026-04-29T00:00:00Z"
};

describe("SettingsView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the algorithm risk table as a table", async () => {
    vi.spyOn(services.risk, "weights").mockResolvedValue(defaultWeights);
    vi.spyOn(services.meta, "algorithmRiskTable").mockResolvedValue({
      items: [
        { algorithm: "RSA-2048", factor_a: 1.5, quantum_vulnerable: true, notes: null },
        { algorithm: "Ed25519", factor_a: 0.75, quantum_vulnerable: false, notes: "" },
        { algorithm: "ML-KEM-768", factor_a: 0.25, quantum_vulnerable: false, notes: "Post-quantum ready" }
      ]
    });

    renderWithApp(<SettingsView />);

    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("columnheader").map((header) => header.textContent)).toEqual([
      "알고리즘",
      "A 계수",
      "양자 취약 여부",
      "비고"
    ]);
    expect(screen.getByText("RSA-2048")).toBeInTheDocument();
    expect(screen.getByText("1.5")).toBeInTheDocument();
    expect(screen.getByText("0.75")).toBeInTheDocument();
    expect(screen.getByText("Post-quantum ready")).toBeInTheDocument();
    expect(screen.getByText("예")).toBeInTheDocument();
    expect(screen.getAllByText("아니오")).toHaveLength(2);
    expect(screen.getAllByText("-")).toHaveLength(2);
    expect(screen.queryByText(/"items"/)).not.toBeInTheDocument();
  });

  it("falls back to an empty table state when no rules are returned", async () => {
    vi.spyOn(services.risk, "weights").mockResolvedValue(defaultWeights);
    vi.spyOn(services.meta, "algorithmRiskTable").mockResolvedValue({} as Awaited<ReturnType<typeof services.meta.algorithmRiskTable>>);

    renderWithApp(<SettingsView />);

    expect(await screen.findByText("설정된 규칙이 없습니다")).toBeInTheDocument();
  });
});
