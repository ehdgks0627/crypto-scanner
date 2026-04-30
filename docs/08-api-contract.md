# 08. REST API 계약

## 8.1 개요

본 문서는 Frontend ↔ Backend 사이의 REST API 계약을 정의한다. API 계약의 기준 원본은 `docs/api/openapi.yaml`이며, 본 문서는 의도·시맨틱·상태 전이·운영 규칙을 설명한다. 백엔드 구현은 Django + Django Ninja 조합을 사용하며, 구현 후 `/api/openapi.json`은 `docs/api/openapi.yaml`과 동등해야 한다.

### 8.1.0 산출물 구성

| 산출물 | 역할 |
|---|---|
| `docs/08-api-contract.md` | 사람이 읽는 계약 문서. API 의미, 상태 전이, 예외 규칙 설명 |
| `docs/api/openapi.yaml` | 기계가 읽는 설계 기준 원본. 프론트 타입 생성과 백엔드 계약 검증 기준 |
| `docs/api/examples/*.json` | 프론트 mock, 문서 예시, 계약 테스트용 대표 payload |
| Django Ninja `/api/openapi.json` | 구현 결과물. CI에서 `docs/api/openapi.yaml`과 차이 검증 |

### 8.1.1 기본 규칙

| 항목 | 값 |
|---|---|
| Base URL | `/api` |
| Content-Type | `application/json` (별도 명시 시 제외) |
| 시간 형식 | ISO 8601 UTC (`2026-04-25T10:00:00Z`) |
| ID 형식 | 정수 (Asset, Target, ScanJob, CbomSnapshot, RiskScore 등) / UUID 문자열 (Agent) |
| 페이지네이션 | offset+limit (`?offset=0&limit=20`), 응답 envelope에 `total` 포함 |
| 정렬 | `?sort=field` (오름차순), `?sort=-field` (내림차순) |
| 필터 | 쿼리 파라미터로 (`?asset_type=algorithm&min_score=60`) |
| 인증 | 없음 (D-04, 단 Agent 통신은 Bearer 토큰) |
| 에러 형식 | `{"error": "<code>", "message": "<human readable>", "details": {...}}` |
| 비동기 작업 | Job Envelope 반환, 클라이언트가 `GET /jobs/{id}` 또는 도메인 상세 API로 폴링 (D-02) |

### 8.1.2 Query Array 규칙

다중 선택 필터는 CSV query string으로 표현한다. OpenAPI에서는 `style: form`, `explode: false` 배열로 정의한다.

예:
- `tier=CRITICAL,HIGH`
- `asset_type=certificate,protocol`
- `asset_ids=9001,9002`

Django Ninja 구현은 공통 CSV 파서 유틸을 사용해 `list[str]`/`list[int]`로 변환한다. 동일 파라미터 반복(`tier=CRITICAL&tier=HIGH`)은 v1 계약 범위에 포함하지 않는다.

### 8.1.3 표준 에러 코드

| HTTP | error code | 의미 |
|---|---|---|
| 400 | `validation_error` | 요청 형식/값 오류 |
| 401 | `invalid_token` | (Agent API 한정) 토큰 누락/오류 |
| 404 | `not_found` | 자원 미존재 |
| 409 | `conflict` | 중복 등록, 상태 전이 불가 등 |
| 409 | `job_not_cancellable` | Job이 현재 상태 또는 kind 정책상 취소 불가 |
| 422 | `unprocessable` | 의미상 처리 불가 (예: 빈 target_ids로 Job 생성) |
| 500 | `internal` | 서버 내부 오류 |
| 503 | `service_unavailable` | Worker/Redis 미가동 등 |

Django Ninja/Pydantic 기본 validation 응답은 그대로 노출하지 않는다. 백엔드는 커스텀 exception handler로 모든 API 오류를 위 ErrorResponse envelope로 변환한다.

## 8.2 엔드포인트 일람

