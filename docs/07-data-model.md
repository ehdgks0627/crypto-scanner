# 07. 데이터 모델 (Django Models)

## 7.1 개요

본 시스템의 영구 저장소는 PostgreSQL 16이며, ORM은 Django ORM을 사용한다. 큰 CBOM JSON 원본은 파일 시스템(`/var/cbom/`)에 저장하고 DB에는 메타데이터와 경로만 보관한다.

## 7.2 ER 다이어그램

```mermaid
erDiagram
    AsyncJob ||--o| ScanJob : tracks
    AsyncJob ||--o| Discovery : tracks
    Target ||--o{ Asset : discovers
    Target ||--o{ ScanJob : "scanned in"
    ScanJob ||--|| CbomSnapshot : produces
    ScanJob ||--o{ ScanRunLog : has
    CbomSnapshot ||--o{ Asset : contains
    CbomSnapshot ||--o{ AssetEdge : contains
    Asset ||--o{ AssetEdge : "from"
    Asset ||--o{ AssetEdge : "to"
    Asset ||--o| AssetContextOverride : has
    Asset ||--o{ RiskScore : "evaluated in"
    Asset ||--o| QualitativeAssessment : has
    Agent ||--o{ AgentHeartbeat : reports
    Agent }o--|| Target : "registered for"
    Discovery ||--o{ DiscoveredEndpoint : finds
    DiscoveredEndpoint }o--|| Target : "promoted to"

    Target {
        int id PK
        string host
        string ip nullable
        int port
        string protocol_hint
        string sni nullable
        string transport
        bool agent_enabled
        string agent_url nullable
        string sensitivity nullable
        int lifespan_years nullable
        string criticality nullable
        string exposure nullable
        string service_role nullable
        datetime created_at
    }

    ScanJob {
        int id PK
        int async_job_id FK
        string status
        json scanner_selection
        json target_ids
        datetime started_at nullable
        datetime finished_at nullable
        string error nullable
    }

    Agent {
        uuid id PK
        string hostname
        string agent_url
        string agent_token_hash
        json capabilities
        string os_distribution
        datetime registered_at
        datetime token_rotated_at
        datetime last_seen
        bool active
    }

    CbomSnapshot {
        int id PK
        int scan_job_id FK
        string serial_number
        string file_path
        int asset_count
        json validation_errors
        datetime created_at
    }

    Asset {
        int id PK
        int snapshot_id FK
        int target_id FK nullable
        string bom_ref
        string asset_class
        string asset_type
        string name
        json crypto_properties
        json properties
        string natural_key
        datetime discovered_at
    }

    AssetEdge {
        int id PK
        int snapshot_id FK
        int from_asset_id FK
        int to_asset_id FK
        string semantic
    }

    AssetContextOverride {
        int id PK
        int asset_id FK
        string sensitivity nullable
        int lifespan_years nullable
        string criticality nullable
        string exposure nullable
        string service_role nullable
        datetime updated_at
    }

    RiskScore {
        int id PK
        int asset_id FK
        int snapshot_id FK
        float factor_a
        float factor_d
        float factor_e
        float factor_l
        float factor_c
        float raw
        int score
        string tier
        json weights
        datetime computed_at
    }

    QualitativeAssessment {
        int id PK
        int asset_id FK
        string provider
        text summary
        json threat_scenarios
        text migration_recommendation
        float confidence
        datetime generated_at
    }

    Discovery {
        int id PK
        int async_job_id FK
        string cidr
        json port_list
        string status
        datetime created_at
        datetime started_at nullable
        datetime finished_at nullable
    }

    DiscoveredEndpoint {
        int id PK
        int discovery_id FK
        string ip
        int port
        string detected_protocol
        json banner_metadata
        bool promoted
        int target_id FK nullable
    }

    AgentHeartbeat {
        int id PK
        uuid agent_id FK
        datetime received_at
        json status_payload
    }

    AsyncJob {
        int id PK
        string kind
        int resource_id nullable
        string status
        json request_payload
        json progress nullable
        json result nullable
        string celery_task_id nullable
        datetime queued_at
        datetime started_at nullable
        datetime cancel_requested_at nullable
        datetime finished_at nullable
        string error nullable
        string created_by
    }

    ScanRunLog {
        int id PK
        int scan_job_id FK
        int target_id FK
        string scanner_kind
        string status
        text error nullable
        datetime started_at
        datetime finished_at nullable
    }
```

