# 08. REST API 계약

## 8.1 개요

본 문서는 Frontend ↔ Backend 사이의 REST API 계약을 정의한다. 본 시스템은 Django + Django Ninja 조합을 사용하며, OpenAPI 스키마는 `/api/openapi.json`으로 자동 노출된다.

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
| 비동기 작업 | Job ID 반환, 클라이언트가 폴링 (`GET /jobs/{id}`, D-02) |

### 8.1.2 표준 에러 코드

| HTTP | error code | 의미 |
|---|---|---|
| 400 | `validation_error` | 요청 형식/값 오류 |
| 401 | `invalid_token` | (Agent API 한정) 토큰 누락/오류 |
| 404 | `not_found` | 자원 미존재 |
| 409 | `conflict` | 중복 등록, 상태 전이 불가 등 |
| 422 | `unprocessable` | 의미상 처리 불가 (예: 빈 target_ids로 Job 생성) |
| 500 | `internal` | 서버 내부 오류 |
| 503 | `service_unavailable` | Worker/Redis 미가동 등 |

## 8.2 엔드포인트 일람

| 그룹 | 메서드 | 경로 | 설명 |
|---|---|---|---|
| Targets | GET | `/api/targets` | Target 목록 |
| | POST | `/api/targets` | Target 생성 |
| | GET | `/api/targets/{id}` | Target 상세 |
| | PATCH | `/api/targets/{id}` | Target 부분 수정 |
| | DELETE | `/api/targets/{id}` | Target 삭제 |
| Discovery | POST | `/api/discoveries` | CIDR 디스커버리 시작 |
| | GET | `/api/discoveries/{id}` | 디스커버리 상태 |
| | GET | `/api/discoveries/{id}/endpoints` | 발견된 endpoint 목록 |
| | POST | `/api/discoveries/{id}/promote` | 선택된 endpoint를 Target으로 승격 |
| Scan Jobs | POST | `/api/jobs` | Scan Job 시작 |
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
| Agents | POST | `/api/agents/register` | Agent 자기 등록 |
| | GET | `/api/agents` | Agent 목록 |
| | GET | `/api/agents/{id}` | Agent 상세 |
| | POST | `/api/agents/{id}/heartbeat` | Heartbeat |
| | DELETE | `/api/agents/{id}` | Agent 비활성화 |
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
  "status": "RUNNING",
  "progress": {
    "completed": 4,
    "total": 9,
    "current_target": "web.testbed.local:443",
    "current_scanner": "network"
  },
  "started_at": "2026-04-25T10:00:00Z",
  "finished_at": null,
  "result": null,
  "error": null
}
```

`status` enum: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.

`COMPLETED`인 경우 `result`에 후속 자원 ID:
```json
{
  "status": "COMPLETED",
  "result": {"snapshot_id": 56}
}
```

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
**옵션**: `context.*`, `sni`, `ip`, `agent_*`.

응답 (201): 생성된 Target 객체.
응답 (409): 이미 존재하는 (host, port, transport) 조합.

### 8.4.3 `PATCH /api/targets/{id}`

부분 수정. context만 보낸 경우 context만 갱신. 운영 컨텍스트가 변경되면 비동기로 RiskScore 재계산이 큐잉된다.

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

### 8.4.4 `DELETE /api/targets/{id}`

응답 (204).

연관된 Asset은 `target` FK가 SET_NULL 되며, 과거 Snapshot은 보존된다.

## 8.5 Discovery

### 8.5.1 `POST /api/discoveries`

요청:
```json
{
  "cidr": "172.20.0.0/24",
  "ports": [22, 443, 8883, 5432, 25, 465, 587, 993, 995, 500, 4500],
  "include_default_ports": true
}
```

`include_default_ports: true`이면 시스템 기본 포트 리스트 (16번 결정의 테스트베드 9개 서비스 포트)에 사용자 입력 `ports`를 합집합한다.

응답 (202): Job Envelope (kind=`discovery`).

### 8.5.2 `GET /api/discoveries/{id}/endpoints`

응답:
```json
{
  "items": [
    {
      "id": 1,
      "ip": "172.20.0.10",
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
  "total": 25
}
```

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
  "status": "PENDING",
  "started_at": null,
  "finished_at": null
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
  "total": 18
}
```

### 8.6.4 `POST /api/jobs/{id}/cancel`

응답 (200): Job Envelope, 상태 `CANCELLED`로 전이.
응답 (409): 이미 종료된 Job (`COMPLETED`/`FAILED`).

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
  "total": 5
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
- `asset_class` (`crypto`/`host`/`service`/`data`)
- `asset_type` (`algorithm`/`certificate`/...)
- `target_id`
- `min_score`, `max_score`, `tier` (`CRITICAL` 등)
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
  "total": 142
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

`history`는 동일 자연 키의 과거 스냅샷 RiskScore (6.10).

### 8.8.3 `PATCH /api/assets/{id}/context`

자산별 컨텍스트 override (D-11, 19b).

요청:
```json
{
  "sensitivity": "critical",
  "criticality": "critical"
}
```

응답 (200):
```json
{
  "asset_id": 9001,
  "applied_overrides": {"sensitivity": "critical", "criticality": "critical"},
  "recompute_job_id": 791
}
```

### 8.8.4 `POST /api/assets/{id}/qualitative`

LLM 정성 분석 요청 (6.6, Mock 응답).

요청 본문 없음 (또는 `{}`).

응답 (200): QualitativeAssessment 객체. 결과는 DB 캐시에 저장되어 동일 자산 재요청 시 즉시 반환.

## 8.9 Risk

### 8.9.1 `GET /api/snapshots/{sid}/risks`

자산별 RiskScore 일람 (자산 정보 일부 포함).

쿼리 파라미터: `tier`, `min_score`, `max_score`, `sort`, `offset`, `limit`.

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
  "total": 142
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

요청: 6.3.3의 weights 객체.
응답 (200): 갱신된 가중치.

## 8.10 Migration

### 8.10.1 `GET /api/snapshots/{sid}/migration-plan`

쿼리 파라미터: `min_score`, `tier`, `asset_type`, `target_id`, `offset`, `limit`.

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
  "total": 23
}
```

권장 알고리즘 결정 규칙은 11번 문서(`11-migration-plan.md`)에서 상세 정의.

## 8.11 Agents

### 8.11.1 `POST /api/agents/register`

헤더: `X-Bootstrap-Token: <BOOTSTRAP_TOKEN>` (4.5.2).

요청:
```json
{
  "hostname": "web.testbed.local",
  "agent_url": "http://web.testbed.local:9100",
  "capabilities": ["cert_store", "ssh_config", "app_cert_files", "app_config"],
  "os_distribution": "alpine:3.20"
}
```

응답 (201):
```json
{
  "id": "f1e2d3c4-...",
  "agent_token": "<원문 토큰, 등록 시 1회만 노출>"
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
      "capabilities": ["cert_store", "ssh_config", ...],
      "os_distribution": "alpine:3.20",
      "registered_at": "...",
      "last_seen": "...",
      "active": true,
      "is_stale": false
    }
  ],
  "total": 3
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

