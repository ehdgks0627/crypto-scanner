# API 테스트 시나리오 계약

## 1 목적

본 문서는 Backend API를 TDD로 구현하기 위한 자연어 기반 테스트 계약이다. `docs/api/openapi.yaml`이 필드와 엔드포인트의 기계 판독 기준이라면, 본 문서는 상태 전이, 오류 처리, worker/agent 흐름, 프론트엔드가 의존하는 동작을 시나리오로 고정한다.

구현 단계에서는 각 시나리오 ID를 Django API test 이름에 대응시킨다.

예:
- `API-COM-001` -> `test_request_id_is_returned_on_success`
- `API-JOB-004` -> `test_running_recompute_job_cannot_be_cancelled`

## 2 공통 테스트 원칙

- 모든 API 경로는 `/api` prefix를 사용한다.
- 모든 JSON 응답은 `application/json`을 사용한다. CBOM export는 예외적으로 다운로드 헤더를 검증한다.
- 모든 2xx/4xx/5xx 응답은 `X-Request-Id`를 포함한다.
- 클라이언트가 UUID 형식의 `X-Request-Id`를 보내면 서버는 같은 값을 반향한다.
- 서버가 생성하는 `X-Request-Id`도 UUID 형식이다.
- 오류 응답은 항상 `{"error": "...", "message": "...", "details": {...}}` envelope를 사용한다. 상세 정보가 없으면 `details`는 빈 객체 `{}`이다.
- Django Ninja/Pydantic 기본 validation 응답은 외부로 직접 노출하지 않는다.
- 다중 query filter는 CSV만 v1 계약으로 인정한다. 예: `tier=CRITICAL,HIGH`.
- 같은 파라미터 반복 형식은 v1 계약이 아니다. 예: `tier=CRITICAL&tier=HIGH`.
- 페이지네이션 응답은 항상 `items`, `total`, `offset`, `limit`을 포함한다.
- JobEnvelope는 항상 `id`, `kind`, `resource`, `status`, `progress`, `started_at`, `cancel_requested_at`, `finished_at`, `result`, `error`를 포함한다.
- `PENDING`/`RUNNING` Job의 `result`는 항상 `null`이다.
- `progress`는 항상 키가 존재하며 값은 `JobProgress | null`이다.

## 3 공통/오류/페이지네이션

### API-COM-001: 성공 응답은 Request ID를 반환한다

전제:
- Target이 1개 이상 존재한다.

행위:
- 클라이언트가 `X-Request-Id: 11111111-1111-4111-8111-111111111111` 헤더로 `GET /api/targets`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 헤더 `X-Request-Id` 값은 `11111111-1111-4111-8111-111111111111`이다.
- 응답 본문은 페이지네이션 envelope를 따른다.

### API-COM-002: 서버가 Request ID를 생성한다

전제:
- 클라이언트가 `X-Request-Id`를 보내지 않는다.

행위:
- `GET /api/meta/protocols`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 헤더에 UUID 형식의 `X-Request-Id`가 있다.

### API-COM-003: validation 오류는 표준 ErrorResponse를 사용한다

행위:
- `POST /api/jobs`에 빈 `target_ids` 또는 빈 `scanners`를 보낸다.

기대:
- 응답 상태는 422이다.
- 응답 본문 `error`는 `unprocessable`이다.
- 응답 본문은 `error`, `message`, `details`를 포함한다.
- Django Ninja 기본 오류 구조가 그대로 노출되지 않는다.

### API-COM-004: not found 오류는 표준 ErrorResponse를 사용한다

행위:
- 존재하지 않는 `GET /api/assets/999999`를 호출한다.

기대:
- 응답 상태는 404이다.
- 응답 본문 `error`는 `not_found`이다.
- 응답 본문은 `details`를 포함한다. 상세 정보가 없으면 `{}`이다.
- 응답 헤더에 `X-Request-Id`가 있다.

### API-COM-005: CSV query array만 다중 필터로 처리한다

전제:
- CRITICAL/HIGH/LOW tier RiskScore가 존재한다.

행위:
- `GET /api/snapshots/{sid}/risks?tier=CRITICAL,HIGH`를 호출한다.

기대:
- 응답 상태는 200이다.
- 반환된 모든 item의 tier는 `CRITICAL` 또는 `HIGH`이다.
- 응답은 `items`, `total`, `offset`, `limit`을 포함한다.

### API-COM-006: 반복 query parameter는 계약 위반으로 거절한다

행위:
- `GET /api/snapshots/{sid}/risks?tier=CRITICAL&tier=HIGH`를 호출한다.

