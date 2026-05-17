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
  const hasSnapshotList = Boolean(snapshots.data);
  const items = snapshots.data?.items ?? [];
  const selectedSnapshot = useMemo(
    () => (hasSnapshotList && items.length ? items.find((snapshot) => snapshot.id === selectedSnapshotId) ?? items[0] : null),
    [hasSnapshotList, items, selectedSnapshotId]
  );

  useEffect(() => {
    if (!hasSnapshotList) {
      return;
    }
    if (!items.length) {
      return;
    }
    if (selectedSnapshot?.id === selectedSnapshotId) {
      return;
    }
    setSelectedSnapshotId(selectedSnapshot?.id ?? items[0].id);
  }, [hasSnapshotList, items, selectedSnapshot?.id, selectedSnapshotId, setSelectedSnapshotId]);

  return {
    snapshots,
    snapshotItems: items,
    selectedSnapshot,
    selectedSnapshotId: hasSnapshotList ? selectedSnapshot?.id ?? null : selectedSnapshotId ?? null,
    setSelectedSnapshotId
  };
}