| 그룹 | 메서드 | 경로 | 설명 |
|---|---|---|---|
| Targets | GET | `/api/targets` | Target 목록 |
| | POST | `/api/targets` | Target 생성 |
| | GET | `/api/targets/{id}` | Target 상세 |
| | PATCH | `/api/targets/{id}` | Target 부분 수정 |
| | DELETE | `/api/targets/{id}` | Target 삭제 |
| Discovery | GET | `/api/discoveries` | Discovery 작업 목록 |
| | POST | `/api/discoveries` | CIDR 디스커버리 시작 |
| | GET | `/api/discoveries/{id}` | 디스커버리 상태 |
| | GET | `/api/discoveries/{id}/endpoints` | 발견된 endpoint 목록 |
| | POST | `/api/discoveries/{id}/promote` | 선택된 endpoint를 Target으로 승격 |
| Jobs | POST | `/api/jobs` | Scan Job 시작 |
| | GET | `/api/jobs` | Job 목록 |
| | GET | `/api/jobs/{id}` | Job 상세 (폴링용) |
| | POST | `/api/jobs/{id}/cancel` | Job 취소 |
| | GET | `/api/jobs/{id}/logs` | ScanRunLog |
| Snapshots | GET | `/api/snapshots` | 스냅샷 목록 |
| | GET | `/api/snapshots/{id}` | 스냅샷 메타 |
| | GET | `/api/snapshots/{id}/export` | CBOM JSON export |
| | GET | `/api/snapshots/{id}/diff?other={id2}` | 두 스냅샷 diff |
| Assets | GET | `/api/snapshots/{sid}/assets` | 자산 목록 (스냅샷 단위) |
| | GET | `/api/assets/{id}` | 자산 상세 |
| | PATCH | `/api/assets/{id}/context` | 자산별 컨텍스트 override |
| | POST | `/api/assets/{id}/qualitative` | 정성 분석 요청 (Mock) |
| Risk | GET | `/api/snapshots/{sid}/risks` | 위험도 점수 목록 |
| | GET | `/api/snapshots/{sid}/risks/top` | Top-N |
| | POST | `/api/snapshots/{sid}/recompute` | 가중치 변경 후 재계산 |
| | GET | `/api/risk/weights` | 현재 가중치 조회 |
| | PUT | `/api/risk/weights` | 가중치 갱신 |
| Migration | GET | `/api/snapshots/{sid}/migration-plan` | 자산별 권장 전환 전략 |
| | GET | `/api/snapshots/{sid}/migration-plan/impact` | 선택 자산 전환 영향 분석 |
| Agents | POST | `/api/agents/register` | Agent 자기 등록 |
| | GET | `/api/agents` | Agent 목록 |
| | GET | `/api/agents/{id}` | Agent 상세 |
| | POST | `/api/agents/{id}/heartbeat` | Heartbeat |
| | DELETE | `/api/agents/{id}` | Agent 비활성화 |
| System | GET | `/api/health` | API/DB/Redis/Worker 상태 |
| Dashboard | GET | `/api/dashboard/summary` | 대시보드용 집계 데이터 |
| Meta | GET | `/api/meta/protocols` | 지원 프로토콜 enum |
| | GET | `/api/meta/scanners` | 사용 가능 스캐너 enum |
| | GET | `/api/meta/algorithm-risk-table` | 알고리즘 위험도 사전 테이블 (6.2.1) |

## 8.3 공통 스키마

### 8.3.1 Pagination Envelope

```json
{
  "items": [ ... ],
  "total": 142,
  "offset": 0,
  "limit": 20
}
```

### 8.3.2 Job Envelope (폴링 응답)

```json
{
  "id": 123,
  "kind": "scan_job",
  "resource": {
    "kind": "scan_job",
    "id": 123
  },
  "status": "RUNNING",
  "progress": {
    "completed": 4,
    "total": 9,
    "current_target": "web.testbed.local:443",
    "current_scanner": "network"
  },
  "started_at": "2026-04-25T10:00:00Z",
  "cancel_requested_at": null,
  "finished_at": null,
  "result": null,
  "error": null
}
```

`status` enum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.

`kind` enum: `scan_job`, `discovery`, `recompute`. `JobEnvelope.id`는 API-visible Job ID이며 작업 종류 전체에서 고유해야 한다. `resource`는 해당 Job이 만든 리소스 ID다. 예를 들어 Discovery 생성 응답에서 프론트엔드는 `job.id`로 폴링하고, `job.resource.id`로 `/discoveries/{id}` 화면에 진입한다. Recompute는 별도 도메인 테이블 없이 `AsyncJob(kind=recompute)` 자체가 작업 리소스이므로 `resource.id == job.id`다. Django 구현은 `AsyncJob` 모델을 두고 `ScanJob`/`Discovery` 도메인 레코드와 1:1로 연결한다. `/api/jobs`는 비동기 작업 목록이며, `POST /api/jobs`는 Scan Job만 생성한다. Discovery와 Recompute는 각각 `/api/discoveries`, `/api/snapshots/{sid}/recompute`에서 생성되지만 동일한 Job Envelope 형식으로 상태를 표현한다.

`result`는 완료 산출물만 담는다. `PENDING`/`RUNNING`에서는 항상 `null`이며, 프론트엔드는 폴링에는 `JobEnvelope.id`, 생성 직후 화면 이동에는 `resource`만 사용한다.

`progress` 키는 항상 존재하며 값은 `JobProgress | null`이다. `PENDING`이면 `null`, `RUNNING`이면 가능한 경우 진행률 객체, 완료/실패/취소 상태에서는 마지막 진행률 또는 `null`을 반환한다. `cancel_requested_at`은 취소 요청이 접수됐지만 Worker 정리가 끝나지 않은 동안에만 채워진다.

`COMPLETED`인 경우 `result`에 완료 산출물:
```json
{
  "id": 123,
  "kind": "scan_job",
  "status": "COMPLETED",
  "resource": {"kind": "scan_job", "id": 123},
  "progress": null,
  "started_at": "2026-04-25T10:00:00Z",
  "cancel_requested_at": null,
  "finished_at": "2026-04-25T10:05:00Z",
  "result": {"snapshot_id": 56},
  "error": null
}
```

