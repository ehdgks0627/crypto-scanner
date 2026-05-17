import { Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "./layout";
import { lazyRoute } from "./lazyRoute";
import { LoadingState } from "../components/common/StateViews";

const DashboardPage = lazyRoute(() => import("../pages/DashboardPage"), "DashboardPage");
const TargetsPage = lazyRoute(() => import("../pages/TargetsPage"), "TargetsPage");
const TargetDetailPage = lazyRoute(() => import("../pages/TargetDetailPage"), "TargetDetailPage");
const DiscoveriesPage = lazyRoute(() => import("../pages/DiscoveriesPage"), "DiscoveriesPage");
const DiscoveryNewPage = lazyRoute(() => import("../pages/DiscoveryNewPage"), "DiscoveryNewPage");
const DiscoveryDetailPage = lazyRoute(() => import("../pages/DiscoveryDetailPage"), "DiscoveryDetailPage");
const ScansPage = lazyRoute(() => import("../pages/ScansPage"), "ScansPage");
const ScanNewPage = lazyRoute(() => import("../pages/ScanNewPage"), "ScanNewPage");
const ScanDetailPage = lazyRoute(() => import("../pages/ScanDetailPage"), "ScanDetailPage");
const SnapshotsPage = lazyRoute(() => import("../pages/SnapshotsPage"), "SnapshotsPage");
const SnapshotDetailPage = lazyRoute(() => import("../pages/SnapshotDetailPage"), "SnapshotDetailPage");
const AssetDetailPage = lazyRoute(() => import("../pages/AssetDetailPage"), "AssetDetailPage");
const SnapshotDiffPage = lazyRoute(() => import("../pages/SnapshotDiffPage"), "SnapshotDiffPage");
const SnapshotRiskPage = lazyRoute(() => import("../pages/SnapshotRiskPage"), "SnapshotRiskPage");
const SnapshotMigrationPage = lazyRoute(() => import("../pages/SnapshotMigrationPage"), "SnapshotMigrationPage");
const SnapshotPerformancePage = lazyRoute(() => import("../pages/SnapshotPerformancePage"), "SnapshotPerformancePage");
const RiskPage = lazyRoute(() => import("../pages/RiskPage"), "RiskPage");
const MigrationPage = lazyRoute(() => import("../pages/MigrationPage"), "MigrationPage");
const PerformancePage = lazyRoute(() => import("../pages/PerformancePage"), "PerformancePage");
const AgentsPage = lazyRoute(() => import("../pages/AgentsPage"), "AgentsPage");
const SettingsPage = lazyRoute(() => import("../pages/SettingsPage"), "SettingsPage");
const TodoPage = lazyRoute(() => import("../pages/TodoPage"), "TodoPage");

function page(element: JSX.Element) {
  return <Suspense fallback={<LoadingState />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: page(<DashboardPage />) },
      { path: "targets", element: page(<TargetsPage />) },
      { path: "targets/:id", element: page(<TargetDetailPage />) },
      { path: "discoveries", element: page(<DiscoveriesPage />) },
      { path: "discoveries/new", element: page(<DiscoveryNewPage />) },
      { path: "discoveries/:id", element: page(<DiscoveryDetailPage />) },
      { path: "scans", element: page(<ScansPage />) },
      { path: "scans/new", element: page(<ScanNewPage />) },
      { path: "scans/:id", element: page(<ScanDetailPage />) },
      { path: "snapshots", element: page(<SnapshotsPage />) },
      { path: "snapshots/:id", element: page(<SnapshotDetailPage />) },
      { path: "snapshots/:id/assets/:aid", element: page(<AssetDetailPage />) },
      { path: "snapshots/:id/diff", element: page(<SnapshotDiffPage />) },
      { path: "snapshots/:id/risk", element: page(<SnapshotRiskPage />) },
      { path: "snapshots/:id/migration", element: page(<SnapshotMigrationPage />) },
      { path: "snapshots/:id/performance", element: page(<SnapshotPerformancePage />) },
      { path: "agents", element: page(<AgentsPage />) },
      { path: "settings", element: page(<SettingsPage />) },
      { path: "migration", element: page(<MigrationPage />) },
      { path: "performance", element: page(<PerformancePage />) },
      { path: "risk", element: page(<RiskPage />) },
      { path: "*", element: <Navigate to="/" replace /> }
    ]
  }
]);
