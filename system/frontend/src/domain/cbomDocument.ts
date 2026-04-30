export type CbomPropertyRow = {
  name: string;
  value: string;
};

export type CbomComponentRow = {
  bomRef: string;
  name: string;
  type: string;
  assetType: string;
  algorithm: string;
  algorithmFamily: string;
  primitive: string;
  quantumVulnerable: string;
  riskTier: string;
  riskScore: string;
};

export type CbomDependencyRow = {
  ref: string;
  dependsOn: string[];
};

export type CbomSummary = {
  bomFormat: string;
  specVersion: string;
  serialNumber: string;
  version: string;
  timestamp: string;
  toolName: string;
  componentCount: number;
  dependencyCount: number;
  metadataPropertyCount: number;
};

export class CbomDocumentModel {
  constructor(private readonly document: Record<string, unknown> | null | undefined) {}

  summary(): CbomSummary {
    const metadata = recordValue(this.document?.metadata);
    const metadataProperties = this.metadataProperties();
    return {
      bomFormat: textValue(this.document?.bomFormat),
      specVersion: textValue(this.document?.specVersion),
      serialNumber: textValue(this.document?.serialNumber),
      version: textValue(this.document?.version),
      timestamp: textValue(metadata?.timestamp),
      toolName: this.toolName(metadata),
      componentCount: this.componentRows().length,
      dependencyCount: this.dependencyRows().length,
      metadataPropertyCount: metadataProperties.length
    };
  }

  metadataProperties(): CbomPropertyRow[] {
    const metadata = recordValue(this.document?.metadata);
    return propertyRows(metadata?.properties);
  }

  componentRows(): CbomComponentRow[] {
    return recordRows(this.document?.components).map((component) => {
      const cryptoProperties = recordValue(component.cryptoProperties);
      const algorithmProperties = recordValue(cryptoProperties?.algorithmProperties);
      const properties = propertyRows(component.properties);
      return {
        bomRef: textValue(component["bom-ref"] ?? component.bomRef),
        name: textValue(component.name),
        type: textValue(component.type),
        assetType: firstText(cryptoProperties?.assetType, propertyValue(properties, "internal:asset_type")),
        algorithm: firstText(
          cryptoProperties?.algorithm,
          algorithmProperties?.parameterSetIdentifier,
          propertyValue(properties, "internal:algorithm")
        ),
        algorithmFamily: firstText(cryptoProperties?.algorithmFamily, propertyValue(properties, "internal:family"), propertyValue(properties, "algorithm.family")),
        primitive: firstText(algorithmProperties?.primitive, propertyValue(properties, "internal:primitive")),
        quantumVulnerable: firstText(propertyValue(properties, "internal:quantum_vulnerable"), propertyValue(properties, "quantum_vulnerable")),
        riskTier: firstText(propertyValue(properties, "risk.tier"), propertyValue(properties, "internal:risk_tier")),
        riskScore: firstText(propertyValue(properties, "risk.score"), propertyValue(properties, "internal:risk_score"))
      };
    });
  }

  dependencyRows(): CbomDependencyRow[] {
    return recordRows(this.document?.dependencies).map((dependency) => ({
      ref: textValue(dependency.ref),
      dependsOn: arrayValues(dependency.dependsOn).map(textValue).filter((value) => value !== "-")
    }));
  }

  private toolName(metadata: Record<string, unknown> | undefined) {
    const component = recordValue(metadata?.component);
    const tools = recordValue(metadata?.tools);
    const toolComponent = recordRows(tools?.components)[0];
    return firstText(toolComponent?.name, component?.name);
  }
}

function propertyRows(value: unknown): CbomPropertyRow[] {
  return recordRows(value)
    .map((property) => ({
      name: textValue(property.name),
      value: textValue(property.value)
    }))
    .filter((property) => property.name !== "-");
}

function propertyValue(properties: CbomPropertyRow[], name: string) {
  return properties.find((property) => property.name === name)?.value;
}

function firstText(...values: unknown[]) {
  for (const value of values) {
    const text = textValue(value);
    if (text !== "-") {
      return text;
    }
  }
  return "-";
}

function textValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (Array.isArray(value)) {
    const joined = value.map(textValue).filter((item) => item !== "-").join(", ");
    return joined || "-";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "-";
    }
  }
  return String(value);
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
}

function recordRows(value: unknown): Record<string, unknown>[] {
  return arrayValues(value).flatMap((item) => {
    const record = recordValue(item);
    return record ? [record] : [];
  });
}

function arrayValues(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}