Recompute 완료의 `result`는 poll ID를 반복하지 않고 실제 산출물만 담는다. 예: `{"snapshot_id": 56, "updated_scores_count": 142}`.

## 8.4 Targets

### 8.4.1 `GET /api/targets`

쿼리 파라미터:
- `host` (부분 일치)
- `protocol_hint` (TLS, SSH, ...)
- `agent_enabled` (bool)
- `sort`, `offset`, `limit`

응답 (200):
```json
{
  "items": [
    {
      "id": 1,
      "host": "web.testbed.local",
      "display_name": "Web Server (RSA)",
      "ip": null,
      "port": 443,
      "protocol_hint": "TLS",
      "sni": null,
      "transport": "TCP",
      "agent_enabled": true,
      "agent_url": null,
      "context": {
        "sensitivity": "high",
        "lifespan_years": 10,
        "criticality": "high",
        "exposure": "internal_network",
        "service_role": "web-frontend"
      },
      "created_at": "2026-04-25T09:00:00Z",
      "updated_at": "2026-04-25T09:00:00Z"
    }
  ],
  "total": 9,
  "offset": 0,
  "limit": 20
}
```

### 8.4.2 `POST /api/targets`

요청:
```json
{
  "host": "web.testbed.local",
  "display_name": "Web Server (RSA)",
  "ip": null,
  "port": 443,
  "protocol_hint": "TLS",
  "sni": null,
  "transport": "TCP",
  "agent_enabled": true,
  "agent_url": null,
  "context": {
    "sensitivity": "high",
    "lifespan_years": 10,
    "criticality": "high",
    "exposure": "internal_network",
    "service_role": "web-frontend"
  }
}
```

**필수**: `host`, `port`, `protocol_hint`.
**옵션**: `display_name`, `context.*`, `sni`, `ip`, `agent_*`.

응답 (201): 생성된 Target 객체.
응답 (409): 이미 존재하는 (host, port, transport) 조합.

### 8.4.3 `PATCH /api/targets/{id}`

부분 수정. `display_name`은 UI/보고서 표시용 이름이며 스캔 정체성, uniqueness, SNI에는 영향을 주지 않는다. context만 보낸 경우 context만 갱신. 운영 컨텍스트가 변경되면 비동기로 RiskScore 재계산이 큐잉된다.

요청 (예: 컨텍스트만 갱신):
```json
{
  "context": {"criticality": "critical"}
}
```

응답 (200): 갱신된 Target 객체 + 트리거된 재계산 Job ID.
```json
{
  "target": { ... },
  "recompute_job_id": 789
}
```

`recompute_job_id`는 `/api/jobs/{id}`로 폴링할 API-visible `AsyncJob.id`다.

### 8.4.4 `DELETE /api/targets/{id}`

응답 (204).

연관된 Asset은 `target` FK가 SET_NULL 되며, 과거 Snapshot은 보존된다.

## 8.5 Discovery

### 8.5.0 `GET /api/discoveries`

디스커버리 작업 목록 조회. 프론트엔드 `/discoveries` 페이지에서 사용한다.

쿼리 파라미터:
- `status` (`PENDING`/`RUNNING`/`COMPLETED`/`FAILED`/`CANCELLED`)
- `sort`, `offset`, `limit`

응답 (200):
```json
{
  "items": [
    {
      "id": 77,
      "cidr": "172.31.240.0/24",
      "port_list": [22, 443, 8883],
      "status": "COMPLETED",
      "created_at": "2026-04-25T09:00:00Z",
      "started_at": "2026-04-25T09:00:00Z",
      "finished_at": "2026-04-25T09:01:30Z",
      "error": null
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 20
}
```

### 8.5.1 `POST /api/discoveries`

요청:
```json
{
  "cidr": "172.31.240.0/24",
  "ports": [22, 443, 8883, 5432, 25, 465, 587, 993, 995, 500, 4500],
  "include_default_ports": true
}
```

`include_default_ports: true`이면 시스템 기본 포트 리스트 (16번 결정의 테스트베드 9개 서비스 포트)에 사용자 입력 `ports`를 합집합한다.

응답 (202): Job Envelope (kind=`discovery`). `id`는 Job ID, `resource.id`는 Discovery ID다.

Discovery 상세 폴링 응답에는 진행률 표시용 `progress`가 포함될 수 있다.
CIDR/port 입력 검증 실패는 422, Worker/Redis 큐 사용 불가는 503으로 ErrorResponse를 반환한다.

```json
{
  "id": 77,
  "cidr": "172.31.240.0/24",
  "port_list": [22, 443, 8883],
  "status": "RUNNING",
  "progress": {
    "completed": 4,
    "total": 256,
    "current_target": "172.31.240.10",
    "current_scanner": "network"
  },
  "created_at": "2026-04-25T09:00:00Z",
  "started_at": "2026-04-25T09:00:00Z",
  "finished_at": null,
  "error": null
}
```

`PENDING` 상태에서는 `started_at`이 `null`이고, `created_at`만 생성 시각으로 채워진다.

### 8.5.2 `GET /api/discoveries/{id}/endpoints`