## 7.3 모델 명세

각 모델은 Django ORM 기준으로 기술한다. 본 문서는 SQL DDL이 아닌 모델 단위 명세이며, 정확한 마이그레이션은 구현 단계에서 생성된다.

### 7.3.1 Target

스캔 대상. 사용자가 명시적으로 등록하거나, Discovery 결과에서 promote된다.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `host` | CharField(253) | not null | 호스트네임. FQDN 또는 IP 문자열 |
| `ip` | GenericIPAddressField | null 가능 | 해석된 IP. null이면 매 스캔 시 해석 |
| `port` | IntegerField | not null | 포트 번호 |
| `protocol_hint` | CharField(20) | not null | `TLS`/`SSH`/`IKE`/`SMTP`/`IMAP`/`POP3`/`UNKNOWN` |
| `sni` | CharField(253) | null 가능 | SNI override (25b). null이면 host 사용 |
| `transport` | CharField(3) | not null, default `TCP` | `TCP`/`UDP` |
| `agent_enabled` | BooleanField | default false | Agent 사용 여부 |
| `agent_url` | URLField | null 가능 | Agent 직접 URL (등록된 Agent와 별개로 override 시) |
| `sensitivity` | CharField(10) | null 가능 | `low/medium/high/critical` |
| `lifespan_years` | IntegerField | null 가능 | 데이터 보호 기간 |
| `criticality` | CharField(10) | null 가능 | `low/medium/high/critical` |
| `exposure` | CharField(20) | null 가능 | `public_internet`/`dmz`/`internal_network`/`air_gapped` |
| `service_role` | CharField(50) | null 가능 | `web-frontend`/`database`/`auth`/`pki`/`mail`/`vpn`/... |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**제약**: `unique_together = (host, port, transport)` — 동일 호스트:포트:전송 조합은 1개 Target만.

**메서드**:
- `resolve_ip()`: dnsmasq 등으로 IP 해석. 결과 캐시 (in-memory, 60s TTL)
- `effective_sni()`: `sni or host`
- `effective_context()`: 컨텍스트 인자 5종 반환. null인 항목은 휴리스틱 추정으로 채움

### 7.3.2 AsyncJob

API-visible 비동기 작업의 공통 상태. `/api/jobs/{id}`는 이 모델을 기준으로 조회한다.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | API-visible Job ID. `scan_job`/`discovery`/`recompute` 전체에서 고유 |
| `kind` | CharField(20) | not null | `scan_job`/`discovery`/`recompute` |
| `resource_id` | BigIntegerField | null 가능 | `scan_job`이면 `ScanJob.id`, `discovery`면 `Discovery.id`. `recompute`는 별도 도메인 테이블 없이 이 `AsyncJob.id`를 사용 |
| `status` | CharField(20) | not null | `PENDING`/`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED` |
| `request_payload` | JSONField | not null, default `{}` | 생성 요청 스냅샷. Recompute의 weights, persist 옵션 등 |
| `progress` | JSONField | null 가능, default null | 폴링 진행률. `PENDING`이면 null, `RUNNING`이면 `completed`, `total`, `current_target`, `current_scanner` 등 |
| `result` | JSONField | null 가능 | 완료 후 산출물. 예: `{"snapshot_id": 56}` 또는 `{"snapshot_id": 56, "updated_scores_count": 142}` |
| `celery_task_id` | CharField(255) | null 가능 | Celery/RQ 같은 worker task id |
| `queued_at` | DateTimeField | auto_now_add | |
| `started_at` | DateTimeField | null 가능 | |
| `cancel_requested_at` | DateTimeField | null 가능 | 사용자 취소 요청 시각. Worker가 확인한 뒤 `CANCELLED`로 전이 |
| `finished_at` | DateTimeField | null 가능 | |
| `error` | TextField | null 가능 | 실패 메시지 |
| `created_by` | CharField(50) | default `"user"` | 싱글 유저이므로 고정값 |

**관계 규칙**:
- `scan_job`: `ScanJob.async_job`과 1:1, `resource_id = ScanJob.id`
- `discovery`: `Discovery.async_job`과 1:1, `resource_id = Discovery.id`
- `recompute`: 가중치 재계산은 별도 도메인 테이블을 만들지 않고 `AsyncJob.request_payload`에 요청값을 저장하며, `resource_id = AsyncJob.id`

