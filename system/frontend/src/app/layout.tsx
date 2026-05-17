import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Bot, Database, Gauge, ListChecks, Moon, Radar, RefreshCw, Settings, ShieldAlert, Sun, Target, Timer, Workflow } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { queryKeys } from "../api/queryKeys";
import { services } from "../api/services";
import { Button } from "../components/ui/button";
import { isActiveJobStatus, isTerminalJobStatus } from "../domain/jobStatus";
import { GlobalSnapshotSelector } from "../features/snapshots/GlobalSnapshotSelector";
import { useJobWatchStore } from "../stores/jobWatchStore";
import { useSnapshotSelectionStore } from "../stores/snapshotSelectionStore";
import { useUiStore } from "../stores/uiStore";
import { getSnapshotSidebarState, type SnapshotSidebarState } from "./snapshotSidebar";

type NavItem = {
  key: "dashboard" | "assets" | "risk" | "migration" | "performance" | "discoveries" | "targets" | "scans" | "agents" | "settings";
  to: string;
  label: string;
  icon: typeof Gauge;
  end?: boolean;
};

const reportNavItems: NavItem[] = [
  { key: "dashboard", to: "/dashboard", label: "대시보드", icon: Gauge, end: true },
  { key: "assets", to: "/snapshots", label: "식별 자산", icon: Database },
  { key: "risk", to: "/risk", label: "위험평가", icon: Workflow },
  { key: "migration", to: "/migration", label: "Review Targets", icon: ListChecks },
  { key: "performance", to: "/performance", label: "가용성 검사", icon: Timer }
];

const operationNavItems: NavItem[] = [
  { key: "discoveries", to: "/discoveries", label: "탐색 대상", icon: Radar },
  { key: "targets", to: "/targets", label: "스캔 대상", icon: Target },
  { key: "scans", to: "/scans", label: "스캔 실행", icon: Activity },
  { key: "agents", to: "/agents", label: "에이전트", icon: Bot },
  { key: "settings", to: "/settings", label: "설정", icon: Settings }
];

export function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { theme, toggleTheme } = useUiStore();
  const setSelectedSnapshotId = useSnapshotSelectionStore((state) => state.setSelectedSnapshotId);
  const trackedJobIds = useJobWatchStore((state) => state.trackedJobIds);
  const untrackJob = useJobWatchStore((state) => state.untrackJob);
  const snapshotSidebarState = useMemo(() => getSnapshotSidebarState(location.pathname), [location.pathname]);
  const routeSnapshotId = useMemo(() => getRouteSnapshotId(location.pathname), [location.pathname]);
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

  useEffect(() => {
    if (routeSnapshotId) {
      setSelectedSnapshotId(routeSnapshotId);
    }
  }, [routeSnapshotId, setSelectedSnapshotId]);
  const invalidateJobDerivedData = useCallback(
    (snapshotId?: number) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.snapshots.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.risk.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.migration.all });
      void queryClient.invalidateQueries({ queryKey: queryKeys.performance.all });
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
          <span>PQC 위험 평가</span>
        </button>
        <div className="app-header__actions">
          <GlobalSnapshotSelector />
          <Button type="button" variant="ghost" onClick={() => navigate("/scans")} aria-label={`활성 작업: ${activeCount}`}>
            <RefreshCw size={15} />
            활성 작업: {activeCount}
          </Button>
          <span className={`health-dot health-dot--${healthStatus}`} title={`상태: ${healthStatus}`} />
          <Button type="button" variant="ghost" size="icon" onClick={toggleTheme} aria-label="테마 변경">
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </Button>
        </div>
      </header>
      <aside className="app-sidebar">
        <nav aria-label="기본 탐색">
          <SidebarSection title="보고 / 조회" items={reportNavItems} snapshotSidebarState={snapshotSidebarState} />
          <SidebarSection title="운영 / 설정" items={operationNavItems} snapshotSidebarState={snapshotSidebarState} />
        </nav>
      </aside>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}

function SidebarSection({
  title,
  items,
  snapshotSidebarState
}: {
  title: string;
  items: NavItem[];
  snapshotSidebarState: SnapshotSidebarState;
}) {
  return (
    <div className="sidebar-nav-section">
      <span className="sidebar-nav-section__label">{title}</span>
      {items.map((item) => (
        <SidebarNavLink key={item.key} item={item} snapshotSidebarState={snapshotSidebarState} />
      ))}
    </div>
  );
}

function SidebarNavLink({ item, snapshotSidebarState }: { item: NavItem; snapshotSidebarState: SnapshotSidebarState }) {
  const Icon = item.icon;
  const resolvedPath = resolveNavPath(item, snapshotSidebarState);
  const active = isSpecialNavActive(item, snapshotSidebarState);

  if (active !== null) {
    return (
      <Link to={resolvedPath} className={active ? "active" : undefined} aria-current={active ? "page" : undefined}>
        <Icon size={16} />
        <span>{item.label}</span>
      </Link>
    );
  }

  return (
    <NavLink to={resolvedPath} end={item.end}>
      <Icon size={16} />
      <span>{item.label}</span>
    </NavLink>
  );
}

function resolveNavPath(item: NavItem, snapshotSidebarState: SnapshotSidebarState) {
  if (item.key === "assets") {
    return "/snapshots";
  }
  if (item.key === "risk") {
    return snapshotSidebarState.riskPath;
  }
  if (item.key === "migration") {
    return snapshotSidebarState.migrationPath;
  }
  if (item.key === "performance") {
    return snapshotSidebarState.performancePath;
  }
  return item.to;
}

function isSpecialNavActive(item: NavItem, snapshotSidebarState: SnapshotSidebarState) {
  if (item.key === "assets") {
    return snapshotSidebarState.activeSection === "snapshot";
  }
  if (item.key === "risk") {
    return snapshotSidebarState.activeSection === "risk";
  }
  if (item.key === "migration") {
    return snapshotSidebarState.activeSection === "migration";
  }
  if (item.key === "performance") {
    return snapshotSidebarState.activeSection === "performance";
  }
  return null;
}

function getRouteSnapshotId(pathname: string) {
  const segments = pathname.split("/").filter(Boolean);
  if (segments[0] !== "snapshots") {
    return null;
  }
  const snapshotId = Number(segments[1]);
  return Number.isSafeInteger(snapshotId) && snapshotId > 0 ? snapshotId : null;
}