응답:
```json
{
  "items": [
    {
      "id": 1,
      "ip": "172.31.240.10",
      "port": 443,
      "detected_protocol": "TLS",
      "banner_metadata": {
        "tls_version": "TLS 1.3",
        "cert_san": ["web.testbed.local", "web-ec.testbed.local"],
        "alpn": ["h2", "http/1.1"]
      },
      "promoted": false,
      "target_id": null,
      "suggested_protocol_hint": "TLS",
      "suggested_host": "web.testbed.local"
    }
  ],
  "total": 25,
  "offset": 0,
  "limit": 20
}
```

`detected_protocol`은 실제 식별된 서비스 프로토콜이다 (`HTTPS`, `MQTT`, `PostgreSQL`, `SSH`, `IKE`, `UNKNOWN` 등). `suggested_protocol_hint`는 Target 생성에 사용할 스캐너 힌트이며 `TLS`/`SSH`/`IKE`/`SMTP`/`IMAP`/`POP3`/`UNKNOWN` 중 하나다.

`suggested_host`는 reverse DNS 또는 인증서 SAN에서 추정 (26b).

### 8.5.3 `POST /api/discoveries/{id}/promote`

선택된 endpoint들을 Target으로 승격.

요청:
```json
{
  "promotions": [
    {
      "endpoint_id": 1,
      "host": "web.testbed.local",
      "protocol_hint": "TLS",
      "context": {
        "sensitivity": "high",
        "lifespan_years": 10,
        "criticality": "high",
        "service_role": "web-frontend"
      },
      "agent_enabled": false
    }
  ]
}
```

응답 (201):
```json
{
  "promoted": [
    {"endpoint_id": 1, "target_id": 42}
  ],
  "skipped": [
    {"endpoint_id": 2, "reason": "already_promoted"}
  ]
}
```

이미 promote된 endpoint는 `skipped`로 반환한다. 취소되었거나 종료 상태가 promote를 허용하지 않는 Discovery는 409 `ErrorResponse`를 반환한다.

## 8.6 Scan Jobs

### 8.6.1 `POST /api/jobs`

요청:
```json
{
  "target_ids": [1, 2, 3],
  "scanners": ["network", "agent.cert_store", "agent.ssh_config"]
}
```

`scanners` 가능 값:
- `network` (필수, 항상 활성화 권고)
- `agent.cert_store`
- `agent.pkg_keyring`
- `agent.ssh_userkey`
- `agent.ssh_config`
- `agent.keystore`
- `agent.app_cert_files`
- `agent.app_config`

agent.* 스캐너는 Target의 `agent_enabled=true`이고 매핑된 Agent의 capability에 포함된 경우에만 실행된다 (4.8.2). 그 외에는 ScanRunLog에 `SKIPPED` 기록.

응답 (202):
```json
{
  "id": 123,
  "kind": "scan_job",
  "resource": {
    "kind": "scan_job",
    "id": 123
  },
  "status": "PENDING",
  "progress": null,
  "started_at": null,
  "cancel_requested_at": null,
  "finished_at": null,
  "result": null,
  "error": null
}
```

응답 (422): `target_ids`가 빈 배열, 또는 `scanners`가 빈 배열.

### 8.6.2 `GET /api/jobs/{id}` (폴링용)

8.3.2 Job Envelope. **클라이언트는 5초 간격 폴링 권장** (D-02). 백엔드는 `Cache-Control: no-store` 응답.

### 8.6.3 `GET /api/jobs/{id}/logs`

응답:
```json
{
  "items": [
    {
      "id": 1001,
      "scan_job_id": 123,
      "target_id": 1,
      "target_label": "web.testbed.local:443",
      "scanner_kind": "network",
      "status": "SUCCESS",
      "findings_count": 14,
      "started_at": "...",
      "finished_at": "...",
      "error": null
    },
    {
      "id": 1002,
      "scan_job_id": 123,
      "target_id": 1,
      "target_label": "web.testbed.local:443",
      "scanner_kind": "agent.cert_store",
      "status": "SKIPPED",
      "findings_count": 0,
      "started_at": null,
      "finished_at": null,
      "error": "agent_unavailable"
    }
  ],
  "total": 18,
  "offset": 0,
  "limit": 20
}
```

### 8.6.4 `POST /api/jobs/{id}/cancel`

모든 `AsyncJob`에 대한 취소 요청 엔드포인트다.

취소 가능 범위:
- `scan_job`: `PENDING`, `RUNNING` 취소 가능
- `discovery`: `PENDING`, `RUNNING` 취소 가능
- `recompute`: `PENDING`만 취소 가능. `RUNNING` 이후에는 `409 job_not_cancellable`

응답 (202): Job Envelope. `RUNNING` scan/discovery는 즉시 `CANCELLED`가 아닐 수 있으며, 이 경우 `cancel_requested_at`이 채워지고 Worker가 확인한 뒤 `CANCELLED`로 전이한다.
응답 (404): 존재하지 않는 Job.
응답 (409): ErrorResponse `{"error": "job_not_cancellable", ...}`. 이미 종료된 Job (`COMPLETED`/`FAILED`/`CANCELLED`) 또는 현재 상태에서 취소 불가.