**상태 전이**:
```
PENDING → RUNNING → COMPLETED
                  ↘ FAILED
PENDING → CANCELLED (사용자 취소)
RUNNING → CANCELLED (사용자 취소)
```

**취소 정책**:
- `scan_job`: `PENDING`, `RUNNING` 취소 가능. `RUNNING`이면 `cancel_requested_at`을 저장하고 Worker가 확인한 뒤 `CANCELLED`로 마감한다. 취소된 scan은 Snapshot을 만들지 않는다.
- `discovery`: `PENDING`, `RUNNING` 취소 가능. 이미 저장된 `DiscoveredEndpoint`는 보존하지만 Discovery 상태가 `CANCELLED`이므로 partial 결과로 취급한다.
- `recompute`: `PENDING`만 취소 가능. `RUNNING` 이후에는 기존 `RiskScore`를 부분 갱신할 수 있으므로 취소 요청은 `409 job_not_cancellable`로 거절한다.
- `COMPLETED`/`FAILED`/`CANCELLED` 작업에 대한 취소 요청은 `409`를 반환한다.

### 7.3.3 ScanJob

1회의 스캔 작업.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `async_job` | OneToOneField(AsyncJob) | not null, on_delete=CASCADE | API-visible Job 상태 |
| `status` | CharField(20) | not null | `PENDING`/`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED` |
| `scanner_selection` | JSONField | not null | 사용자가 선택한 스캐너 종류. `["network", "agent.cert_store", "agent.ssh_config"]` 등 |
| `target_ids` | JSONField | not null | `[1, 2, 3]` 형태. 스냅샷 시점의 대상 Target ID 배열 |
| `started_at` | DateTimeField | null 가능 | |
| `finished_at` | DateTimeField | null 가능 | |
| `error` | TextField | null 가능 | Job 전체 실패 시 메시지 |
| `created_at` | DateTimeField | auto_now_add | |
| `created_by` | CharField(50) | default `"user"` | 싱글 유저이므로 고정값 |

**제약**: `target_ids`는 빈 배열 불가, `scanner_selection`은 빈 배열 불가.

**상태 전이**:
```
PENDING → RUNNING → COMPLETED
                  ↘ FAILED
PENDING → CANCELLED (사용자 취소)
RUNNING → CANCELLED (사용자 취소)
```

`status`, `started_at`, `finished_at`, `error`는 `AsyncJob`과 같은 값을 유지한다. 구현은 `AsyncJob`을 API 폴링의 기준으로 삼고, `ScanJob`의 동일 필드는 스캔 도메인 조회 최적화를 위한 denormalized 필드로 취급한다.

### 7.3.4 ScanRunLog

ScanJob 내 Target × Scanner 단위 실행 로그.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `scan_job` | ForeignKey(ScanJob) | not null, on_delete=CASCADE | |
| `target` | ForeignKey(Target) | not null, on_delete=PROTECT | |
| `scanner_kind` | CharField(50) | not null | `network`/`agent.cert_store`/... |
| `status` | CharField(20) | not null | `SUCCESS`/`PARTIAL`/`TIMEOUT`/`UNREACHABLE`/`ERROR`/`SKIPPED` |
| `error` | TextField | null 가능 | |
| `findings_count` | IntegerField | default 0 | 이 실행에서 발견된 자산 수 |
| `started_at` | DateTimeField | not null | |
| `finished_at` | DateTimeField | null 가능 | |

**인덱스**: `(scan_job, target)`, `(scan_job, status)`.

### 7.3.5 Agent

테스트베드 호스트에 배포된 Agent (4.5).

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | UUIDField | PK | 등록 시 백엔드 발급 |
| `hostname` | CharField(253) | not null, unique | Target 매핑 키 |
| `agent_url` | URLField | not null | Worker가 호출할 URL |
| `agent_token_hash` | CharField(128) | not null | Bearer 토큰의 해시 (원문 미저장) |
| `capabilities` | JSONField | not null | `["cert_store", "ssh_config", ...]` |
| `os_distribution` | CharField(100) | null 가능 | `alpine:3.20` 등 |
| `registered_at` | DateTimeField | auto_now_add | |
| `token_rotated_at` | DateTimeField | not null | Agent token 최초 발급 또는 재발급 시각 |
| `last_seen` | DateTimeField | not null | heartbeat마다 갱신 |
| `active` | BooleanField | default true | 명시적 비활성화 시 false |

