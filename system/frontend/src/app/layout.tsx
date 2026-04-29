import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, Database, Gauge, ListChecks, Moon, Radar, RefreshCw, Server, Settings, ShieldAlert, Sun, Target, Workflow } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { queryKeys } from "../api/queryKeys";
import { services } from "../api/services";
import { Button } from "../components/ui/button";
import { isActiveJobStatus, isTerminalJobStatus } from "../domain/jobStatus";
import { useJobWatchStore } from "../stores/jobWatchStore";
import { useUiStore } from "../stores/uiStore";

const navItems = [
  { to: "/", label: "대시보드", icon: Gauge },
  { to: "/targets", label: "타겟", icon: Target },
  { to: "/discoveries", label: "디스커버리", icon: Radar },
  { to: "/scans", label: "스캔", icon: Activity },
  { to: "/snapshots", label: "스냅샷", icon: Database },
  { to: "/cbom", label: "CBOM", icon: Server },
  { to: "/agents", label: "에이전트", icon: Bot },
  { to: "/settings", label: "설정", icon: Settings }
];

export function AppLayout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { theme, toggleTheme } = useUiStore();
  const trackedJobIds = useJobWatchStore((state) => state.trackedJobIds);
  const untrackJob = useJobWatchStore((state) => state.untrackJob);
  const health = useQuery({
    queryKey: queryKeys.health,
    queryFn: () => services.health.get(),
    refetchInterval: 60_000
  });
  const runningJobs = useQuery({
    queryKey: queryKeys.jobs.list("RUNNING"),
    queryFn: () => services.jobs.list("RUNNING"),
    refetchInterval: 5_000
  });
  const pendingJobs = useQuery({
    queryKey: queryKeys.jobs.list("PENDING"),
    queryFn: () => services.jobs.list("PENDING"),
    refetchInterval: 5_000
  });
  const recentJobs = useQuery({
    queryKey: queryKeys.jobs.list(),
    queryFn: () => services.jobs.list(),
    refetchInterval: 15_000
  });

  const healthStatus = health.data?.status ?? (health.isError ? "down" : "degraded");
  const activeCount = (runningJobs.data?.total ?? 0) + (pendingJobs.data?.total ?? 0);
  const activeJobIds = useMemo(
    () => [...(runningJobs.data?.items ?? []), ...(pendingJobs.data?.items ?? [])].map((job) => job.id).sort((a, b) => a - b),
    [pendingJobs.data?.items, runningJobs.data?.items]
  );
  const previousActiveJobIds = useRef<number[]>([]);
  const previousRecentJobSignature = useRef<string | null>(null);
  const trackedJobs = useQueries({
    queries: trackedJobIds.map((jobId) => ({
      queryKey: queryKeys.jobs.detail(jobId),
      queryFn: () => services.jobs.get(jobId),
      refetchInterval: 3_000
    }))
  });
  const invalidateJobDerivedData = useCallback(
    (snapshotId?: number) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.migration.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.discoveries.all });
      if (snapshotId) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.detail(snapshotId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.assetsPrefix(snapshotId) });
      }
    },
    [queryClient]
  );

  useEffect(() => {
    const previous = previousActiveJobIds.current;
    const completedOrCancelled = previous.some((jobId) => !activeJobIds.includes(jobId));
    previousActiveJobIds.current = activeJobIds;
    if (!completedOrCancelled) {
      return;
    }
    invalidateJobDerivedData();
    void runningJobs.refetch();
    void pendingJobs.refetch();
  }, [activeJobIds, invalidateJobDerivedData, pendingJobs, runningJobs]);

  useEffect(() => {
    const items = recentJobs.data?.items ?? [];
    const signature = items.map((job) => `${job.id}:${job.status}:${job.finished_at ?? ""}`).join("|");
    if (previousRecentJobSignature.current === null) {
      previousRecentJobSignature.current = signature;
      return;
    }
    if (previousRecentJobSignature.current === signature) {
      return;
    }
    previousRecentJobSignature.current = signature;
    if (items.some((job) => isTerminalJobStatus(job.status))) {
      invalidateJobDerivedData();
    }
  }, [invalidateJobDerivedData, recentJobs.data?.items]);

  useEffect(() => {
    trackedJobs.forEach((query, index) => {
      const job = query.data;
      if (!job || isActiveJobStatus(job.status)) {
        return;
      }
      untrackJob(trackedJobIds[index]);
      invalidateJobDerivedData(job.result?.snapshot_id ?? undefined);
    });
  }, [invalidateJobDerivedData, trackedJobIds, trackedJobs, untrackJob]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <button className="brand" type="button" onClick={() => navigate("/")}>
          <ShieldAlert size={20} />
          <span>PQC Risk Assessment</span>
        </button>
        <div className="app-header__actions">
          <Button type="button" variant="ghost" onClick={() => navigate("/scans")}>
            <RefreshCw size={15} />
            활성 Job: {activeCount}
          </Button>
          <span className={`health-dot health-dot--${healthStatus}`} title={`health: ${healthStatus}`} />
          <Button type="button" variant="ghost" size="icon" onClick={toggleTheme} aria-label="테마 변경">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
        </div>
      </header>
      <aside className="app-sidebar">
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink key={item.to} to={item.to} end={item.to === "/"}>
                <Icon size={16} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
        <NavLink to="/snapshots" className="sidebar-link-secondary">
          <ListChecks size={16} />
          <span>마이그레이션</span>
        </NavLink>
        <NavLink to="/snapshots" className="sidebar-link-secondary">
          <Workflow size={16} />
          <span>위험평가</span>
        </NavLink>
      </aside>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