## 8.7 Snapshots & Diff

### 8.7.1 `GET /api/snapshots`

쿼리 파라미터: `sort`, `offset`, `limit`.

응답:
```json
{
  "items": [
    {
      "id": 56,
      "scan_job_id": 123,
      "serial_number": "urn:uuid:9f8e7d6c-...",
      "asset_count": 142,
      "created_at": "2026-04-25T10:05:00Z",
      "summary": {
        "by_tier": {"CRITICAL": 8, "HIGH": 15, "MEDIUM": 30, "LOW": 89},
        "by_type": {"algorithm": 50, "certificate": 20, "key": 30, "protocol": 15, "keystore": 2, "device": 7, "service": 14, "data": 4}
      }
    }
  ],
  "total": 5,
  "offset": 0,
  "limit": 20
}
```

### 8.7.2 `GET /api/snapshots/{id}/export`

쿼리 파라미터:
- `pretty=1` (들여쓰기 적용)

응답: CycloneDX 1.6 CBOM JSON. `Content-Type: application/vnd.cyclonedx+json`.

응답 헤더에 `Content-Disposition: attachment; filename="cbom-<id>.json"`.

### 8.7.3 `GET /api/snapshots/{id}/diff?other={id2}`

응답 (5.9.2 CbomDiff):
```json
{
  "snapshot_a": 55,
  "snapshot_b": 56,
  "added": [
    {"bom_ref": "alg-mldsa-65", "type": "crypto-asset", "name": "ML-DSA-65"}
  ],
  "removed": [],
  "modified": [
    {
      "bom_ref": "proto-tls13-web",
      "field_changes": {
        "properties.internal:alpn": ["http/1.1", "h2"]
      }
    }
  ],
  "unchanged_count": 138
}
```

`field_changes` 값은 `[old_value, new_value]` 배열.

## 8.8 Assets

### 8.8.1 `GET /api/snapshots/{sid}/assets`

쿼리 파라미터:
- `asset_class` (`crypto`/`host`/`service`/`data`, CSV 다중 선택 가능)
- `asset_type` (`algorithm`/`certificate`/..., CSV 다중 선택 가능)
- `target_id`
- `min_score`, `max_score`, `tier` (`CRITICAL` 등, CSV 다중 선택 가능)
- `quantum_vulnerable` (`true`/`false`)
- `q` (자유 텍스트, name 부분 일치)
- `sort` (예: `-risk_score`, `name`)
- `offset`, `limit`

응답:
```json
{
  "items": [
    {
      "id": 9001,
      "snapshot_id": 56,
      "bom_ref": "cert-leaf-web-rsa2048-ab12cd34",
      "asset_class": "crypto",
      "asset_type": "certificate",
      "name": "web.testbed.local (leaf)",
      "target_id": 1,
      "target_label": "web.testbed.local:443",
      "summary": {
        "algorithm": "RSA-2048",
        "key_size_bits": 2048,
        "quantum_vulnerable": true,
        "expires_at": "2026-01-01T00:00:00Z"
      },
      "risk": {
        "score": 84,
        "tier": "CRITICAL"
      }
    }
  ],
  "total": 142,
  "offset": 0,
  "limit": 20
}
```

### 8.8.2 `GET /api/assets/{id}`

응답: 전체 메타데이터 + 의존성 그래프.
```json
{
  "id": 9001,
  "snapshot_id": 56,
  "bom_ref": "cert-leaf-web-rsa2048-ab12cd34",
  "asset_class": "crypto",
  "asset_type": "certificate",
  "name": "web.testbed.local (leaf)",
  "crypto_properties": { ... },
  "properties": { ... },
  "natural_key": "x509:ab12cd34...",
  "discovered_at": "...",
  "target": {
    "id": 1,
    "host": "web.testbed.local",
    "port": 443
  },
  "effective_context": {
    "sensitivity": "critical",
    "lifespan_years": 10,
    "criticality": "critical",
    "exposure": "internal_network",
    "service_role": "web-frontend"
  },
  "context_override": {
    "sensitivity": "critical",
    "lifespan_years": null,
    "criticality": "critical",
    "exposure": null,
    "service_role": null
  },
  "context_sources": {
    "sensitivity": "asset_override",
    "lifespan_years": "target",
    "criticality": "asset_override",
    "exposure": "target",
    "service_role": "heuristic"
  },
  "risk": {
    "score": 84,
    "tier": "CRITICAL",
    "factor_a": 0.95,
    "factor_d": 0.8,
    "factor_e": 0.4,
    "factor_l": 0.85,
    "factor_c": 0.75,
    "weights": {"wA": 1.0, "wD": 1.0, "wE": 1.0, "wL": 1.0, "wC": 1.0}
  },
  "qualitative": {
    "provider": "mock",
    "summary": "...",
    "threat_scenarios": ["..."],
    "migration_recommendation": "...",
    "confidence": 0.5,
    "generated_at": "..."
  },
  "dependencies": {
    "dependsOn": [
      {"id": 9002, "bom_ref": "key-rsa-2048-web-leaf", "name": "RSA-2048 public key", "semantic": "embeds_key"}
    ],
    "dependedBy": [
      {"id": 9100, "bom_ref": "proto-tls13-web", "semantic": "uses_cert"}
    ]
  },
  "history": [
    {"snapshot_id": 55, "score": 80, "tier": "CRITICAL", "snapshot_created_at": "..."},
    {"snapshot_id": 56, "score": 84, "tier": "CRITICAL", "snapshot_created_at": "..."}
  ]
}
```

