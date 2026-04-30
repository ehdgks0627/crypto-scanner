import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { queryKeys } from "../../api/queryKeys";
import { services } from "../../api/services";
import { useSnapshotSelectionStore } from "../../stores/snapshotSelectionStore";

export function useSelectedSnapshot() {
  const selectedSnapshotId = useSnapshotSelectionStore((state) => state.selectedSnapshotId);
  const setSelectedSnapshotId = useSnapshotSelectionStore((state) => state.setSelectedSnapshotId);
  const snapshots = useQuery({
    queryKey: queryKeys.snapshots.all,
    queryFn: () => services.snapshots.list()
  });
  const items = snapshots.data?.items ?? [];
  const selectedSnapshot = useMemo(
    () => items.find((snapshot) => snapshot.id === selectedSnapshotId) ?? items[0] ?? null,
    [items, selectedSnapshotId]
  );

  useEffect(() => {
    if (!items.length || selectedSnapshot?.id === selectedSnapshotId) {
      return;
    }
    setSelectedSnapshotId(items[0].id);
  }, [items, selectedSnapshot?.id, selectedSnapshotId, setSelectedSnapshotId]);

  return {
    snapshots,
    snapshotItems: items,
    selectedSnapshot,
    selectedSnapshotId: selectedSnapshot?.id ?? selectedSnapshotId ?? null,
    setSelectedSnapshotId
  };
}
