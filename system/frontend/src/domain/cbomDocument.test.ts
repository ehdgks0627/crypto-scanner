import { describe, expect, it } from "vitest";

import { CbomDocumentModel } from "./cbomDocument";

describe("CbomDocumentModel", () => {
  it("extracts summary, component rows, metadata properties, and dependencies", () => {
    const model = new CbomDocumentModel({
      bomFormat: "CycloneDX",
      specVersion: "1.6",
      serialNumber: "urn:uuid:test",
      version: 1,
      metadata: {
        timestamp: "2026-04-30T00:00:00Z",
        tools: { components: [{ name: "PQC Risk Assessment System" }] },
        properties: [{ name: "internal:snapshot_id", value: "56" }]
      },
      components: [
        {
          type: "crypto-asset",
          "bom-ref": "alg-rsa-2048",
          name: "RSA-2048",
          cryptoProperties: {
            assetType: "algorithm",
            algorithmProperties: {
              parameterSetIdentifier: "rsaEncryption",
              primitive: "signature"
            }
          },
          properties: [
            { name: "internal:family", value: "RSA" },
            { name: "internal:quantum_vulnerable", value: "true" },
            { name: "risk.tier", value: "HIGH" },
            { name: "risk.score", value: "91" }
          ]
        }
      ],
      dependencies: [{ ref: "proto-tls13", dependsOn: ["alg-rsa-2048"] }]
    });

    expect(model.summary()).toMatchObject({
      bomFormat: "CycloneDX",
      specVersion: "1.6",
      serialNumber: "urn:uuid:test",
      version: "1",
      timestamp: "2026-04-30T00:00:00Z",
      toolName: "PQC Risk Assessment System",
      componentCount: 1,
      dependencyCount: 1,
      metadataPropertyCount: 1
    });
    expect(model.metadataProperties()).toEqual([{ name: "internal:snapshot_id", value: "56" }]);
    expect(model.componentRows()[0]).toMatchObject({
      bomRef: "alg-rsa-2048",
      name: "RSA-2048",
      type: "crypto-asset",
      assetType: "algorithm",
      algorithm: "rsaEncryption",
      algorithmFamily: "RSA",
      primitive: "signature",
      quantumVulnerable: "true",
      riskTier: "HIGH",
      riskScore: "91"
    });
    expect(model.dependencyRows()).toEqual([{ ref: "proto-tls13", dependsOn: ["alg-rsa-2048"] }]);
  });

  it("supports the current testbed CBOM shape", () => {
    const model = new CbomDocumentModel({
      metadata: {
        component: { name: "crypto-scanner-testbed" }
      },
      components: [
        {
          "bom-ref": "cert-web",
          name: "web certificate",
          type: "cryptographic-asset",
          cryptoProperties: {
            assetType: "certificate",
            algorithm: "RSA-2048",
            algorithmFamily: "RSA"
          },
          properties: [
            { name: "risk.tier", value: "CRITICAL" },
            { name: "risk.score", value: "98" }
          ]
        }
      ]
    });

    expect(model.summary().toolName).toBe("crypto-scanner-testbed");
    expect(model.componentRows()[0]).toMatchObject({
      assetType: "certificate",
      algorithm: "RSA-2048",
      algorithmFamily: "RSA",
      riskTier: "CRITICAL",
      riskScore: "98"
    });
  });

  it("falls back to empty rows for malformed collections", () => {
    const model = new CbomDocumentModel({
      components: { invalid: true },
      dependencies: "invalid",
      metadata: { properties: [null, { name: "", value: "ignored" }] }
    });

    expect(model.summary()).toMatchObject({ componentCount: 0, dependencyCount: 0, metadataPropertyCount: 0 });
    expect(model.componentRows()).toEqual([]);
    expect(model.dependencyRows()).toEqual([]);
    expect(model.metadataProperties()).toEqual([]);
  });
});