`effective_context`는 위험도 계산에 실제로 사용된 값이다. `context_override`는 `AssetContextOverride`에 저장된 원본 override이며, 값이 `null`이면 해당 필드는 Target/휴리스틱 상속 상태다. `context_sources`는 각 필드가 `asset_override`, `target`, `heuristic` 중 어디에서 왔는지 표시한다. `history`는 동일 자연 키의 과거 스냅샷 RiskScore (6.10).

### 8.8.3 `PATCH /api/assets/{id}/context`

자산별 컨텍스트 override (D-11, 19b).

요청:
```json
{
  "sensitivity": "critical",
  "criticality": "critical"
}
```

필드 생략은 기존 override 유지, 명시적 `null`은 해당 override 제거 후 Target/휴리스틱 상속값으로 복귀를 의미한다. override는 `AssetContextOverride`에 저장된다.

응답 (200):
```json
{
  "asset_id": 9001,
  "applied_overrides": {"sensitivity": "critical", "criticality": "critical"},
  "effective_context": {
    "sensitivity": "critical",
    "lifespan_years": 10,
    "criticality": "critical",
    "exposure": "internal_network",
    "service_role": "web-frontend"
  },
  "context_override": {
    "sensitivity": "critical",
    "lifespan_years": null,
    "criticality": "critical",
    "exposure": null,
    "service_role": null
  },
  "context_sources": {
    "sensitivity": "asset_override",
    "lifespan_years": "target",
    "criticality": "asset_override",
    "exposure": "target",
    "service_role": "heuristic"
  },
  "recompute_job_id": 791
}
```

`recompute_job_id`는 `/api/jobs/{id}`로 폴링할 API-visible `AsyncJob.id`다.

### 8.8.4 `POST /api/assets/{id}/qualitative`

LLM 정성 분석 요청 (6.6, Mock 응답).

요청 본문 없음 (또는 `{}`).

응답 (200): QualitativeAssessment 객체. 동일 Asset에는 QualitativeAssessment를 1개만 유지하며 재요청 시 기존 레코드를 갱신해 반환한다.

## 8.9 Risk

### 8.9.1 `GET /api/snapshots/{sid}/risks`

자산별 RiskScore 일람 (자산 정보 일부 포함).

쿼리 파라미터: `tier` (CSV 다중 선택 가능), `min_score`, `max_score`, `sort`, `offset`, `limit`.
반복 query parameter 형식(`tier=CRITICAL&tier=HIGH`)은 허용하지 않고 400 `ErrorResponse`를 반환한다.

응답:
```json
{
  "items": [
    {
      "asset_id": 9001,
      "asset_name": "web.testbed.local (leaf)",
      "asset_type": "certificate",
      "score": 84,
      "tier": "CRITICAL",
      "factors": {"a": 0.95, "d": 0.8, "e": 0.4, "l": 0.85, "c": 0.75},
      "computed_at": "..."
    }
  ],
  "total": 142,
  "offset": 0,
  "limit": 20
}
```

### 8.9.2 `GET /api/snapshots/{sid}/risks/top`

쿼리 파라미터: `n` (default 10).

응답: 같은 형식, `n`건만 반환. 정렬은 6.9 규칙.

### 8.9.3 `POST /api/snapshots/{sid}/recompute`

가중치 변경 후 재계산.

요청:
```json
{
  "weights": {"wA": 1.5, "wD": 1.0, "wE": 0.8, "wL": 1.5, "wC": 1.0},
  "persist_weights_as_default": false
}
```

응답 (202): Job Envelope (kind=`recompute`).

### 8.9.4 `GET /api/risk/weights`

응답:
```json
{
  "wA": 1.0,
  "wD": 1.0,
  "wE": 1.0,
  "wL": 1.0,
  "wC": 1.0,
  "updated_at": "..."
}
```

### 8.9.5 `PUT /api/risk/weights`

기본 가중치 갱신. 기존 RiskScore는 자동 재계산되지 않음 (사용자가 명시적으로 8.9.3 호출).

요청: 6.3.3의 weights 객체. 요청에는 `updated_at`을 포함하지 않는다.
```json
{
  "wA": 1.0,
  "wD": 1.0,
  "wE": 1.0,
  "wL": 1.5,
  "wC": 1.0
}
```

응답 (200): 갱신된 가중치 + `updated_at`.

## 8.10 Migration

### 8.10.1 `GET /api/snapshots/{sid}/migration-plan`