기대:
- 응답 상태는 400이다.
- 응답 본문 `error`는 `validation_error`이다.
- 응답 본문 `details`는 반복 query parameter가 v1 계약이 아님을 식별할 수 있는 정보를 포함한다.

### API-COM-007: 내부 예외도 표준 ErrorResponse와 Request ID를 반환한다

전제:
- 테스트에서 endpoint handler 또는 service 함수를 monkeypatch하여 처리 중 예외가 발생하게 한다.

행위:
- 해당 API를 호출한다.

기대:
- 응답 상태는 500이다.
- 응답 본문 `error`는 `internal`이다.
- 응답 본문은 `error`, `message`, `details`를 포함한다.
- 응답 헤더에 `X-Request-Id`가 있다.

## 4 Targets

### API-TGT-001: Target 목록을 조회한다

전제:
- Target `web.testbed.local:443/TCP`가 존재한다.

행위:
- `GET /api/targets?host=web&limit=20&offset=0`를 호출한다.

기대:
- 응답 상태는 200이다.
- `items`에는 host가 `web`을 포함하는 Target만 있다.
- 각 Target은 `context`, `created_at`, `updated_at`을 포함한다.

### API-TGT-002: Target을 생성한다

행위:
- `POST /api/targets`에 host, port, protocol_hint, transport, context를 보낸다.

기대:
- 응답 상태는 201이다.
- 생성된 Target은 요청한 host/port/transport를 가진다.
- context 필드는 누락된 값이 있더라도 schema에 맞게 반환된다.

### API-TGT-003: Target 상세를 조회한다

전제:
- Target `web.testbed.local:443/TCP`가 존재한다.

행위:
- `GET /api/targets/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 Target 단일 객체이다.
- `id`, `host`, `port`, `protocol_hint`, `transport`, `context`, `created_at`, `updated_at`을 포함한다.

### API-TGT-004: 중복 Target 생성은 conflict로 거절한다

전제:
- `(host, port, transport)`가 같은 Target이 이미 존재한다.

행위:
- 같은 `(host, port, transport)`로 `POST /api/targets`를 호출한다.

기대:
- 응답 상태는 409이다.
- 응답은 ErrorResponse envelope를 따른다.

### API-TGT-005: Target context 변경은 recompute job id를 반환한다

전제:
- Target에 연결된 Asset과 RiskScore가 존재한다.
- context 변경으로 위험도 재계산이 필요한 상태이다.

행위:
- `PATCH /api/targets/{id}`에 `{"context": {"criticality": "critical"}}`을 보낸다.

기대:
- 응답 상태는 200이다.
- 응답 본문은 갱신된 `target`을 포함한다.
- `recompute_job_id`가 API-visible AsyncJob id로 반환된다.

### API-TGT-006: Target context 변경 enqueue 실패는 rollback한다

전제:
- Target에 연결된 Asset과 RiskScore가 존재한다.
- backend가 recompute job enqueue에 실패하도록 설정한다.

행위:
- `PATCH /api/targets/{id}`에 위험도 재계산이 필요한 context 변경을 보낸다.

기대:
- 응답 상태는 503이다.
- 응답 본문 `error`는 `service_unavailable`이다.
- Target context 변경은 commit되지 않는다.
- orphan recompute AsyncJob은 남지 않는다.

### API-TGT-007: 변경 없는 Target PATCH는 recompute job을 만들지 않는다

전제:
- Target의 현재 `criticality`가 `high`이다.

행위:
- `PATCH /api/targets/{id}`에 `{"context": {"criticality": "high"}}`을 보낸다.

기대:
- 응답 상태는 200이다.
- `recompute_job_id`는 `null`이다.
- 새 recompute AsyncJob은 생성되지 않는다.

### API-TGT-008: Target 삭제는 soft unlink 정책을 따른다

전제:
- Target이 존재하고 과거 Snapshot Asset이 해당 Target을 참조한다.

행위:
- `DELETE /api/targets/{id}`를 호출한다.

기대:
- 응답 상태는 204이다.
- Target은 삭제된다.
- 과거 Snapshot/Asset은 보존된다.
- 연관 Asset의 `target` FK는 `SET_NULL` 정책을 따른다.

## 5 Discovery

### API-DSC-001: Discovery 목록은 page envelope를 반환한다

전제:
- COMPLETED Discovery와 RUNNING Discovery가 존재한다.

행위:
- `GET /api/discoveries?status=COMPLETED&limit=20&offset=0`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `items`, `total`, `offset`, `limit`을 포함한다.
- 반환된 item은 모두 `status=COMPLETED`이다.

### API-DSC-002: Discovery 생성은 JobEnvelope를 반환한다

행위:
- `POST /api/discoveries`에 CIDR, ports, include_default_ports를 보낸다.

기대:
- 응답 상태는 202이다.
- 응답은 JobEnvelope이다.
- `kind`는 `discovery`이다.
- `id`는 API-visible Job ID이다.
- `resource.kind`는 `discovery`이고 `resource.id`는 Discovery ID이다.
- `status`는 `PENDING`이다.
- `progress`는 `null`이다.
- `result`는 `null`이다.

### API-DSC-003: Discovery 상세는 생성 시각과 실행 시작 시각을 분리한다

전제:
- PENDING Discovery가 존재한다.

행위:
- `GET /api/discoveries/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- `created_at`은 값이 있다.
- `started_at`은 PENDING이면 `null`이다.
- worker가 실행을 시작한 뒤에는 `started_at`이 채워진다.
- 응답 헤더 `Cache-Control`은 `no-store`이다.

