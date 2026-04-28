# 09. 프론트엔드 페이지 명세

## 9.1 개요

본 문서는 React 기반 대시보드의 페이지 구성, 컴포넌트, 라우팅을 정의한다. 각 페이지는 명확한 책임을 가지며 8장 API와 1:1 또는 1:N으로 매핑된다.

### 9.1.1 기술 스택 요약

| 항목 | 선택 |
|---|---|
| 프레임워크 | React 18 + TypeScript |
| 빌드 | Vite |
| 라우팅 | React Router v6 |
| 서버 상태 | TanStack Query v5 |
| 클라이언트 상태 | Zustand (가벼운 전역 상태용) |
| UI 컴포넌트 | shadcn/ui (Radix UI + Tailwind) |
| 차트 | Recharts |
| 폼 | React Hook Form + Zod |
| 다이어그램 (자산 그래프) | React Flow |
| 아이콘 | lucide-react |
| 다크모드 | shadcn 기본 테마 토글 (라이트 default, 27c) |
| 언어 | 한국어 (UI 텍스트), 코드 주석은 영어 허용 |

## 9.2 라우팅 트리

```
/                           Dashboard (Overview)
/targets                    Targets 관리
/targets/:id                Target Detail (모달이 아닌 별도 페이지)
/discoveries                Discovery 작업 목록
/discoveries/new            Discovery 시작
/discoveries/:id            Discovery 결과 (Endpoint 선택 + Promote)
/scans                      Scan Job 목록
/scans/new                  Scan Job 시작 (Targets + Scanner 선택)
/scans/:id                  Scan Job 상세 (진행 + 로그)
/snapshots                  CBOM Snapshot 목록
/snapshots/:id              Snapshot 상세 (Asset Inventory 진입점)
/snapshots/:id/assets/:aid  Asset Detail
/snapshots/:id/diff         Snapshot Diff (선택 → 비교)
/snapshots/:id/risk         Risk Assessment (Top-N + 가중치 조정)
/snapshots/:id/migration    Migration Plan
/cbom                       CBOM Export 허브
/agents                     Agent 관리
/settings                   환경 설정 (가중치 default, 다크모드, Bootstrap 토큰 등)
```

## 9.3 글로벌 레이아웃

```
┌─────────────────────────────────────────────────────────────────┐
│  [로고] PQC Risk Assessment                  [⏵ 진행중 Job: 2]  [🌗] │  Header (sticky)
├──────────┬──────────────────────────────────────────────────────┤
│          │                                                      │
│ Sidebar  │              Main Content                            │
│          │                                                      │
│ 대시보드  │                                                      │
│ 타겟      │                                                      │
│ 디스커버리 │                                                      │
│ 스캔      │                                                      │
│ 스냅샷    │                                                      │
│ 위험평가  │                                                      │
│ 마이그레이션│                                                     │
│ 에이전트  │                                                      │
│ ────     │                                                      │
│ 설정      │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
```

| 영역 | 컴포넌트 | 설명 |
|---|---|---|
| Header | `<AppHeader />` | 로고, 활성 Job 카운터 (좌상단 → 우측 클릭 시 `/scans?status=RUNNING`), 다크모드 토글, 시스템 상태 인디케이터 (Worker/Redis 상태) |
| Sidebar | `<AppSidebar />` | 좌측 네비게이션, 활성 라우트 하이라이트 |
| Main | `<Outlet />` | React Router outlet |
| Toast | `<Toaster />` | shadcn sonner. 에러/성공 알림 |

### 9.3.1 활성 Job 카운터

Header 우측에 항상 표시. 5초 주기로 `/api/jobs?status=RUNNING&limit=1` 호출하여 카운트만 갱신. 클릭 시 Scan Jobs 목록으로 이동.

### 9.3.2 시스템 상태 인디케이터

Header에 작은 점 아이콘 (녹/황/적). 1분 주기로 `GET /api/health`를 호출해 API/DB/Redis/Worker 상태를 확인한다. `status=ok`는 녹색, `degraded`는 황색, `down` 또는 fetch 실패는 적색으로 표시한다.

## 9.4 페이지별 상세

### 9.4.1 Dashboard (`/`)

**목적**: 전체 시스템의 위험 현황을 한눈에 파악.

**API**: `GET /api/dashboard/summary` (snapshot_id 생략 시 최신).

**레이아웃**:

```
┌───────────────────────────────────────────────────────┐
│ Snapshot 선택: [2026-04-25 10:05 (#56) ▼]   [+ 새 스캔] │
├───────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│ │ 142    │ │  8     │ │ 75/142 │ │  3/3   │          │
│ │ 자산수  │ │Critical│ │양자취약 │ │Agents  │          │
│ └────────┘ └────────┘ └────────┘ └────────┘          │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────────┐  ┌─────────────────────────┐ │
│ │ 위험도 등급 분포 (도넛)│  │ 자산 타입 분포 (도넛)    │ │
│ └─────────────────────┘  └─────────────────────────┘ │
├───────────────────────────────────────────────────────┤
│ ┌─────────────────────┐  ┌─────────────────────────┐ │
│ │ 알고리즘 패밀리 분포  │  │ 양자취약/안전 비율       │ │
│ │ (가로 바)            │  │ (도넛)                   │ │
│ └─────────────────────┘  └─────────────────────────┘ │
├───────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────┐ │
│ │ 시간대별 트렌드 (라인)                              │ │
│ │ X: Snapshot, Y: Critical/Total 자산수              │ │
│ └──────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────┤
│ 최근 Scan Jobs (테이블, 5개)                          │
│  - #123 ✅ COMPLETED  3 targets  2026-04-25 10:00    │
│  - #122 ⏳ RUNNING    9 targets  2026-04-25 09:30    │
└───────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<SnapshotSelector />` — 드롭다운, 스냅샷 목록 (`GET /api/snapshots`)
- `<KpiCard />` × 4 — 자산수/Critical/양자취약/Agents
- `<TierDonut />` — Recharts PieChart, by_tier
- `<AssetTypeDonut />` — by_asset_type
- `<AlgorithmFamilyBar />` — Recharts BarChart, by_algorithm_family (가로 바)
- `<QuantumVulnerabilityDonut />` — quantum_vulnerable_ratio
- `<TrendLineChart />` — Recharts LineChart, trend 배열
- `<RecentJobsTable />` — recent_jobs

**상호작용**:
- KpiCard 클릭 → 해당 필터링된 Asset Inventory로 이동
  - "Critical" 클릭 → `/snapshots/{id}/assets?tier=CRITICAL`
  - "양자취약" 클릭 → `/snapshots/{id}/assets?quantum_vulnerable=true`
- 차트 segment 클릭 → 해당 필터로 Asset Inventory 이동
- "새 스캔" 버튼 → `/scans/new`

### 9.4.2 Targets (`/targets`)

**목적**: 등록된 Target 관리.

**API**: `GET /api/targets`, `POST /api/targets`, `PATCH`, `DELETE`.

**레이아웃**:

```
┌─────────────────────────────────────────────────────────┐
│ Targets                                  [+ 신규 등록]   │
│                                          [🔍 디스커버리] │
├─────────────────────────────────────────────────────────┤
│ 필터: [host: ____] [protocol: All ▼] [agent: □]         │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Host             Port  Proto  Agent  Sens  Crit   ⋮ │ │
│ │ web.testbed.local  443  TLS   ✓     high   high  ⋮ │ │
│ │ ssh.testbed.local   22  SSH   ✓     med    high  ⋮ │ │
│ │ ...                                                 │ │
│ └─────────────────────────────────────────────────────┘ │
│ 페이지네이션: ◀ 1 2 3 ▶                                 │
└─────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<TargetTable />` — shadcn DataTable (정렬/필터/페이지네이션)
- 각 행 액션: 보기 (`/targets/{id}`), 편집 (모달), 삭제 (확인 다이얼로그)
- `<TargetCreateDialog />` — 등록 폼

**TargetCreateDialog 폼 필드**:
- 호스트 (required)
- IP (옵션, 자동 해석 안내)
- 포트 (required, 숫자)
- 프로토콜 힌트 (select: TLS/SSH/IKE/SMTP/IMAP/POP3/UNKNOWN)
- SNI (옵션)
- Transport (TCP/UDP, default TCP)
- **Agent 사용 여부** (체크박스, 기본 false)
  - 체크 시: Agent URL 입력 필드 노출 (옵션, 비우면 hostname 매핑된 등록 Agent 자동 사용)
- 운영 컨텍스트 (collapsible 섹션):
  - Sensitivity (select)
  - Lifespan (years, 숫자)
  - Criticality (select)
  - Exposure (select, 자동추정 옵션)
  - Service Role (select + 직접 입력)

검증: Zod 스키마. 동일 (host, port, transport) 등록 시 409 표시.

### 9.4.3 Target Detail (`/targets/:id`)

**API**: `GET /api/targets/{id}`, 자산 조회는 별도 (`?target_id=` 필터).

**레이아웃**:

```
┌─────────────────────────────────────────────────────────┐
│ ← Targets                                                │
│ web.testbed.local:443 (TLS)                  [편집] [삭제]│
├─────────────────────────────────────────────────────────┤
│ 운영 컨텍스트                                            │
│   Sensitivity: high  Lifespan: 10y  Criticality: high   │
│   Exposure: internal_network  Role: web-frontend        │
├─────────────────────────────────────────────────────────┤
│ 발견 자산 (최신 스냅샷 기준)                              │
│ - 14 algorithms, 3 certs, 2 keys, 1 protocol           │
│ [전체 자산 보기 →]                                       │
├─────────────────────────────────────────────────────────┤
│ 매핑된 Agent                                             │
│ - web.testbed.local (last_seen 2분 전, capabilities: 4) │
│ [Agent 상세 →]                                           │
├─────────────────────────────────────────────────────────┤
│ 최근 Scan Job 이력 (이 Target 포함)                      │
│ - #123 ✅ ... | #120 ✅ ... | #115 ❌ TIMEOUT           │
└─────────────────────────────────────────────────────────┘
```

### 9.4.4 Discoveries (`/discoveries`)

**목적**: CIDR 디스커버리 작업 관리.

**API**: `GET /api/discoveries`, `POST /api/discoveries`.

**레이아웃**: 작업 목록 테이블 (CIDR, 상태, 발견 endpoint 수, 시작/완료 시각).

### 9.4.5 Discovery Start (`/discoveries/new`)

**API**: `POST /api/discoveries`.

**레이아웃**:

```
┌─────────────────────────────────────────────────────────┐
│ 신규 디스커버리                                          │
├─────────────────────────────────────────────────────────┤
│ CIDR: [172.20.0.0/24___________]                        │
│                                                         │
│ ☑ 기본 포트 사용 (테스트베드 표준)                       │
│   = 22, 443, 8883, 5432, 25, 465, 587, 993, 995, 500, 4500│
│                                                         │
│ 추가 포트: [____, ____, ____] (콤마 구분)                │
│                                                         │
│                            [취소]  [디스커버리 시작]     │
└─────────────────────────────────────────────────────────┘
```

제출 시 `POST /api/discoveries` → `job.resource.id`로 `/discoveries/{id}` 이동한다. 전역 Job 목록/카운터에서는 `job.id`를 사용한다.

### 9.4.6 Discovery Detail (`/discoveries/:id`)

**API**: `GET /api/discoveries/{id}` (폴링), `GET /api/discoveries/{id}/endpoints`, `POST /api/discoveries/{id}/promote`.

**레이아웃**:

