import { Database } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { Select } from "../../components/ui/form";
import { formatDateTime } from "../../lib/format";
import { useSelectedSnapshot } from "./useSelectedSnapshot";

export function GlobalSnapshotSelector() {
  const navigate = useNavigate();
  const location = useLocation();
  const { snapshots, snapshotItems, selectedSnapshotId, setSelectedSnapshotId } = useSelectedSnapshot();
  const disabled = snapshots.isLoading || snapshots.isError || snapshotItems.length === 0;

  function selectSnapshot(snapshotId: number) {
    setSelectedSnapshotId(snapshotId);
    const nextPath = getSnapshotSelectionPath(location.pathname, snapshotId);
    if (nextPath && nextPath !== `${location.pathname}${location.search}`) {
      navigate(nextPath);
    }
  }

  return (
    <label className="global-snapshot-selector">
      <span className="global-snapshot-selector__label">
        <Database size={14} />
        Snapshot
      </span>
      <Select
        aria-label="전역 Snapshot 선택"
        className="global-snapshot-selector__select"
        disabled={disabled}
        value={disabled ? "" : selectedSnapshotId ?? ""}
        onChange={(event) => selectSnapshot(Number(event.target.value))}
      >
        {disabled ? <option value="">{snapshotSelectorPlaceholder(snapshots.status)}</option> : null}
        {snapshotItems.map((snapshot) => (
          <option key={snapshot.id} value={snapshot.id}>
            #{snapshot.id} · {formatDateTime(snapshot.created_at)}
          </option>
        ))}
      </Select>
    </label>
  );
}

export function getSnapshotSelectionPath(pathname: string, snapshotId: number) {
  const segments = pathname.split("/").filter(Boolean);
  if (segments[0] !== "snapshots" || !segments[1]) {
    return null;
  }
  if (segments[2] === "risk") {
    return `/snapshots/${snapshotId}/risk`;
  }
  if (segments[2] === "migration") {
    return `/snapshots/${snapshotId}/migration`;
  }
  if (segments[2] === "diff") {
    return `/snapshots/${snapshotId}/diff`;
  }
  return "/snapshots";
}

function snapshotSelectorPlaceholder(status: "pending" | "error" | "success") {
  if (status === "pending") {
    return "불러오는 중";
  }
  if (status === "error") {
    return "불러오기 실패";
  }
  return "스냅샷 없음";
}