**stale 판정**: `last_seen < now() - 5min`이면 Worker는 Agent를 호출하지 않음 (4.8.1).

**재등록 정책**: `POST /api/agents/register`는 bootstrap token이 유효하면 `hostname` 기준 upsert로 동작한다. 기존 hostname이면 `agent_url`, `capabilities`, `os_distribution`, `active=true`를 갱신하고 새 Agent token을 발급해 `agent_token_hash`와 `token_rotated_at`을 교체한다. Raw token은 등록 응답에서만 1회 노출하고 DB에는 저장하지 않는다.

### 7.3.6 AgentHeartbeat

Agent의 주기 상태 보고 (옵션, 운영 가시성).

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `agent` | ForeignKey(Agent) | not null, on_delete=CASCADE | |
| `received_at` | DateTimeField | auto_now_add | |
| `status_payload` | JSONField | not null | uptime, version 등 |

**보존 정책**: 최근 100건만 유지 (Agent당). 초과분은 trigger 또는 cron으로 정리.

### 7.3.7 CbomSnapshot

1 Scan Job = 1 Snapshot.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `scan_job` | OneToOneField(ScanJob) | not null, on_delete=PROTECT | |
| `serial_number` | CharField(50) | not null, unique | CBOM `urn:uuid:...` |
| `file_path` | CharField(500) | not null | `/var/cbom/123.json` 같은 경로 |
| `asset_count` | IntegerField | default 0 | |
| `validation_errors` | JSONField | default `[]` | 5.10 검증 실패 항목 |
| `created_at` | DateTimeField | auto_now_add | |

### 7.3.8 Asset

스냅샷의 단일 자산. CBOM의 component 1개에 1:1 매핑.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `snapshot` | ForeignKey(CbomSnapshot) | not null, on_delete=CASCADE | |
| `target` | ForeignKey(Target) | null 가능, on_delete=SET_NULL | 이 자산이 발견된 출처 |
| `bom_ref` | CharField(200) | not null | CBOM 내 참조 키 |
| `asset_class` | CharField(20) | not null | `crypto`/`host`/`service`/`data` |
| `asset_type` | CharField(50) | not null | `algorithm`/`certificate`/`key`/`protocol`/`keystore`/`device`/`service`/`data` |
| `name` | CharField(500) | not null | 표시용 이름 |
| `crypto_properties` | JSONField | not null, default `{}` | CBOM `cryptoProperties` 객체 그대로 |
| `properties` | JSONField | not null, default `{}` | `internal:*`, `risk:*` 등 평탄화된 키-값 dict |
| `natural_key` | CharField(200) | not null | 자연 키 (5.9.2). 스냅샷 간 동일성 판정용 |
| `discovered_at` | DateTimeField | not null | |

**인덱스**:
- `(snapshot, asset_type)`
- `(snapshot, target)`
- `(natural_key)` — Diff 시 빠른 매칭용
- `(bom_ref, snapshot)` — unique

**제약**: `(snapshot, bom_ref)` unique.

### 7.3.9 AssetContextOverride

자산 단위 운영 컨텍스트 override. Target에서 상속된 값과 다르게 평가해야 할 때 생성된다.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `asset` | OneToOneField(Asset) | not null, on_delete=CASCADE | override 대상 자산 |
| `sensitivity` | CharField(10) | null 가능 | `low/medium/high/critical`; null이면 Target/휴리스틱 상속 |
| `lifespan_years` | IntegerField | null 가능 | null이면 Target/휴리스틱 상속 |
| `criticality` | CharField(10) | null 가능 | `low/medium/high/critical`; null이면 Target/휴리스틱 상속 |
| `exposure` | CharField(20) | null 가능 | `public_internet`/`dmz`/`internal_network`/`air_gapped`; null이면 Target/휴리스틱 상속 |
| `service_role` | CharField(50) | null 가능 | null이면 Target/휴리스틱 상속 |
| `created_at` | DateTimeField | auto_now_add | |
| `updated_at` | DateTimeField | auto_now | |

