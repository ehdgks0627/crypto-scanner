import { lazy, Suspense, type ComponentType } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppLayout } from "./layout";
import { LoadingState } from "../components/common/StateViews";

const DashboardPage = lazy(() => import("../pages/DashboardPage").then(toDefault("DashboardPage")));
const TargetsPage = lazy(() => import("../pages/TargetsPage").then(toDefault("TargetsPage")));
const TargetDetailPage = lazy(() => import("../pages/TargetDetailPage").then(toDefault("TargetDetailPage")));
const DiscoveriesPage = lazy(() => import("../pages/DiscoveriesPage").then(toDefault("DiscoveriesPage")));
const DiscoveryNewPage = lazy(() => import("../pages/DiscoveryNewPage").then(toDefault("DiscoveryNewPage")));
const DiscoveryDetailPage = lazy(() => import("../pages/DiscoveryDetailPage").then(toDefault("DiscoveryDetailPage")));
const ScansPage = lazy(() => import("../pages/ScansPage").then(toDefault("ScansPage")));
const ScanNewPage = lazy(() => import("../pages/ScanNewPage").then(toDefault("ScanNewPage")));
const ScanDetailPage = lazy(() => import("../pages/ScanDetailPage").then(toDefault("ScanDetailPage")));
const SnapshotsPage = lazy(() => import("../pages/SnapshotsPage").then(toDefault("SnapshotsPage")));
const SnapshotDetailPage = lazy(() => import("../pages/SnapshotDetailPage").then(toDefault("SnapshotDetailPage")));
const AssetDetailPage = lazy(() => import("../pages/AssetDetailPage").then(toDefault("AssetDetailPage")));
const SnapshotDiffPage = lazy(() => import("../pages/SnapshotDiffPage").then(toDefault("SnapshotDiffPage")));
const SnapshotRiskPage = lazy(() => import("../pages/SnapshotRiskPage").then(toDefault("SnapshotRiskPage")));
const SnapshotMigrationPage = lazy(() => import("../pages/SnapshotMigrationPage").then(toDefault("SnapshotMigrationPage")));
const CbomPage = lazy(() => import("../pages/CbomPage").then(toDefault("CbomPage")));
const AgentsPage = lazy(() => import("../pages/AgentsPage").then(toDefault("AgentsPage")));
const SettingsPage = lazy(() => import("../pages/SettingsPage").then(toDefault("SettingsPage")));

function toDefault<T extends Record<string, ComponentType>>(key: keyof T) {
  return (module: T) => ({ default: module[key] });
}

function page(element: JSX.Element) {
  return <Suspense fallback={<LoadingState />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: page(<DashboardPage />) },
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
      { path: "cbom", element: page(<CbomPage />) },
      { path: "agents", element: page(<AgentsPage />) },
      { path: "settings", element: page(<SettingsPage />) },
      { path: "*", element: <Navigate to="/" replace /> }
    ]
  }
]);