쿼리 파라미터: `min_score`, `tier` (CSV 다중 선택 가능), `asset_type` (CSV 다중 선택 가능), `target_id`, `offset`, `limit`.
추가로 `asset_ids=9001,9002` 형식의 특정 자산 필터를 사용할 수 있다.

응답:
```json
{
  "items": [
    {
      "asset_id": 9001,
      "asset_name": "web.testbed.local (leaf)",
      "asset_type": "certificate",
      "current": {
        "algorithm": "RSA-2048",
        "key_size_bits": 2048,
        "quantum_vulnerable": true
      },
      "recommendation": {
        "strategy": "hybrid",
        "target_algorithm": "RSA-2048 + ML-DSA-65 (hybrid certificate)",
        "rationale": "Long-lived data (lifespan=10y), high criticality. Hybrid 전략으로 호환성 유지.",
        "confidence": 0.7
      },
      "alternatives": [
        {
          "strategy": "replace",
          "target_algorithm": "ML-DSA-65",
          "trade_off": "기존 RSA 클라이언트와 비호환"
        }
      ],
      "risk_score": 84,
      "tier": "CRITICAL"
    }
  ],
  "total": 23,
  "offset": 0,
  "limit": 20
}
```

권장 알고리즘 결정 규칙은 11번 문서(`11-migration-plan.md`)에서 상세 정의.

### 8.10.2 `GET /api/snapshots/{sid}/migration-plan/impact`

선택된 자산들에 대한 전환 영향 분석만 별도 조회한다. Migration Plan 페이지에서 사용자가 Plan에 추가한 자산들의 호스트/서비스 영향과 예상 작업량을 갱신할 때 사용한다.

쿼리 파라미터:
- `asset_ids` (콤마 구분, 필수)

`asset_ids`가 비었거나 Snapshot에 속하지 않는 asset id를 포함하면 422 `ErrorResponse`를 반환한다.

응답:
```json
{
  "selected_count": 23,
  "hosts": ["web.testbed.local", "mail.testbed.local", "db.testbed.local"],
  "services": ["svc-web-https", "svc-mail-imaps", "svc-db-postgres"],
  "cert_reissues": 12,
  "config_changes": 4,
  "key_regens": 8,
  "estimated_downtime_min": 30
}
```

## 8.11 Agents

### 8.11.1 `POST /api/agents/register`

헤더: `X-Bootstrap-Token: <BOOTSTRAP_TOKEN>` (4.5.2).

요청:
```json
{
  "hostname": "web.testbed.local",
  "agent_url": "http://web.testbed.local:9100",
  "capabilities": ["agent.cert_store", "agent.ssh_config", "agent.app_cert_files", "agent.app_config"],
  "os_distribution": "alpine:3.20"
}
```

응답:
- `201 Created`: 새 hostname 등록
- `200 OK`: 기존 hostname 재등록. `agent_url`, `capabilities`, `os_distribution`을 갱신하고 새 token을 발급해 기존 token을 폐기
- `401 Unauthorized`: bootstrap token 누락/오류

등록 응답의 `agent_token`은 1회만 노출된다. Agent는 `id`와 token을 컨테이너 재시작 후에도 유지되도록 파일/볼륨에 저장한다. 권장 경로: `/var/lib/pqc-agent/credentials.json`. DB에는 raw token을 저장하지 않고 `agent_token_hash`만 저장한다.

```json
{
  "id": "f1e2d3c4-...",
  "agent_token": "<원문 토큰, 등록 시 1회만 노출>",
  "registration_action": "created",
  "token_rotated_at": "2026-04-25T09:00:00Z"
}
```

### 8.11.2 `GET /api/agents`

응답:
```json
{
  "items": [
    {
      "id": "f1e2d3c4-...",
      "hostname": "web.testbed.local",
      "agent_url": "http://web.testbed.local:9100",
      "capabilities": ["agent.cert_store", "agent.ssh_config", ...],
      "os_distribution": "alpine:3.20",
      "registered_at": "...",
      "token_rotated_at": "...",
      "last_seen": "...",
      "active": true,
      "is_stale": false
    }
  ],
  "total": 3,
  "offset": 0,
  "limit": 20
}
```

`is_stale`: `last_seen < now() - 5min` (4.4 정의).

### 8.11.3 `POST /api/agents/{id}/heartbeat`

헤더: `Authorization: Bearer <agent_token>`.

요청:
```json
{
  "uptime_sec": 3600,
  "version": "0.1.0"
}
```

응답 (200): `{"received_at": "..."}`.

### 8.11.4 `DELETE /api/agents/{id}`

비활성화 (소프트 삭제, `active=false`). 이후 Worker는 이 Agent를 호출하지 않음.

응답 (204).

## 8.12 Health

### 8.12.1 `GET /api/health`

프론트엔드 Header의 시스템 상태 인디케이터가 사용하는 경량 상태 API. API 서버가 응답 가능한 경우 HTTP 200으로 반환하고, 세부 상태는 body의 `status`와 component 필드로 판단한다. 응답은 캐시하지 않는다.

응답:
```json
{
  "status": "ok",
  "api": "ok",
  "database": "ok",
  "redis": "ok",
  "worker": "ok",
  "checked_at": "2026-04-29T00:00:00Z"
}
```