**PATCH 의미**:
- 필드 생략: 기존 override 값 유지
- 필드 값 지정: 해당 override 저장
- 필드 값 `null`: 해당 override 제거 후 상속값 사용
- 모든 override 필드가 null이 되면 레코드는 삭제 가능

### 7.3.10 AssetEdge

자산 간 의존 관계 (5.6).

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `snapshot` | ForeignKey(CbomSnapshot) | not null, on_delete=CASCADE | |
| `from_asset` | ForeignKey(Asset, related_name='edges_out') | not null, on_delete=CASCADE | |
| `to_asset` | ForeignKey(Asset, related_name='edges_in') | not null, on_delete=CASCADE | |
| `semantic` | CharField(30) | not null | `embeds_key`/`signed_by`/`uses_algorithm`/`uses_cert`/`hosts`/`protects_data`/`chains_to`/... |

**제약**: `(snapshot, from_asset, to_asset, semantic)` unique.

### 7.3.11 RiskScore

자산별 위험도 평가 결과.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `asset` | ForeignKey(Asset) | not null, on_delete=CASCADE | |
| `snapshot` | ForeignKey(CbomSnapshot) | not null, on_delete=CASCADE | |
| `factor_a` | FloatField | not null | 0.0~1.0 |
| `factor_d` | FloatField | not null | |
| `factor_e` | FloatField | not null | |
| `factor_l` | FloatField | not null | |
| `factor_c` | FloatField | not null | |
| `raw` | FloatField | not null | A×D×E×L×C 결과 (가중치 적용 후) |
| `score` | IntegerField | not null | 0~100 |
| `tier` | CharField(10) | not null | `CRITICAL`/`HIGH`/`MEDIUM`/`LOW` |
| `weights` | JSONField | not null | 평가 시점의 가중치 스냅샷 |
| `computed_at` | DateTimeField | auto_now | |

**인덱스**: `(snapshot, score DESC)` — Top-N 조회용 (6.9).

**제약**: `(asset, snapshot)` unique.

### 7.3.12 QualitativeAssessment

자산별 LLM 정성 분석 (6.6).

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `asset` | OneToOneField(Asset) | not null, on_delete=CASCADE | |
| `provider` | CharField(50) | not null | `mock`/`openai-gpt-4`/... |
| `summary` | TextField | not null | |
| `threat_scenarios` | JSONField | not null, default `[]` | |
| `migration_recommendation` | TextField | not null | |
| `confidence` | FloatField | not null | 0.0~1.0 |
| `generated_at` | DateTimeField | auto_now_add | |

> 자산 단위로 1개만. 재요청 시 같은 레코드 갱신.

### 7.3.13 Discovery

CIDR 디스커버리 작업 (16, 2c).

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `async_job` | OneToOneField(AsyncJob) | not null, on_delete=CASCADE | API-visible Job 상태 |
| `cidr` | CharField(50) | not null | 입력 CIDR |
| `port_list` | JSONField | not null | 사전 정의 포트 + 사용자 추가 |
| `status` | CharField(20) | not null | `PENDING`/`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED` |
| `created_at` | DateTimeField | auto_now_add | Discovery 요청 생성 시각 |
| `started_at` | DateTimeField | null 가능 | Worker가 실제 Discovery 실행을 시작한 시각. `PENDING`이면 null |
| `finished_at` | DateTimeField | null 가능 | |
| `error` | TextField | null 가능 | |

`status`, `started_at`, `finished_at`, `error`는 `AsyncJob`과 같은 값을 유지한다. `created_at`은 Discovery 도메인 레코드 생성 시각이며 `AsyncJob.queued_at`과 같은 의미다. 구현은 `AsyncJob`을 API 폴링의 기준으로 삼고, `Discovery`의 동일 필드는 Discovery 화면 조회 최적화를 위한 denormalized 필드로 취급한다.

### 7.3.14 DiscoveredEndpoint

Discovery로 발견된 endpoint.

| 필드 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BigAutoField | PK | |
| `discovery` | ForeignKey(Discovery) | not null, on_delete=CASCADE | |
| `ip` | GenericIPAddressField | not null | |
| `port` | IntegerField | not null | |
| `detected_protocol` | CharField(20) | null 가능 | banner/probe로 추정 |
| `banner_metadata` | JSONField | not null, default `{}` | TLS cert SAN, SSH 버전 문자열 등 |
| `promoted` | BooleanField | default false | Target으로 등록되었는지 |
| `target` | ForeignKey(Target) | null 가능, on_delete=SET_NULL | promote 시 연결 |