## 8.12 Dashboard

### 8.12.1 `GET /api/dashboard/summary`

쿼리 파라미터: `snapshot_id` (생략 시 최신).

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
    {"id": 123, "status": "COMPLETED", "started_at": "...", "finished_at": "..."}
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

## 8.13 Meta

### 8.13.1 `GET /api/meta/protocols`

응답:
```json
{
  "protocols": ["TLS", "SSH", "IKE", "SMTP", "IMAP", "POP3", "UNKNOWN"]
}
```

### 8.13.2 `GET /api/meta/scanners`

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

### 8.13.3 `GET /api/meta/algorithm-risk-table`

응답: 6.2.1 테이블 (UI에서 참고용 표시).

## 8.14 응답 헤더 정책

| 헤더 | 정책 |
|---|---|
| `Cache-Control` | 폴링 엔드포인트 (`/api/jobs/{id}`, `/api/discoveries/{id}`)는 `no-store`. 정적 메타 (`/api/meta/*`)는 `max-age=600` |
| `X-Request-Id` | 모든 응답에 요청 추적용 UUID. 클라이언트가 보낸 경우 그대로 반향 |
| `Content-Disposition` | export 엔드포인트만 (8.7.2) |

## 8.15 OpenAPI 자동화

Django Ninja는 `/api/openapi.json` (스펙)과 `/api/docs` (Swagger UI)를 자동 노출한다. 본 문서는 의도와 시맨틱을 정의하며, 실제 엔드포인트 시그니처/필드 타입은 OpenAPI 문서와 일치해야 한다.
