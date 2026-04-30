import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { services } from "../../api/services";
import type { Schema } from "../../api/types";
import { renderWithApp } from "../../test/test-utils";
import { MigrationPlanView } from "./MigrationViews";

const migrationItem = {
  asset_id: 9001,
  asset_name: "cert-leaf-web-rsa2048",
  asset_type: "certificate",
  current: { algorithm: "RSA-2048", key_size_bits: 2048, quantum_vulnerable: true },
  recommendation: {
    strategy: "hybrid",
    target_algorithm: "RSA-2048 + ML-DSA-65",
    target_algorithm_set: ["RSA-2048", "ML-DSA-65"],
    final_algorithm_set: ["ML-DSA-65"],
    phase: "hybrid_first",
    blockers: ["runtime_capability_unknown"],
    rollback: "Keep the existing RSA path enabled.",
    validation: ["rescan_crypto_inventory"],
    rationale: "Use a hybrid transition before converging to PQC.",
    confidence: 0.77
  },
  alternatives: [{ strategy: "replace", target_algorithm: "ML-DSA-65", trade_off: "requires client compatibility review" }],
  risk_score: 95,
  tier: "CRITICAL",
  agility: {
    score: 36,
    level: "LOW",
    blockers: ["runtime_capability_unknown"],
    enablers: ["inventory_fresh"]
  },
  playbook: [
    {
      order: 1,
      kind: "enable_hybrid",
      title: "Enable hybrid transition",
      action: "Deploy RSA-2048 + ML-DSA-65 while retaining the classical fallback.",
      validation: "rescan_crypto_inventory"
    }
  ]
} satisfies Schema<"MigrationPlanItem">;

describe("MigrationPlanView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders crypto agility and playbook data from migration recommendations", async () => {
    const user = userEvent.setup();
    vi.spyOn(services.migration, "plan").mockResolvedValue({ items: [migrationItem], total: 1, offset: 0, limit: 20 });
    vi.spyOn(services.migration, "impact").mockResolvedValue({
      selected_count: 1,
      hosts: ["web.testbed.local"],
      services: ["web.testbed.local:443"],
      cert_reissues: 1,
      config_changes: 1,
      key_regens: 0,
      estimated_downtime_min: 15
    });

    renderWithApp(<MigrationPlanView snapshotId={3} />);

    expect(await screen.findByText("cert-leaf-web-rsa2048")).toBeInTheDocument();
    expect(screen.getByText("hybrid_first")).toBeInTheDocument();
    expect(screen.getByText("36 · LOW")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "cert-leaf-web-rsa2048 선택" }));

    expect(await screen.findByText("Crypto Agility Playbook")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Work item" })).toBeInTheDocument();
    expect(screen.getByText("Certificate reissues")).toBeInTheDocument();
    expect(screen.getByText("15 min")).toBeInTheDocument();
    expect(screen.getByText("web.testbed.local:443")).toBeInTheDocument();
    expect(screen.queryByText("selected_count")).not.toBeInTheDocument();
    expect(screen.getByText("runtime_capability_unknown")).toBeInTheDocument();
    expect(screen.getByText("Enable hybrid transition")).toBeInTheDocument();
    expect(screen.getByText("Keep the existing RSA path enabled.")).toBeInTheDocument();
  });
});
