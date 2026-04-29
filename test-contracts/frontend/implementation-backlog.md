# Frontend Implementation Backlog

This backlog tracks the end-to-end React implementation for the API contract.
The frontend must be assembled from shared domain/API/UI modules first, then
feature pages. Pages should stay thin route composition layers.

## Phase FE-1: Project Scaffold And Contract Types

- [x] `FE-SCAFFOLD-001` Create `system/frontend` Vite + React + TypeScript project structure.
- [x] `FE-SCAFFOLD-002` Add package scripts for dev, build, typecheck, test, lint, and OpenAPI type generation.
- [x] `FE-SCAFFOLD-003` Generate API types from `docs/api/openapi.yaml` into `src/api/generated/types.ts`.
- [x] `FE-SCAFFOLD-004` Configure app providers, router, styles, and test setup.

## Phase FE-2: Shared OOP-Oriented Foundation

- [x] `FE-FOUNDATION-001` Implement `ApiClient` with typed request handling, errors, and query-string serialization.
- [x] `FE-FOUNDATION-002` Implement service classes for dashboard, targets, discoveries, jobs, snapshots, assets, risk, migration, agents, meta, and health.
- [x] `FE-FOUNDATION-003` Implement shared query key factory and TanStack Query hooks.
- [x] `FE-FOUNDATION-004` Implement shared domain models, formatters, constants, and Zustand UI store.

## Phase FE-3: Shared UI Primitives

- [x] `FE-UI-001` Implement layout shell, header, sidebar, and route outlet.
- [x] `FE-UI-002` Implement reusable Button, Card, Badge, Input, Select, Textarea, Checkbox, Dialog, Tabs, Table, EmptyState, and Progress primitives.
- [x] `FE-UI-003` Implement risk/status badges, page headers, filter bars, metric cards, chart cards, JSON preview, and graph placeholder primitives.
- [x] `FE-UI-004` Apply dashboard-grade responsive styling and dark-mode support.

## Phase FE-4: Feature Pages

- [x] `FE-PAGE-001` Implement Dashboard overview with snapshot selection, KPI cards, charts, and recent jobs.
- [x] `FE-PAGE-002` Implement Targets list, create form, detail view, context editing, and delete flow.
- [x] `FE-PAGE-003` Implement Discoveries list, start form, detail endpoints, and promote flow.
- [x] `FE-PAGE-004` Implement Scan Jobs list, start form, detail progress/logs, and cancel flow.
- [x] `FE-PAGE-005` Implement Snapshots list/detail, asset inventory, asset detail, context patch, and qualitative assessment.
- [x] `FE-PAGE-006` Implement Snapshot diff, risk assessment, risk weights editing, recompute, migration plan, and impact views.
- [x] `FE-PAGE-007` Implement CBOM export hub, Agents management, and Settings page.

## Phase FE-5: Verification

- [x] `FE-VERIFY-001` Add unit/component tests for shared API/query/UI behavior and core pages.
- [x] `FE-VERIFY-002` Run typecheck, unit tests, and production build.
- [x] `FE-VERIFY-003` Start local frontend dev server for manual inspection.

## Phase FE-6: Flow Completion Polish

- [x] `FE-FLOW-001` Preserve target context when starting a scan from a target detail page.
- [x] `FE-FLOW-002` Link completed job results, risk rows, and dependency graph nodes to their detail pages.
- [x] `FE-FLOW-003` Add migration plan filters, report selection, impact-driven Markdown report download, and domain tests.

## Phase FE-7: Post-Review Stability

- [x] `FE-STAB-001` Add safe confirmation flows for cancel/delete/deactivate and explicit discovery promotion selection.
- [x] `FE-STAB-002` Fix active job/discovery polling, endpoint refresh, scan preselection reconciliation, and query-state filters.
- [x] `FE-STAB-003` Align target/asset context patch payloads with nullable OpenAPI contracts and poll recompute jobs before broad invalidation.
- [x] `FE-STAB-004` Add regression tests for target patch serialization, discovery promotion payloads, migration report fallback, and download side effects.

## Phase FE-8: Final Revalidation Stability

- [x] `FE-REVAL-001` Expose Discovery `job_id` and `port_list` through the OpenAPI-generated type path and remove runtime casts from cancellation/list rendering.
- [x] `FE-REVAL-002` Align cancel affordances with backend policy, including non-cancellable running recompute jobs and already requested cancels.
- [x] `FE-REVAL-003` Count pending plus running jobs in the global active-job indicator and surface job-log query failures.
- [x] `FE-REVAL-004` Validate risk weights as 0.5-2.0 finite values, prevent blank-to-zero coercion, and block duplicate recompute submits while polling.
- [x] `FE-REVAL-005` Keep migration invalid-filter states isolated from cached rows while allowing report download with impact-analysis fallback.
- [x] `FE-REVAL-006` Extract discovery port parsing and asset-context patch serialization into tested domain helpers.
- [x] `FE-REVAL-007` Lock target and asset context forms while create/update mutations are pending.
- [x] `FE-REVAL-008` Remove browser-bundled shared API token support; production auth must be handled by same-origin server/proxy or a future user auth layer.
- [x] `FE-REVAL-009` Broaden job-derived invalidation with recent-job polling and tracked terminal job handling.
- [x] `FE-REVAL-010` Invalidate dashboard/asset/snapshot caches after agent or target mutations that affect cross-page summaries.
- [x] `FE-REVAL-011` Validate asset context lifespan input before submit and cover invalid numeric cases with tests.
- [x] `FE-REVAL-012` Add frontend CI gates for typecheck, unit tests, and production build.
