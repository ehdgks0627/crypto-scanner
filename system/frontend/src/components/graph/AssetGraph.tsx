import { Background, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { Schema } from "../../api/types";

export function AssetGraph({
  dependencies,
  onAssetSelect
}: {
  dependencies: Schema<"AssetDependencies">;
  onAssetSelect?: (assetId: number) => void;
}) {
  const nodes = [
    { id: "current", position: { x: 220, y: 120 }, data: { label: "현재 자산" } },
    ...dependencies.dependsOn.map((item, index) => ({
      id: `asset-${item.id}`,
      position: { x: 20, y: index * 90 },
      data: { label: item.name, assetId: item.id }
    })),
    ...dependencies.dependedBy.map((item, index) => ({
      id: `asset-by-${item.id}`,
      position: { x: 440, y: index * 90 },
      data: { label: item.name, assetId: item.id }
    }))
  ];
  const edges = [
    ...dependencies.dependsOn.map((item) => ({ id: `e-dep-${item.id}`, source: "current", target: `asset-${item.id}` })),
    ...dependencies.dependedBy.map((item) => ({ id: `e-by-${item.id}`, source: `asset-by-${item.id}`, target: "current" }))
  ];

  const linkedAssets = [...dependencies.dependsOn, ...dependencies.dependedBy];

  return (
    <div className="section-stack">
      <div className="asset-graph">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          onNodeClick={(_, node) => {
            const assetId = (node.data as { assetId?: number }).assetId;
            if (assetId) {
              onAssetSelect?.(assetId);
            }
          }}
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>
      {linkedAssets.length > 0 ? (
        <div className="inline-actions" aria-label="의존성 탐색">
          {linkedAssets.map((asset) => (
            <button key={`${asset.semantic}-${asset.id}`} type="button" className="link-button" onClick={() => onAssetSelect?.(asset.id)}>
              {asset.name}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