### API-DSC-004: Discovery endpoint 목록은 protocol hint와 detected protocol을 분리한다

전제:
- Discovery가 HTTPS, SSH, PostgreSQL endpoint를 발견했다.

행위:
- `GET /api/discoveries/{id}/endpoints`를 호출한다.

기대:
- 응답 상태는 200이다.
- `detected_protocol`은 실제 식별된 값이다. 예: `HTTPS`, `SSH`, `PostgreSQL`.
- `suggested_protocol_hint`는 Target 생성용 hint이다. 예: `TLS`, `SSH`, `UNKNOWN`.

### API-DSC-005: Discovery endpoint promote는 Target들을 생성한다

전제:
- Discovery endpoint 2개가 아직 promoted=false이다.

행위:
- `POST /api/discoveries/{id}/promote`에 endpoint id들과 target override를 보낸다.

기대:
- 응답 상태는 201이다.
- 각 promotion은 생성/기존 Target 연결 결과를 반환한다.
- promoted endpoint는 `promoted=true`와 `target_id`를 가진다.

### API-DSC-006: Worker/Redis 사용 불가 시 discovery 생성은 503이다

전제:
- backend가 worker queue에 enqueue할 수 없다.

행위:
- `POST /api/discoveries`를 호출한다.

기대:
- 응답 상태는 503이다.
- 응답 본문 `error`는 `service_unavailable`이다.
- Discovery와 AsyncJob 레코드는 생성되지 않는다.

### API-DSC-007: 취소된 Discovery는 partial endpoint를 보존한다

전제:
- RUNNING Discovery에 이미 저장된 DiscoveredEndpoint 2개가 있다.
- 사용자가 `POST /api/jobs/{job_id}/cancel`을 호출했고 worker가 취소 요청을 확인했다.

행위:
- `GET /api/discoveries/{id}`와 `GET /api/discoveries/{id}/endpoints`를 호출한다.

기대:
- Discovery `status`는 `CANCELLED`이다.
- 이미 저장된 endpoint는 목록에 남아 있다.
- 이 결과는 partial discovery 결과로 취급된다.
- 취소된 Discovery의 endpoint promote 허용 여부는 v1에서 금지한다. `POST /api/discoveries/{id}/promote`는 409 ErrorResponse를 반환한다.

## 6 Jobs / AsyncJob

### API-JOB-001: Scan Job 생성은 JobEnvelope를 반환한다

행위:
- `POST /api/jobs`에 target_ids와 scanners를 보낸다.

기대:
- 응답 상태는 202이다.
- `kind`는 `scan_job`이다.
- `resource.kind`는 `scan_job`이다.
- `status`는 `PENDING`이다.
- `progress`, `started_at`, `cancel_requested_at`, `finished_at`, `result`, `error`는 모두 키가 존재한다.
- `progress`와 `result`는 `null`이다.

### API-JOB-002: Worker/Redis 사용 불가 시 scan job 생성은 503이다

전제:
- backend가 worker queue에 enqueue할 수 없다.

행위:
- `POST /api/jobs`에 유효한 target_ids와 scanners를 보낸다.

기대:
- 응답 상태는 503이다.
- 응답 본문 `error`는 `service_unavailable`이다.
- ScanJob/AsyncJob 도메인 레코드는 orphan 상태로 남지 않는다.

### API-JOB-003: Job 목록은 page envelope를 반환한다

전제:
- scan_job, discovery, recompute AsyncJob이 존재한다.