```
┌──────────────────────────────────────────────────────────┐
│ Discovery #4 — 172.20.0.0/24                             │
│ 상태: ⏳ RUNNING (4/256 호스트 스캔)                      │
│       ✅ COMPLETED — 25 endpoints 발견                    │
├──────────────────────────────────────────────────────────┤
│ ☑ Select All  [Promote 선택된 항목 →]                    │
│ ┌────────────────────────────────────────────────────┐  │
│ │ ☑  IP            Port   Proto   Suggested Host     │  │
│ │ ☑  172.20.0.10   443    TLS     web.testbed.local  │  │
│ │ ☑  172.20.0.10   22     ?       (none)             │  │
│ │ □  172.20.0.11   443    TLS     pqc-tls.testbed... │  │
│ │ ☑  172.20.0.13   8883   MQTT    mqtt.testbed.local │  │
│ │ ...                                                │  │
│ └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Promote 다이얼로그**: 선택된 endpoint마다 Target Create와 같은 컨텍스트 폼 (sensitivity, lifespan, criticality 등). bulk 처리 가능 (모두 같은 컨텍스트 적용 옵션).

### 9.4.7 Scans (`/scans`)

**API**: `GET /api/jobs`.

**레이아웃**: 작업 목록 테이블 (#, status, targets, scanners, started, finished, duration).

상태 필터: All / Pending / Running / Completed / Failed / Cancelled.

각 행 클릭 → `/scans/{id}`.

### 9.4.8 Scan Start (`/scans/new`)

**API**: `POST /api/jobs`, `GET /api/targets`, `GET /api/meta/scanners`.

**레이아웃**: 2단계 위저드 또는 1페이지 폼.

```
┌──────────────────────────────────────────────────────────┐
│ 신규 스캔                                                 │
├──────────────────────────────────────────────────────────┤
│ 1) Targets 선택                                           │
│   [전체 선택] 또는 개별 선택                               │
│   ┌──────────────────────────────────────────────────┐  │
│   │ ☑ web.testbed.local:443 (TLS)  agent: ✓          │  │
│   │ ☑ ssh.testbed.local:22 (SSH)   agent: ✓          │  │
│   │ ☑ pqc-tls.testbed.local:443 (TLS) agent: ✗       │  │
│   │ ...                                              │  │
│   └──────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────┤
│ 2) Scanner 선택                                           │
│   ☑ Network Scanner (필수, 항상 활성)                    │
│   ─ Agent 스캐너 (Agent 탑재 호스트만 적용) ─             │
│   ☑ System CA Store                                      │
│   ☑ Package Repository Keys                              │
│   ☑ SSH User Keys                                        │
│   ☑ SSH Config Policy                                    │
│   ☐ Keystore Files                                       │
│   ☑ Application Cert Files                               │
│   ☑ Application Config Policy                            │
├──────────────────────────────────────────────────────────┤
│ 미리보기: 3 targets × 5 scanners = 최대 15 작업           │
│   - web (Network + 4 Agent) = 5                          │
│   - ssh (Network + 3 Agent applicable) = 4               │
│   - pqc-tls (Network only) = 1 (Agent 미탑재 → 자동 skip)│
│                                                          │
│                     [취소]   [스캔 시작]                  │
└──────────────────────────────────────────────────────────┘
```

**미리보기 계산**: Frontend에서 선택된 Target과 Scanner를 기반으로 실행 예상 수를 계산. agent.* 스캐너는 Target.agent_enabled 검사. 정확한 capability 매칭은 백엔드가 수행 (`SKIPPED` 처리).

### 9.4.9 Scan Job Detail (`/scans/:id`)

**API**: `GET /api/jobs/{id}` (폴링 5초), `GET /api/jobs/{id}/logs`.

**레이아웃**:

```
┌───────────────────────────────────────────────────────────┐
│ ← Scans                                                    │
│ Scan Job #123                                              │
│ 상태: ⏳ RUNNING  진행: 7/15  현재: web @ network          │
│ 시작: 10:00:00  경과: 1m 32s              [취소]          │
├───────────────────────────────────────────────────────────┤
│ Targets: web, ssh, pqc-tls                                │
│ Scanners: network, agent.cert_store, agent.ssh_config, ...│
├───────────────────────────────────────────────────────────┤
│ 실행 로그 (실시간 갱신)                                     │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ ✅ web : network (12 findings, 2.3s)                │  │
│ │ ✅ web : agent.cert_store (5 findings, 1.1s)        │  │
│ │ ⏳ web : agent.ssh_config (running)                 │  │
│ │ ⏸ ssh : network (pending)                           │  │
│ │ ⊘ pqc-tls : agent.cert_store (skipped: no agent)    │  │
│ │ ...                                                 │  │
│ └─────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│ COMPLETED 시:                                              │
│   [📄 결과 스냅샷 보기 →]                                  │
└───────────────────────────────────────────────────────────┘
```

상태가 `COMPLETED`로 전이하면 Toast로 "스캔 완료" + 자동 스냅샷 링크.

### 9.4.10 Snapshots (`/snapshots`)

**API**: `GET /api/snapshots`.

**레이아웃**: 카드 그리드 또는 테이블.

```
┌──────────────────────────────────────────────────────────┐
│ Snapshots                                                 │
│ [Diff 모드 토글: □]                                       │
├──────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│ │ #56         │ │ #55         │ │ #54         │          │
│ │ 2026-04-25  │ │ 2026-04-24  │ │ 2026-04-23  │          │
│ │ 142 assets  │ │ 138 assets  │ │ 135 assets  │          │
│ │ 8 critical  │ │ 7 critical  │ │ 6 critical  │          │
│ │ [열기]       │ │ [열기]       │ │ [열기]       │          │
│ └─────────────┘ └─────────────┘ └─────────────┘          │
│                                                          │
│ Diff 모드 활성화 시: 두 카드 체크박스 → [Diff 보기]       │
└──────────────────────────────────────────────────────────┘
```

### 9.4.11 Snapshot Detail / Asset Inventory (`/snapshots/:id`)

**목적**: CBOM 자산 탐색의 메인 페이지. 발표자료의 keycloak 예시와 유사.

**API**: `GET /api/snapshots/{id}`, `GET /api/snapshots/{id}/assets`.

**레이아웃**:

```
┌────────────────────────────────────────────────────────────────┐
│ Snapshot #56 (2026-04-25 10:05)             [📥 CBOM Export]   │
│                                              [🔀 Diff]          │
│                                              [⚖ Risk]           │
│                                              [🚀 Migration]    │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────┐  ┌──────────────────────────────────────────────┐│
│ │ 필터      │  │ 자산 (142개)                                 ││
│ │ ──────   │  │  검색: [______________]                     ││
│ │ 클래스    │  │ ┌──────────────────────────────────────────┐ ││
│ │ ☑ Crypto │  │ │Name              Type      Algo     Risk│ ││
│ │ ☑ Host   │  │ │alg-rsa-2048      algo      RSA-2048  ⛔ ││
│ │ ☑ Service│  │ │cert-leaf-web     cert      RSA-2048  ⛔ ││
│ │ ☑ Data   │  │ │proto-tls13-web   proto     X25519    🟡 ││
│ │ ──────   │  │ │svc-web-https     service   -          - ││
│ │ 위험등급  │  │ │ ...                                     │ ││
│ │ ☑ Critical│ │  │                                         │ ││
│ │ ☑ High   │  │ │                                         │ ││
│ │ ☐ Medium │  │ └──────────────────────────────────────────┘ ││
│ │ ☐ Low    │  │  페이지네이션 ◀ 1 2 3 ▶                     ││
│ │ ──────   │  │                                              ││
│ │ 양자취약  │  │                                              ││
│ │ ☑ Yes    │  │                                              ││
│ │ ☐ No     │  │                                              ││
│ │ ──────   │  │                                              ││
│ │ Target   │  │                                              ││
│ │ [Select▼]│  │                                              ││
│ └──────────┘  └──────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────────┤
│ 요약 (사이드 칩 형태)                                            │
│ [142 자산] [8 Critical] [75 양자취약] [50 algorithms] ...       │
└────────────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<AssetFilterPanel />` — 좌측 사이드바 (체크박스 + select)
- `<AssetTable />` — 메인 테이블, 행 클릭 → `/snapshots/{id}/assets/{aid}`
- `<AssetSummaryChips />` — 상단 요약 칩

**필터 상태**: URL query string에 동기화 (`?asset_class=crypto&tier=CRITICAL,HIGH`).

**테이블 컬럼**:
- Name (bom_ref or 표시명)
- Type (algorithm/certificate/key/...)
- Algorithm (cert는 키 알고리즘, protocol은 사용 알고리즘 요약)
- Source (network/agent)
- Risk Score + Tier (badge)
- Target

### 9.4.12 Asset Detail (`/snapshots/:id/assets/:aid`)

**목적**: 단일 자산의 모든 메타데이터 + 의존성 그래프 + 위험도 + 정성 분석.

**API**: `GET /api/assets/{id}`, `PATCH /api/assets/{id}/context`, `POST /api/assets/{id}/qualitative`.

**레이아웃**:

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Snapshot #56                                                   │
│ 🔐 cert-leaf-web-rsa2048-ab12cd34                                │
│ web.testbed.local (leaf certificate)                             │
│  Type: certificate  Class: crypto                                │
│  Algorithm: RSA-2048  Quantum Vulnerable: ✅                     │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────┐  ┌──────────────────────────────┐  │
│ │ Risk Score              │  │ Quantum Vulnerability         │  │
│ │     84 / 100            │  │ Algorithm: RSA-2048           │  │
│ │  Tier: 🔴 CRITICAL      │  │ Threat: Shor's algorithm      │  │
│ │                         │  │ HNDL Risk: HIGH (10y)         │  │
│ │ A=0.95 D=0.80 E=0.40    │  └──────────────────────────────┘  │
│ │ L=0.85 C=0.75           │                                    │
│ │ [factor breakdown 차트] │                                    │
│ └─────────────────────────┘                                    │
├─────────────────────────────────────────────────────────────────┤
│ Properties (테이블)                                              │
│  Subject: CN=web.testbed.local                                   │
│  Issuer: CN=Internal Intermediate CA                             │
│  Valid From: 2025-01-01                                          │
│  Valid To: 2026-01-01 (만료 임박 ⚠)                              │
│  Fingerprint (SHA-256): ab12cd34...                              │
│  Source Scanner: network                                         │
│  ...                                                             │
├─────────────────────────────────────────────────────────────────┤
│ 의존성 그래프 (React Flow)                                        │
│   [cert-intermediate] ──┐                                        │
│                         ↓                                        │
│   [cert-leaf-web] ─── embeds_key ──→ [key-rsa-2048-web-leaf]   │
│         │                                                        │
│         └─── used by ──→ [proto-tls13-web]                      │
├─────────────────────────────────────────────────────────────────┤
│ Risk Score Trend (라인 차트)                                     │
│  Snapshot #54: 80, #55: 80, #56: 84                              │
├─────────────────────────────────────────────────────────────────┤
│ 정성 분석 (LLM)                                                   │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Provider: mock (LLM 미구성)                                 │ │
│ │ "RSA-2048은 양자 컴퓨터에 의해 높은 확률로 무력화될 수 있는  │ │
│ │  알고리즘이며, 이 자산은 운영 컨텍스트상 즉각적인 PQC 전환이 │ │
│ │  권고됩니다."                                                │ │
│ │ 권장 전환: Hybrid (RSA-2048 + ML-DSA-65)                    │ │
│ │ Confidence: 0.5                                             │ │
│ │                                  [🔄 분석 재요청]            │ │
│ └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│ 컨텍스트 Override                                                │
│  Effective: critical / 10y / critical / internal / web-frontend │
│  Sources: override / target / override / target / heuristic     │
│  Override 시: [편집 →] 모달                                      │
└─────────────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<AssetHeader />` — 제목, 타입, 알고리즘, 양자취약 뱃지
- `<RiskScoreCard />` — 점수 + 인자 breakdown (작은 막대)
- `<QuantumThreatCard />` — 알고리즘별 위협 설명 (사전 정의 텍스트)
- `<PropertyTable />` — properties dict 테이블 표시
- `<DependencyGraph />` — React Flow, 자산 노드를 클릭하면 해당 Asset Detail로
- `<RiskTrendChart />` — Recharts LineChart
- `<QualitativeCard />` — LLM 정성 분석, 재요청 버튼
- `<ContextOverrideDialog />` — `effective_context`, `context_override`, `context_sources` 표시 후 PATCH `/api/assets/{id}/context`

