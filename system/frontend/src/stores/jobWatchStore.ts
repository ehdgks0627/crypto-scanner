import { create } from "zustand";

type JobWatchState = {
  trackedJobIds: number[];
  trackJob: (jobId: number) => void;
  untrackJob: (jobId: number) => void;
};

export const useJobWatchStore = create<JobWatchState>((set) => ({
  trackedJobIds: [],
  trackJob: (jobId) =>
    set((state) => ({
      trackedJobIds: state.trackedJobIds.includes(jobId) ? state.trackedJobIds : [...state.trackedJobIds, jobId]
    })),
  untrackJob: (jobId) =>
    set((state) => ({
      trackedJobIds: state.trackedJobIds.filter((trackedJobId) => trackedJobId !== jobId)
    }))
}));