`status`, `api`, `database`, `redis`, `worker` 값은 `ok`, `degraded`, `down` 중 하나다.

top-level `status` 집계 규칙:
- 모든 component가 `ok`이면 `status=ok`
- `api` 또는 `database`가 `down`이면 `status=down`
- 그 외 component 중 하나라도 `degraded` 또는 `down`이면 `status=degraded`

따라서 Redis/Worker 장애는 기존 조회 기능은 가능하지만 새 scan/discovery/recompute가 제한되는 `degraded`로 표시한다.

## 8.13 Dashboard

### 8.13.1 `GET /api/dashboard/summary`

쿼리 파라미터: `snapshot_id` (생략 시 최신).

스냅샷이 아직 없으면 `snapshot`은 `null`이고 집계 객체/배열은 빈 값으로 반환한다. 프론트엔드는 이 응답을 Empty State로 렌더링한다.

응답:
```json
{
  "snapshot": {
    "id": 56,
    "created_at": "...",
    "asset_count": 142
  },
  "by_tier": {"CRITICAL": 8, "HIGH": 15, "MEDIUM": 30, "LOW": 89},
  "by_asset_type": {"algorithm": 50, "certificate": 20, "key": 30, "protocol": 15, "keystore": 2, "device": 7, "service": 14, "data": 4},
  "by_algorithm_family": {"RSA": 35, "ECDSA": 12, "ECDH": 18, "DH": 5, "Ed25519": 4, "AES": 30, "SHA": 15, "ML-KEM": 1, "ML-DSA": 1},
  "quantum_vulnerable_ratio": {"vulnerable": 75, "safe": 50, "unknown": 17},
  "recent_jobs": [
    {
      "id": 123,
      "kind": "scan_job",
      "resource": {"kind": "scan_job", "id": 123},
      "status": "COMPLETED",
      "progress": null,
      "started_at": "...",
      "cancel_requested_at": null,
      "finished_at": "...",
      "result": {"snapshot_id": 56},
      "error": null
    }
  ],
  "agents_status": {"total": 3, "active": 3, "stale": 0},
  "trend": [
    {"snapshot_id": 53, "created_at": "...", "critical_count": 5, "total_count": 130},
    {"snapshot_id": 54, "created_at": "...", "critical_count": 6, "total_count": 135},
    {"snapshot_id": 55, "created_at": "...", "critical_count": 7, "total_count": 138},
    {"snapshot_id": 56, "created_at": "...", "critical_count": 8, "total_count": 142}
  ]
}
```

## 8.14 Meta

### 8.14.1 `GET /api/meta/protocols`

응답:
```json
{
  "protocols": ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]
}
```

### 8.14.2 `GET /api/meta/scanners`

응답:
```json
{
  "scanners": [
    {"id": "network", "label": "Network Scanner", "requires_agent": false},
    {"id": "agent.cert_store", "label": "System CA Store", "requires_agent": true},
    {"id": "agent.pkg_keyring", "label": "Package Repository Keys", "requires_agent": true},
    {"id": "agent.ssh_userkey", "label": "SSH User Keys", "requires_agent": true},
    {"id": "agent.ssh_config", "label": "SSH Config Policy", "requires_agent": true},
    {"id": "agent.keystore", "label": "Keystore Files", "requires_agent": true},
    {"id": "agent.app_cert_files", "label": "Application Cert Files", "requires_agent": true},
    {"id": "agent.app_config", "label": "Application Config Policy", "requires_agent": true}
  ]
}
```

### 8.14.3 `GET /api/meta/algorithm-risk-table`

응답: 6.2.1 테이블 (UI에서 참고용 표시).

## 8.15 응답 헤더 정책

| 헤더 | 정책 |
|---|---|
| `Cache-Control` | 폴링 엔드포인트 (`/api/jobs/{id}`, `/api/discoveries/{id}`)와 `/api/health`는 `no-store`. 정적 메타 (`/api/meta/*`)는 `max-age=600` |
| `X-Request-Id` | 모든 응답에 요청 추적용 UUID. 클라이언트가 보낸 경우 그대로 반향 |
| `Content-Disposition` | export 엔드포인트만 (8.7.2) |

## 8.16 OpenAPI 계약 자동화

정적 설계 기준 원본은 `docs/api/openapi.yaml`이다. Django Ninja는 구현 결과물로 `/api/openapi.json` (스펙)과 `/api/docs` (Swagger UI)를 자동 노출한다.

구현 단계의 원칙:

- Django Ninja schema/router 이름은 `docs/api/openapi.yaml`의 `operationId`와 `components.schemas` 이름을 따른다.
- 프론트엔드 타입은 우선 `docs/api/openapi.yaml`에서 생성한다.
- 백엔드 구현 후 CI에서 `docs/api/openapi.yaml`과 `/api/openapi.json`의 path, method, required field, enum 차이를 검증한다.
- 문서 예시는 `docs/api/examples/*.json`에 보관하고, Markdown 본문의 예시는 해당 파일과 의미적으로 일치해야 한다.