행위:
- `GET /api/jobs?status=RUNNING&limit=20&offset=0`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `items`, `total`, `offset`, `limit`을 포함한다.
- 각 item은 full JobEnvelope이다.
- 반환된 item은 모두 `status=RUNNING`이다.

### API-JOB-004: Job polling은 no-store와 JobEnvelope를 반환한다

전제:
- RUNNING scan job이 존재한다.

행위:
- `GET /api/jobs/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 헤더 `Cache-Control`은 `no-store`이다.
- `progress`는 null이 아니며 `completed`, `total`을 포함한다.
- `result`는 `null`이다.

### API-JOB-005: Completed scan job은 snapshot result를 반환한다

전제:
- COMPLETED scan job이 Snapshot #56을 생성했다.

행위:
- `GET /api/jobs/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- `status`는 `COMPLETED`이다.
- `result.snapshot_id`는 56이다.

### API-JOB-006: Failed job은 error와 finished_at을 반환한다

전제:
- FAILED scan_job 또는 discovery AsyncJob이 존재한다.

행위:
- `GET /api/jobs/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- `status`는 `FAILED`이다.
- `result`는 `null`이다.
- `error`는 실패 원인을 담은 문자열이다.
- `finished_at`은 `null`이 아니다.

### API-JOB-007: RUNNING scan_job과 discovery는 cancel_requested_at을 반환한다

전제:
- RUNNING scan_job 또는 discovery AsyncJob이 존재한다.

행위:
- `POST /api/jobs/{id}/cancel`을 호출한다.

기대:
- 응답 상태는 202이다.
- 응답은 JobEnvelope이다.
- `cancel_requested_at`은 `null`이 아니다.
- API 응답 직후 상태는 `RUNNING`이고 취소 요청만 기록된다.
- worker가 취소 요청을 확인하면 최종 상태는 `CANCELLED`가 된다.

### API-JOB-008: PENDING recompute는 취소할 수 있다

전제:
- PENDING recompute AsyncJob이 존재한다.

행위:
- `POST /api/jobs/{id}/cancel`을 호출한다.

기대:
- 응답 상태는 202이다.
- 응답은 JobEnvelope이다.
- 최종 상태는 `CANCELLED`이다.

### API-JOB-009: RUNNING recompute는 취소할 수 없다

전제:
- RUNNING recompute AsyncJob이 존재한다.

행위:
- `POST /api/jobs/{id}/cancel`을 호출한다.

기대:
- 응답 상태는 409이다.
- 응답 본문 `error`는 `job_not_cancellable`이다.
- 응답 본문 `details`는 최소한 job id, kind, status를 포함한다.

### API-JOB-010: 종료된 Job 취소는 job_not_cancellable이다

전제:
- COMPLETED, FAILED, 또는 CANCELLED Job이 존재한다.

행위:
- `POST /api/jobs/{id}/cancel`을 호출한다.

기대:
- 응답 상태는 409이다.
- 응답 본문 `error`는 `job_not_cancellable`이다.

### API-JOB-011: 존재하지 않는 Job 취소는 not_found이다

행위:
- `POST /api/jobs/999999/cancel`을 호출한다.

기대:
- 응답 상태는 404이다.
- 응답 본문 `error`는 `not_found`이다.

### API-JOB-012: Job logs는 ScanRunLog page를 반환한다

전제:
- scan_job에 target x scanner 실행 로그가 존재한다.

행위:
- `GET /api/jobs/{id}/logs`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 page envelope이다.
- 각 item은 `scanner_kind`, `status`, `findings_count`, `started_at`, `finished_at`, `error`를 포함한다.

### API-JOB-013: Agent unavailable 또는 capability mismatch 로그는 API에서 조회된다

전제:
- Target은 `agent_enabled=true`이다.
- worker/service test 또는 fixture로 매핑된 Agent가 stale이거나 요청한 scanner capability를 지원하지 않는 실행 결과를 만든다.
- ScanRunLog에는 SKIPPED 로그가 이미 존재한다.

행위:
- `GET /api/jobs/{id}/logs`를 호출한다.

기대:
- 해당 Agent scanner 실행 로그는 `status=SKIPPED`이다.
- `error`는 `agent_unavailable`, `agent_stale`, 또는 `capability_unsupported` 중 하나이다.
- scan job 전체는 network scanner 결과가 있으면 `COMPLETED` 또는 `PARTIAL` 정책을 따른다.

## 7 Snapshots / Assets / Context

### API-SNP-001: Snapshot 목록은 최신순 페이지로 조회 가능하다

전제:
- Snapshot이 1개 이상 존재한다.

행위:
- `GET /api/snapshots?limit=20&offset=0`를 호출한다.

기대:
- 응답 상태는 200이다.
- 각 item은 `id`, `scan_job_id`, `serial_number`, `asset_count`, `created_at`, `summary`를 포함한다.

### API-SNP-002: Snapshot 상세를 조회한다

전제:
- Snapshot #56이 존재한다.

행위:
- `GET /api/snapshots/{id}`를 Snapshot #56의 id로 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `id`, `scan_job_id`, `serial_number`, `asset_count`, `created_at`, `summary`, `validation_errors`를 포함한다.

### API-SNP-003: Snapshot export는 CBOM JSON 다운로드를 반환한다

전제:
- Snapshot #56의 CBOM 파일이 존재한다.

행위:
- `GET /api/snapshots/56/export`를 호출한다.

기대:
- 응답 상태는 200이다.
- `Content-Disposition` 헤더가 다운로드 파일명을 포함한다.
- 응답 본문은 저장된 CBOM JSON이다.

### API-SNP-004: Snapshot diff는 두 snapshot의 변경 요약을 반환한다

전제:
- Snapshot #55와 #56이 존재한다.

행위:
- `GET /api/snapshots/56/diff?other=55`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `snapshot_a`, `snapshot_b`, `added`, `removed`, `modified`, `unchanged_count`를 포함한다.
- 동일 natural_key 기준으로 변경을 판정한다.

### API-AST-001: Asset 목록은 risk/filter/sort와 함께 조회 가능하다

전제:
- Snapshot #56에 certificate Asset과 RiskScore가 존재한다.

행위:
- `GET /api/snapshots/56/assets?asset_type=certificate&tier=CRITICAL,HIGH&sort=-risk_score`를 호출한다.

기대:
- 응답 상태는 200이다.
- 반환된 item은 asset summary와 risk summary를 포함한다.
- `offset`과 `limit`이 응답에 포함된다.

### API-AST-002: Asset 상세는 context 원본과 effective 값을 함께 반환한다

전제:
- Asset #9001에 Target context와 일부 AssetContextOverride가 존재한다.

행위:
- `GET /api/assets/9001`을 호출한다.

기대:
- 응답 상태는 200이다.
- `effective_context`는 위험도 계산에 사용된 최종값이다.
- `context_override`는 저장된 override 원본이며 상속 필드는 `null`이다.
- `context_sources`는 각 필드의 출처를 `asset_override`, `target`, `heuristic` 중 하나로 표시한다.

### API-AST-003: Asset context patch는 omit과 null을 구분한다

전제:
- Asset #9001에 기존 context_override가 존재한다.
- 기존 override는 `sensitivity=critical`, `criticality=high`, `lifespan_years=10`이다.
- Target context는 `sensitivity=high`, `criticality=medium`, `lifespan_years=5`, `exposure=internal_network`이다.

행위:
- `PATCH /api/assets/9001/context`에 `{"criticality": "critical", "lifespan_years": null}`을 보낸다.

기대:
- 생략된 `sensitivity`는 기존 override 값 `critical`을 유지한다.
- `criticality`는 `critical`로 저장된다.
- `lifespan_years` override는 제거되고 Target/heuristic 상속값을 사용한다.
- `context_override.lifespan_years`는 `null`이다.
- `effective_context.lifespan_years`는 Target context의 5이다.
- `context_sources.lifespan_years`는 `target`이다.
- 응답은 `effective_context`, `context_override`, `context_sources`, `recompute_job_id`를 포함한다.

### API-AST-004: Asset context patch enqueue 실패는 rollback한다

전제:
- Asset #9001과 기존 RiskScore가 존재한다.
- backend가 recompute job enqueue에 실패하도록 설정한다.

행위:
- `PATCH /api/assets/9001/context`에 유효한 override 변경을 보낸다.

기대:
- 응답 상태는 503이다.
- 응답 본문 `error`는 `service_unavailable`이다.
- AssetContextOverride 변경은 commit되지 않는다.
- orphan recompute AsyncJob은 남지 않는다.

### API-AST-005: 정성 분석 요청은 기존 레코드를 갱신해 반환한다

전제:
- Asset #9001이 존재한다.
- Asset #9001에 기존 QualitativeAssessment가 존재한다.

행위:
- `POST /api/assets/9001/qualitative`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 provider, summary, threat_scenarios, migration_recommendation, confidence, generated_at을 포함한다.
- 같은 자산에 기존 평가가 있으면 새 레코드를 만들지 않고 같은 레코드를 갱신해 반환한다.

## 8 Risk / Recompute / Migration

### API-RSK-001: 기본 risk weights 조회는 state를 반환한다

행위:
- `GET /api/risk/weights`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `wA`, `wD`, `wE`, `wL`, `wC`, `updated_at`을 포함한다.

### API-RSK-002: Snapshot risk 목록은 필터와 page envelope를 반환한다

전제:
- Snapshot #56에 CRITICAL/HIGH/LOW RiskScore가 존재한다.

행위:
- `GET /api/snapshots/56/risks?tier=CRITICAL,HIGH&min_score=70&limit=20&offset=0`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `items`, `total`, `offset`, `limit`을 포함한다.
- 반환된 item은 `asset_id`, `asset_name`, `asset_type`, `score`, `tier`, `factors`, `computed_at`을 포함한다.
- 반환된 item은 tier와 min_score 필터를 만족한다.

### API-RSK-003: risk weights 갱신 요청은 updated_at을 받지 않는다

행위:
- `PUT /api/risk/weights`에 `wA`, `wD`, `wE`, `wL`, `wC`만 보낸다.

기대:
- 응답 상태는 200이다.
- 응답은 갱신된 weights와 `updated_at`을 포함한다.

### API-RSK-004: risk weights 요청에 updated_at이 있으면 거절한다

행위:
- `PUT /api/risk/weights`에 `wA`, `wD`, `wE`, `wL`, `wC`와 추가 필드 `updated_at`을 보낸다.

기대:
- 응답 상태는 422이다.
- 응답 본문 `error`는 `unprocessable`이다.
- 기존 weights는 변경되지 않는다.

### API-RSK-005: risk weights 범위 밖 값은 거절한다

행위:
- `PUT /api/risk/weights`에 `wA=0.1`처럼 허용 범위 밖 값을 보낸다.

기대:
- 응답 상태는 422이다.
- 응답 본문 `details`는 실패한 필드와 허용 범위를 식별할 수 있다.

### API-RSK-006: Snapshot recompute는 recompute JobEnvelope를 반환한다

행위:
- `POST /api/snapshots/{sid}/recompute`에 weights와 persist flag를 보낸다.

기대:
- 응답 상태는 202이다.
- `kind`는 `recompute`이다.
- `resource.kind`는 `recompute`이고 `resource.id == id`이다.
- `result`는 `PENDING`이므로 `null`이다.

### API-RSK-007: Completed recompute는 updated_scores_count를 반환한다

전제:
- COMPLETED recompute AsyncJob이 Snapshot #56의 RiskScore 142개를 갱신했다.

행위:
- `GET /api/jobs/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- `kind`는 `recompute`이다.
- `status`는 `COMPLETED`이다.
- `result.snapshot_id`는 56이다.
- `result.updated_scores_count`는 142이다.

