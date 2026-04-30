import { create } from "zustand";

const STORAGE_KEY = "pqc-selected-snapshot-id";

type SnapshotSelectionState = {
  selectedSnapshotId: number | null;
  setSelectedSnapshotId: (snapshotId: number) => void;
  clearSelectedSnapshotId: () => void;
};

function readStoredSnapshotId() {
  if (typeof localStorage === "undefined") {
    return null;
  }
  const value = Number(localStorage.getItem(STORAGE_KEY));
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

export const useSnapshotSelectionStore = create<SnapshotSelectionState>((set) => ({
  selectedSnapshotId: readStoredSnapshotId(),
  setSelectedSnapshotId: (snapshotId) => {
    localStorage.setItem(STORAGE_KEY, String(snapshotId));
    set({ selectedSnapshotId: snapshotId });
  },
  clearSelectedSnapshotId: () => {
    localStorage.removeItem(STORAGE_KEY);
    set({ selectedSnapshotId: null });
  }
}));
