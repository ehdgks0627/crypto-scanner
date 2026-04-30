import { Database } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { Select } from "../../components/ui/form";
import type { Schema } from "../../api/types";
import { formatDateTime } from "../../lib/format";
import { useSelectedSnapshot } from "./useSelectedSnapshot";

type SnapshotOption = Pick<Schema<"CbomSnapshot">, "id" | "created_at">;

export function GlobalSnapshotSelector() {
  const navigate = useNavigate();
  const location = useLocation();
  const { snapshots, snapshotItems, selectedSnapshotId, setSelectedSnapshotId } = useSelectedSnapshot();
  const disabled = snapshots.isLoading || snapshots.isError || snapshotItems.length === 0;
  const latestSnapshotId = getLatestSnapshotId(snapshotItems);

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
            {formatSnapshotOptionLabel(snapshot, latestSnapshotId)}
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
  if (segments[2] === "performance") {
    return `/snapshots/${snapshotId}/performance`;
  }
  if (segments[2] === "diff") {
    return `/snapshots/${snapshotId}/diff`;
  }
  return "/snapshots";
}

export function getLatestSnapshotId(snapshots: SnapshotOption[]) {
  let latest: SnapshotOption | null = null;
  for (const snapshot of snapshots) {
    if (!latest || compareSnapshotRecency(snapshot, latest) > 0) {
      latest = snapshot;
    }
  }
  return latest?.id ?? null;
}

export function formatSnapshotOptionLabel(snapshot: SnapshotOption, latestSnapshotId: number | null) {
  const prefix = snapshot.id === latestSnapshotId ? "최신 · " : "";
  return `${prefix}#${snapshot.id} · ${formatDateTime(snapshot.created_at)}`;
}

function compareSnapshotRecency(a: SnapshotOption, b: SnapshotOption) {
  const aTime = Date.parse(a.created_at);
  const bTime = Date.parse(b.created_at);
  const aRank = Number.isFinite(aTime) ? aTime : 0;
  const bRank = Number.isFinite(bTime) ? bTime : 0;
  if (aRank !== bRank) {
    return aRank - bRank;
  }
  return a.id - b.id;
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