### API-RSK-008: Worker/Redis 사용 불가 시 recompute는 503이다

전제:
- backend가 worker queue에 enqueue할 수 없다.

행위:
- `POST /api/snapshots/{sid}/recompute`에 유효한 요청을 보낸다.

기대:
- 응답 상태는 503이다.
- 응답 본문 `error`는 `service_unavailable`이다.
- orphan recompute AsyncJob은 남지 않는다.

### API-RSK-009: Top risks는 n개 이하의 page envelope를 반환한다

전제:
- Snapshot #56에 RiskScore가 3개 이상 존재한다.

행위:
- `GET /api/snapshots/56/risks/top?n=2`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `items`, `total`, `offset`, `limit`을 포함한다.
- `items` 길이는 2 이하이다.
- item은 score 내림차순이다.

### API-MIG-001: Migration plan은 전환 권고 page를 반환한다

전제:
- Snapshot #56에 양자취약 Asset과 RiskScore가 존재한다.

행위:
- `GET /api/snapshots/56/migration-plan?tier=CRITICAL,HIGH&asset_type=certificate`를 호출한다.

기대:
- 응답 상태는 200이다.
- 각 item은 current, recommendation, alternatives, risk_score, tier를 포함한다.
- recommendation.strategy는 `replace`, `hybrid`, `no_change` 중 하나이다.