**제약**: `(discovery, ip, port)` unique.

## 7.4 인덱스 전략 요약

| 쿼리 패턴 | 인덱스 |
|---|---|
| Asset Inventory 페이지 (snapshot 필터, type 필터) | `Asset(snapshot, asset_type)` |
| Risk Top-N | `RiskScore(snapshot, score DESC)` |
| CBOM Diff 매칭 | `Asset(natural_key)` |
| Agent 매핑 | `Agent(hostname)` unique |
| Discovery 결과 조회 | `DiscoveredEndpoint(discovery, promoted)` |

## 7.5 데이터 보존 정책

| 데이터 | 정책 |
|---|---|
| ScanJob, CbomSnapshot, Asset, RiskScore | 무제한 (D-08, 사용자 수동 삭제) |
| ScanRunLog | Snapshot 삭제 시 cascade |
| AgentHeartbeat | Agent당 최근 100건 |
| Discovery, DiscoveredEndpoint | 30일 후 자동 정리 (cron) |
| QualitativeAssessment | Asset 삭제 시 cascade |

## 7.6 트랜잭션 경계

API mutation이 비동기 Job enqueue를 동반하면 Worker/Redis preflight를 먼저 수행한다. preflight 또는 enqueue 예약 단계에서 실패하면 503을 반환하고 domain row와 `AsyncJob`은 남기지 않는다. DB 변경, `AsyncJob` 생성, enqueue 예약은 1개 DB 트랜잭션으로 묶고 실제 Redis publish는 `transaction.on_commit`에서 실행한다. commit 이후 publish 실패는 해당 `AsyncJob`을 `FAILED`로 마감하고 운영 알림 대상이며, API 503 계약 테스트는 commit 전 실패 경로를 검증한다.

| 작업 | 트랜잭션 |
|---|---|
| Scan Job 생성 + AsyncJob + enqueue 예약 | Worker/Redis preflight 후 1개 트랜잭션. preflight/enqueue 예약 실패 시 503, `ScanJob`/`AsyncJob` 생성 없음 |
| Discovery 생성 + AsyncJob + enqueue 예약 | Worker/Redis preflight 후 1개 트랜잭션. 실패 시 `Discovery`/`AsyncJob` 생성 없음 |
| Snapshot 생성 + Asset bulk insert + Edge bulk insert + 파일 저장 | 1개 트랜잭션. 파일 저장은 트랜잭션 commit 후. 트랜잭션 실패 시 임시 파일 삭제 |
| RiskScore 계산 | 자산 단위 별개 트랜잭션. 일부 실패해도 다른 자산은 평가 완료 |
| Target 컨텍스트 수정 + recompute AsyncJob + enqueue 예약 | 1개 트랜잭션. 실패 시 Target 변경과 `AsyncJob` 모두 rollback |
| Asset 컨텍스트 override 수정 + recompute AsyncJob + enqueue 예약 | 1개 트랜잭션. 실패 시 `AssetContextOverride` 변경과 `AsyncJob` 모두 rollback |
| Risk recompute Job 생성 + enqueue 예약 | Worker/Redis preflight 후 1개 트랜잭션. 실패 시 `AsyncJob` 생성 없음 |

## 7.7 마이그레이션 전략

- Django의 표준 마이그레이션 사용
- 초기 마이그레이션 1개로 시작
- 캡스톤 기간 중에는 하위 호환을 신경 쓰지 않고 destructive migration 허용
- 운영 가정 시 `RunPython` 데이터 마이그레이션은 별도 작성

## 7.8 시드 데이터

테스트베드와 함께 기본 시드 데이터를 제공한다.

| 시드 | 내용 |
|---|---|
| Algorithm Risk Table | 6.2.1의 알고리즘별 A 값 사전 등록 (코드 상수) |
| 기본 Target | 테스트베드 7개 호스트의 주요 포트 사전 등록 (`fixtures/initial_targets.json`) |
| 기본 가중치 | 모두 1.0 |

> 시드는 `python manage.py loaddata`로 적재.