### 9.4.13 Snapshot Diff (`/snapshots/:id/diff`)

**목적**: 두 스냅샷 간 자산 변경사항 비교 (17b).

**API**: `GET /api/snapshots/{id}/diff?other={id2}`.

**레이아웃**:

```
┌──────────────────────────────────────────────────────────────┐
│ Diff: Snapshot #55 → #56                                      │
│  Snapshot A: [#55 (2026-04-24) ▼]                             │
│  Snapshot B: [#56 (2026-04-25) ▼]                             │
├──────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                      │
│  │ +4 추가   │ │ -2 제거   │ │ ~3 변경   │  138 unchanged   │
│  │ added    │ │ removed   │ │ modified  │                  │
│  └──────────┘ └──────────┘ └──────────┘                      │
├──────────────────────────────────────────────────────────────┤
│ 탭: [추가] [제거] [변경] [전체]                               │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐│
│ │ + alg-mldsa-65            algorithm    PQC               ││
│ │ + key-mldsa-pqc-tls       key          ML-DSA-65         ││
│ │ - cert-leaf-old-rsa1024   certificate  (제거됨)          ││
│ │ ~ proto-tls13-web         protocol                       ││
│ │   alpn: "http/1.1" → "h2"                                ││
│ │   (자세히 보기)                                           ││
│ └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

**자세히 보기** 클릭 시 변경된 필드의 before/after JSON을 인라인 표시.

### 9.4.14 Risk Assessment (`/snapshots/:id/risk`)

**목적**: Top-N 위험 자산 + 가중치 조정 + 재계산 트리거.

**API**: `GET /api/snapshots/{id}/risks/top`, `GET /api/snapshots/{id}/risks`, `POST /api/snapshots/{id}/recompute`, `GET /api/risk/weights`.

**레이아웃**:

```
┌────────────────────────────────────────────────────────────┐
│ Risk Assessment — Snapshot #56                              │
├────────────────────────────────────────────────────────────┤
│ 가중치 조정 (현재 default)                                   │
│   wA (Algorithm)    [────●────]  1.0                       │
│   wD (Data)         [───●─────]  0.8                       │
│   wE (Exposure)     [────●────]  1.0                       │
│   wL (Lifespan)     [─────●───]  1.5                       │
│   wC (Criticality)  [────●────]  1.0                       │
│   ☐ 이 가중치를 default로 저장                              │
│                                  [재계산 실행]              │
├────────────────────────────────────────────────────────────┤
│ Top 10 위험 자산                                            │
│ ┌────────────────────────────────────────────────────────┐│
│ │ Rank Asset                              Score Tier   A│ │
│ │  1   cert-leaf-db-rsa1024               92    🔴 ...│ │
│ │  2   alg-rsa-2048-tls-mail              88    🔴 ...│ │
│ │  3   cert-leaf-web-rsa2048              84    🔴 ...│ │
│ │  ...                                                 │ │
│ └────────────────────────────────────────────────────────┘│
├────────────────────────────────────────────────────────────┤
│ 전체 분포 (히스토그램)                                       │
│ [Score 0~100 X축, 자산 수 Y축, Tier별 색상]                 │
└────────────────────────────────────────────────────────────┘
```

**상호작용**:
- 슬라이더 조정 → 즉시 미리보기 (옵션, 클라이언트에서 단순 곱셈으로 추정 표시)
- "재계산 실행" → POST recompute → Job 폴링 → 완료 시 페이지 새로고침
- 자산 행 클릭 → Asset Detail

### 9.4.15 Migration Plan (`/snapshots/:id/migration`)

**API**: `GET /api/snapshots/{id}/migration-plan`, `GET /api/snapshots/{id}/migration-plan/impact`.

**레이아웃**:

```
┌──────────────────────────────────────────────────────────────┐
│ Migration Plan — Snapshot #56                                 │
├──────────────────────────────────────────────────────────────┤
│ 필터: tier=[All ▼] type=[All ▼] target=[All ▼]                │
├──────────────────────────────────────────────────────────────┤
│ 전환 권고 (위험도 순)                                          │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ #1  cert-leaf-db-rsa1024              🔴 92               ││
│ │     현재: RSA-1024                                         ││
│ │     권고: ML-DSA-65 (replace)                             ││
│ │     사유: 약한 키, 즉각 교체 필요                          ││
│ │     [상세] [Plan에 추가]                                   ││
│ │ ─────────────────────────────────────────────────         ││
│ │ #2  cert-leaf-mail-rsa2048             🔴 88               ││
│ │     현재: RSA-2048                                         ││
│ │     권고: Hybrid (RSA-2048 + ML-DSA-65)                    ││
│ │     사유: Lifespan 10y, 호환성 유지 필요                   ││
│ │     [상세] [Plan에 추가]                                   ││
│ │ ...                                                        ││
│ └──────────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────────┤
│ 전환 시뮬레이션 (선택 자산 합산)                                │
│  - 영향 받는 서비스: 4 (web, mail, db, ipsec)                  │
│  - 예상 작업량: 12 인증서 재발급, 3 설정 변경                   │
│  - 추정 다운타임: 서비스당 5분 미만                              │
│  [📥 Migration Plan 보고서 다운로드 (PDF/MD)]                  │
└──────────────────────────────────────────────────────────────┘
```

**참고**: 본 페이지의 권고 알고리즘 결정 규칙은 `11-migration-plan.md` 참고. 실제 전환 실행은 v2.

### 9.4.16 CBOM Export (`/cbom`)

**API**: `GET /api/snapshots`, `GET /api/snapshots/{id}/export`.

**레이아웃**:

```
┌──────────────────────────────────────────────────────────────┐
│ CBOM Export                                                   │
├──────────────────────────────────────────────────────────────┤
│ Snapshot 선택: [#56 (2026-04-25 10:05) ▼]                     │
│                                                              │
│ 옵션:                                                         │
│   ☑ Pretty Print (들여쓰기)                                   │
│   ☐ 필터 적용 (선택 시 필터 옵션 노출, v2)                     │
│                                                              │
│ 미리보기 (처음 200줄):                                         │
│ ┌──────────────────────────────────────────────────────────┐│
│ │ {                                                        ││
│ │   "bomFormat": "CycloneDX",                              ││
│ │   "specVersion": "1.6",                                  ││
│ │   ...                                                    ││
│ │ }                                                        ││
│ └──────────────────────────────────────────────────────────┘│
│                                                              │
│                              [📥 다운로드 (cbom-56.json)]    │
└──────────────────────────────────────────────────────────────┘
```

### 9.4.17 Agents (`/agents`)

**API**: `GET /api/agents`, `DELETE /api/agents/{id}`.

**레이아웃**: 테이블 (Hostname, URL, Capabilities, Last Seen, Status, 액션).

상태 배지: Active (녹) / Stale (황) / Inactive (회). `active=false`와 stale 조건이 동시에 참이면 Inactive를 우선 표시한다 (`Inactive > Stale > Active`).

각 행 액션: 비활성화 (DELETE).

신규 등록 UI는 없음 (Agent가 자기 등록함).

### 9.4.18 Settings (`/settings`)

**API**: `GET/PUT /api/risk/weights`, 클라이언트 설정 (다크모드 등 localStorage).

**레이아웃**:

```
┌──────────────────────────────────────────────────────────┐
│ 설정                                                      │
├──────────────────────────────────────────────────────────┤
│ Default 가중치                                            │
│   wA: [1.0]  wD: [1.0]  wE: [1.0]  wL: [1.0]  wC: [1.0] │
│                                          [저장]           │
├──────────────────────────────────────────────────────────┤
│ 외관                                                      │
│   ○ 라이트  ○ 다크  ● 시스템 (auto)                       │
├──────────────────────────────────────────────────────────┤
│ 시스템 정보                                                │
│   Backend: http://localhost:8000  ✅ 연결됨                │
│   Bootstrap Token: **** (마스킹, 변경은 docker env로)     │
└──────────────────────────────────────────────────────────┘
```

## 9.5 컴포넌트 라이브러리 정리

| 카테고리 | 컴포넌트 | 출처 |
|---|---|---|
| Layout | AppHeader, AppSidebar, AppShell | 자작 (shadcn 기반) |
| Form | TargetForm, ContextEditor, WeightSlider | 자작 (RHF + Zod) |
| Table | DataTable, AssetTable, JobTable, TargetTable | shadcn DataTable 확장 |
| Chart | ChartContainer, DonutChartFrame, BarChartFrame, LineChartFrame | Recharts primitive wrapper. TierDonut 등 화면별 조합은 feature 내부 |
| Graph | GraphCanvas, GraphNodeShell, GraphToolbar | React Flow primitive wrapper. DependencyGraph 조합은 feature 내부 |
| Card | KpiCard, RiskScoreCard, QuantumThreatCard, QualitativeCard | 자작 (shadcn Card) |
| Dialog | TargetCreateDialog, ContextOverrideDialog, PromoteDialog | shadcn Dialog |
| Misc | RiskTierBadge, AlgorithmBadge, StatusPill, JobProgressBar | 자작 |

## 9.6 데이터 페칭 패턴

### 9.6.1 TanStack Query 키 컨벤션

```typescript
['targets']                              // GET /api/targets
['targets', { host: 'web', limit: 20 }]  // 필터 포함
['target', targetId]                     // GET /api/targets/{id}
['snapshots']
['snapshot', snapshotId]
['snapshot', snapshotId, 'assets', filters]
['asset', assetId]
['job', jobId]                           // 폴링용
['discovery', discoveryId]
['discovery', discoveryId, 'endpoints']
['agents']
['dashboard', snapshotId]
['risk-weights']
['snapshot', snapshotId, 'risks', { top: 10 }]
['snapshot', snapshotId, 'diff', otherSnapshotId]
['snapshot', snapshotId, 'migration-plan']
['meta', 'protocols' | 'scanners' | 'algorithm-risk-table']
```

### 9.6.2 폴링 정책

| 자원 | 주기 | 조건 |
|---|---|---|
| `['job', id]` | 5초 | status가 PENDING/RUNNING인 동안만 |
| `['discovery', id]` | 5초 | status가 PENDING/RUNNING인 동안만 |
| 활성 Job 카운터 | 5초 | 항상 (Header 표시) |
| `['health']` | 1분 | 항상 (Header 표시) |
| `['agents']` | 1분 | Agents 페이지 활성 시 |
| 그 외 | 폴링 없음 | 사용자 액션으로 invalidate |

### 9.6.3 Mutation 후 invalidate 규칙

| Mutation | Invalidate |
|---|---|
| Target 생성/수정/삭제 | `['targets']`, `['target', id]` |
| Discovery 시작 | `['discovery', id]` |
| Promote endpoints | `['targets']`, `['discovery', id]` |
| Scan Job 시작 | `['job', id]` 폴링 시작 |
| Recompute 트리거 | `['job', id]` 폴링 → 완료 후 `['snapshot', id, 'risks*']` |
| Context Override | `['asset', id]`, `['snapshot', id, 'assets']`, `['snapshot', id, 'risks*']` (재계산 완료 후) |
| Qualitative 요청 | `['asset', id]` |
| Agent 비활성화 | `['agents']` |

## 9.7 에러/로딩 표시 표준

| 상황 | UI |
|---|---|
| 페이지 첫 로딩 | shadcn Skeleton |
| 부분 로딩 (테이블 추가 페이지 등) | 인라인 spinner |
| API 에러 (4xx) | 페이지 내 인라인 에러 (`<ErrorBanner>`) + 재시도 버튼 |
| API 에러 (5xx) | Toast (sonner) + 인라인 에러 |
| 폼 검증 에러 | 필드 옆 빨간 텍스트 |
| 네트워크 단절 | 글로벌 배너 ("백엔드와 연결 끊김. 재연결 시도 중...") |
| 빈 상태 | `<EmptyState>` 컴포넌트 (아이콘 + 설명 + CTA 버튼) |

## 9.8 다크모드 색상 토큰

shadcn 기본 토큰 + 위험도 색상 추가:

| 토큰 | Light | Dark |
|---|---|---|
| `--risk-critical` | `#dc2626` | `#ef4444` |
| `--risk-high` | `#ea580c` | `#f97316` |
| `--risk-medium` | `#ca8a04` | `#eab308` |
| `--risk-low` | `#16a34a` | `#22c55e` |
| `--quantum-vulnerable` | `#dc2626` | `#ef4444` |
| `--quantum-safe` | `#16a34a` | `#22c55e` |
| `--algorithm-pqc` | `#7c3aed` | `#a78bfa` |

## 9.9 접근성

- 모든 색상 표시는 텍스트/아이콘과 병행 (색맹 대응)
- shadcn 기본 키보드 네비게이션 유지
- 차트는 aria-label과 데이터 테이블 fallback 제공
- 다이얼로그는 ESC 닫기, focus trap

## 9.10 디렉터리 구조 (참고)

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── app/
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                        # shadcn 생성물
│   │   ├── layout/
│   │   ├── charts/
│   │   ├── graph/
│   │   └── common/
│   ├── api/
│   │   ├── client.ts                  # fetch wrapper
│   │   └── generated/                 # OpenAPI 생성 타입
│   ├── features/
│   │   ├── dashboard/
│   │   ├── targets/
│   │   ├── discoveries/
│   │   ├── jobs/
│   │   ├── snapshots/
│   │   ├── assets/
│   │   ├── risk/
│   │   ├── migration/
│   │   ├── agents/
│   │   ├── cbom/
│   │   └── settings/
│   ├── pages/                         # route entry components
│   ├── lib/
│   │   ├── utils.ts
│   │   └── format.ts                  # 점수, 시간 포맷터
│   ├── stores/                        # Zustand
│   └── styles/
└── package.json
```