### API-MIG-002: Migration impact는 선택 Asset 영향만 계산한다

행위:
- `GET /api/snapshots/56/migration-plan/impact?asset_ids=9001,9002`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 selected_count, hosts, services, cert_reissues, config_changes, key_regens, estimated_downtime_min을 포함한다.

### API-MIG-003: Migration impact는 잘못된 asset_ids를 거절한다

행위:
- `GET /api/snapshots/56/migration-plan/impact?asset_ids=`를 호출한다.

기대:
- 응답 상태는 422이다.
- 응답 본문 `error`는 `unprocessable`이다.

행위:
- Snapshot #56에 속하지 않는 asset id를 포함해 `GET /api/snapshots/56/migration-plan/impact?asset_ids=9001,9999`를 호출한다.

기대:
- 응답 상태는 422이다.
- 응답 본문 `details`는 snapshot에 속하지 않는 asset id를 식별할 수 있다.

## 9 Agents

### API-AGT-001: 신규 Agent 등록은 token을 1회 반환한다

전제:
- 같은 hostname의 Agent가 없다.
- 요청에 유효한 `X-Bootstrap-Token`이 있다.

행위:
- `POST /api/agents/register`를 호출한다.

기대:
- 응답 상태는 201이다.
- 응답은 `id`, `agent_token`, `registration_action`, `token_rotated_at`을 포함한다.
- `registration_action`은 `created`이다.
- DB에는 raw token이 저장되지 않고 hash만 저장된다.
- 등록 직후 Agent의 `last_seen`은 등록 시각으로 초기화되어 list/detail 응답에서 null이 아니다.

### API-AGT-002: 기존 hostname 재등록은 token을 회전한다

전제:
- 같은 hostname의 Agent가 이미 존재한다.
- 요청에 유효한 `X-Bootstrap-Token`이 있다.

행위:
- 같은 hostname으로 `POST /api/agents/register`를 호출한다.

기대:
- 응답 상태는 200이다.
- 기존 Agent id가 유지된다.
- `registration_action`은 `token_rotated`이다.
- 새 `agent_token`이 반환된다.
- 기존 token으로 heartbeat를 호출하면 401이다.
- 새 token으로 heartbeat를 호출하면 200이다.
- 기존 Agent가 `active=false`였다면 재등록 후 `active=true`로 복구된다.

### API-AGT-003: bootstrap token이 없거나 틀리면 등록을 거절한다

행위:
- `X-Bootstrap-Token` 없이 `POST /api/agents/register`를 호출한다.

기대:
- 응답 상태는 401이다.
- 응답 본문 `error`는 `invalid_token`이다.

### API-AGT-004: Agent heartbeat는 last_seen을 갱신한다

전제:
- 활성 Agent와 유효한 agent_token이 존재한다.

행위:
- `POST /api/agents/{id}/heartbeat`를 Bearer token과 함께 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 `received_at`을 포함한다.
- Agent의 `last_seen`이 갱신된다.

### API-AGT-005: inactive Agent heartbeat는 거절한다

전제:
- `active=false`인 Agent와 과거에 발급된 token이 존재한다.

행위:
- `POST /api/agents/{id}/heartbeat`를 Bearer token과 함께 호출한다.

기대:
- 응답 상태는 401이다.
- 응답 본문 `error`는 `invalid_token`이다.
- `last_seen`은 갱신되지 않는다.

### API-AGT-006: Agent 목록은 stale 상태와 token 비노출을 보장한다

전제:
- 최근 5분 내 heartbeat를 보낸 active Agent가 있다.
- `last_seen < now - 5min`인 stale Agent가 있다.
- `active=false`인 inactive Agent가 있다.

행위:
- `GET /api/agents`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 page envelope이다.
- active fresh Agent의 `is_stale`은 `false`이다.
- stale Agent의 `is_stale`은 `true`이다.
- inactive Agent는 `active=false`로 표시된다.
- 어떤 item에도 `agent_token` 또는 `agent_token_hash`가 포함되지 않는다.

### API-AGT-007: Agent 상세는 token을 노출하지 않는다

전제:
- Agent가 존재한다.

행위:
- `GET /api/agents/{id}`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 Agent 단일 객체이다.
- `token_rotated_at`, `last_seen`, `active`, `is_stale`을 포함한다.
- `agent_token`과 `agent_token_hash`는 포함하지 않는다.

### API-AGT-008: Agent 비활성화는 soft delete이다

전제:
- 활성 Agent가 존재한다.

행위:
- `DELETE /api/agents/{id}`를 호출한다.

기대:
- 응답 상태는 204이다.
- Agent 레코드는 삭제되지 않고 `active=false`가 된다.
- 이후 Worker는 해당 Agent를 호출하지 않는다.

### API-AGT-009: stale 또는 capability mismatch Agent는 scan에서 skip된다

구현 위치:
- 이 시나리오는 HTTP API 테스트가 아니라 worker/service unit test로 구현한다.

전제:
- Target은 `agent_enabled=true`이다.
- 매핑된 Agent가 stale이거나 요청 scanner capability가 없다.

행위:
- scan job을 실행한다.

기대:
- Worker는 해당 Agent scanner 호출을 수행하지 않는다.
- ScanRunLog에는 `status=SKIPPED`가 기록된다.
- `error`는 `agent_stale` 또는 `capability_unsupported`이다.

## 10 Dashboard / Health / Meta

### API-DSH-001: Dashboard summary는 최신 snapshot 기준 집계를 반환한다

전제:
- 최신 Snapshot과 RiskScore, 최근 Job, Agent가 존재한다.

행위:
- `GET /api/dashboard/summary`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답은 snapshot, by_tier, by_asset_type, by_algorithm_family, quantum_vulnerable_ratio, recent_jobs, agents_status, trend를 포함한다.
- `recent_jobs`의 각 항목은 full JobEnvelope이다.

### API-DSH-002: Snapshot이 없으면 dashboard는 empty state를 반환한다

전제:
- Snapshot이 하나도 없다.

행위:
- `GET /api/dashboard/summary`를 호출한다.

기대:
- 응답 상태는 200이다.
- `snapshot`은 `null`이다.
- 집계 객체/배열은 빈 값 또는 0 값이다.
- 프론트엔드는 이를 오류가 아닌 empty state로 처리할 수 있다.

### API-DSH-003: Dashboard는 raw agent token을 노출하지 않는다

전제:
- Agent가 등록되어 있고 raw token이 발급된 적이 있다.

행위:
- `GET /api/dashboard/summary`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 본문 어디에도 `agent_token` 또는 `agent_token_hash`가 포함되지 않는다.
- `agents_status`는 `total`, `active`, `stale`을 포함한다.

### API-LST-001: 주요 목록 API는 empty page를 오류로 취급하지 않는다

전제:
- 대상 데이터가 없는 빈 DB 또는 빈 snapshot을 사용한다.

행위:
- `GET /api/targets`, `GET /api/discoveries`, `GET /api/jobs`, `GET /api/snapshots`, `GET /api/agents`를 호출한다.

기대:
- 각 응답 상태는 200이다.
- 각 응답은 `items=[]`, `total=0`, `offset`, `limit`을 포함한다.
- 프론트엔드는 이를 오류가 아닌 empty state로 렌더링할 수 있다.

### API-HEALTH-001: Health endpoint는 API/DB/Redis/Worker 상태를 반환한다

전제:
- API 서버, database, Redis, worker가 정상이다.

행위:
- `GET /api/health`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 헤더 `Cache-Control`은 `no-store`이다.
- 응답은 `status`, `api`, `database`, `redis`, `worker`, `checked_at`을 포함한다.
- 각 상태 값은 `ok`, `degraded`, `down` 중 하나이다.

### API-HEALTH-002: Health endpoint는 부분 장애를 degraded로 집계한다

전제:
- API 서버와 database는 정상이다.
- Redis 또는 worker 중 하나가 `down`이다.

행위:
- `GET /api/health`를 호출한다.

기대:
- 응답 상태는 200이다.
- 장애 component 값은 `down`이다.
- top-level `status`는 `degraded`이다.
- 프론트엔드는 Header 상태 인디케이터를 황색으로 표시할 수 있다.

### API-META-001: Meta endpoints는 정적 enum을 반환한다

행위:
- `GET /api/meta/protocols`, `GET /api/meta/scanners`, `GET /api/meta/algorithm-risk-table`를 호출한다.

기대:
- 응답 상태는 200이다.
- 응답 헤더 `Cache-Control`은 `max-age=600`이다.
- 값은 OpenAPI enum과 문서의 지원 목록과 일치한다.

## 11 Django 테스트 변환 가이드

첫 번째 Django 테스트 단계에서는 다음 순서로 구현한다.

1. 공통 middleware/exception 테스트: `API-COM-*`
2. Target CRUD 테스트: `API-TGT-*`
3. AsyncJob/JobEnvelope/cancel 테스트: `API-JOB-*`
4. Agent registration/token rotation 테스트: `API-AGT-*`
5. Discovery 생성/상태/endpoint/promote 테스트: `API-DSC-*`
6. Risk weights/recompute 테스트: `API-RSK-*`
7. Asset context override 테스트: `API-AST-*`
8. Dashboard/health/meta smoke 테스트: `API-DSH-*`, `API-HEALTH-*`, `API-META-*`

각 Django test는 OpenAPI schema 자체를 다시 검증하기보다, 본 시나리오의 상태 전이와 응답 의미를 검증한다. 필드 수준 schema 검증은 `docs/api/openapi.yaml`과 generated client/contract test가 담당한다.
