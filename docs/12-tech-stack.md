# 12. 기술 스택 및 배포 가이드

## 12.1 개요

본 문서는 시스템 구현에 사용되는 라이브러리와 도구의 정확한 버전, 전체 저장소 구조, 환경변수, 그리고 로컬 개발 및 데모 배포 절차를 정의한다.

## 12.2 백엔드 스택

### 12.2.1 핵심 라이브러리

| 카테고리 | 패키지 | 버전 | 용도 |
|---|---|---|---|
| 언어 | Python | 3.12+ | |
| 웹 프레임워크 | Django | 5.0+ | |
| API 프레임워크 | django-ninja | 1.3+ | OpenAPI 자동 생성, 타입 안전 |
| ORM 마이그레이션 | (Django 내장) | - | |
| DB 드라이버 | psycopg | 3.2+ | PostgreSQL 클라이언트 (psycopg3) |
| 작업 큐 | celery | 5.4+ | 비동기 Job 실행 |
| 큐 broker | redis | 5.0+ | (서버), redis-py 5.0+ (클라이언트) |
| 데이터 검증 | pydantic | 2.7+ | django-ninja에 내장 |
| 환경변수 | django-environ | 0.11+ | `.env` 파일 로딩 |
| 로깅 | structlog | 24.1+ | 구조화 로깅 |
| 테스트 | pytest, pytest-django | 8.2+ / 4.8+ | |

### 12.2.2 스캐너 / 암호 라이브러리

| 카테고리 | 패키지 | 버전 | 용도 |
|---|---|---|---|
| 암호 기본 | cryptography | 42+ | X.509, RSA/EC 키 파싱 |
| TLS handshake | tlslite-ng | 0.8+ | TLS 1.0~1.3 ClientHello 직접 작성 |
| OpenSSL 바인딩 | pyOpenSSL | 24+ | SSL 컨텍스트 보조 |
| PQC 협상 | (외부 의존) | OQS Provider 기반 OpenSSL 3.x | subprocess로 호출 |
| PQC Python | oqs-python | optional, lockfile 고정 | (옵션) ML-KEM/ML-DSA 직접 사용 |
| 패킷 작성/파싱 | scapy | 2.5+ | IKE_SA_INIT |
| OpenPGP | pgpy | 0.6+ | PGP keyring 파싱 |
| PKCS#12 | cryptography | 42+ | (내장) |
| Java Keystore | pyjks | 20+ | JKS 파일 파싱 |
| SSH wire | (직접 구현) | - | KEX_INIT 단계 (paramiko 미사용 권장) |

### 12.2.3 Agent 의존성 (별도, 가벼운 구성)

| 패키지 | 버전 | 용도 |
|---|---|---|
| Python | 3.11+ | (Alpine 호환) |
| FastAPI | 0.110+ | Agent HTTP 서버 |
| uvicorn | 0.27+ | ASGI 서버 |
| pydantic | 2.7+ | |
| cryptography | 42+ | 인증서/키 파싱 (Agent도 일부 메타 추출) |
| pgpy | 0.6+ | PGP keyring |
| httpx | 0.27+ | 백엔드 등록/heartbeat 호출 |

> Agent는 Django/Celery에 의존하지 않는 독립 패키지로 구성한다.

## 12.3 프론트엔드 스택

| 카테고리 | 패키지 | 버전 | 용도 |
|---|---|---|---|
| 언어 | TypeScript | 5.4+ | |
| 프레임워크 | React | 18.3+ | |
| 빌드 | Vite | 5.2+ | |
| 라우팅 | react-router-dom | 6.23+ | |
| 서버 상태 | @tanstack/react-query | 5.32+ | |
| 클라이언트 상태 | zustand | 4.5+ | (가벼운 전역 상태) |
| HTTP 클라이언트 | ky | 1.x, lockfile 고정 | fetch wrapper 기반 |
| 폼 | react-hook-form | 7.51+ | |
| 검증 | zod | 3.23+ | |
| UI 컴포넌트 | shadcn/ui | (Radix 1.0+) | Tailwind 기반 |
| 스타일 | tailwindcss | 3.4+ | |
| 차트 | recharts | 2.12+ | |
| 그래프 | @xyflow/react (React Flow) | 12+ | 자산 의존성 그래프 |
| 아이콘 | lucide-react | lockfile 고정 | |
| 토스트 | sonner | 1.4+ | (shadcn 통합) |
| 날짜 | date-fns | 3.6+ | |
| 테이블 | @tanstack/react-table | 8.16+ | (shadcn DataTable 기반) |
| 코드 표시 | react-syntax-highlighter | 15+ | CBOM JSON 미리보기 |
| 마크다운 | marked | 12+ | Migration 보고서 다운로드 시 |

### 12.3.1 OpenAPI → 타입 생성

| 패키지 | 용도 |
|---|---|
| openapi-typescript | `docs/api/openapi.yaml` 또는 Backend의 `/api/openapi.json`에서 TS 타입 자동 생성 |

계약 설계 단계에서는 정적 원본인 `docs/api/openapi.yaml`을 사용한다.
백엔드 구현 후에는 Django Ninja가 노출하는 `/api/openapi.json`과 정적 원본의 차이를 검증한다.
타입 생성은 v1 계약 gate에 포함한다.

빌드 시점 또는 dev script로 호출:
```bash
npx openapi-typescript ../../docs/api/openapi.yaml -o src/api/generated/types.ts
```

## 12.4 인프라 / 운영

| 카테고리 | 도구 | 버전 | 용도 |
|---|---|---|---|
| 컨테이너 | Docker Engine | 25+ | |
| 오케스트레이션 | Docker Compose | v2.20+ | 시스템 스택 + 테스트베드 각각 |
| DB | PostgreSQL | 16 | |
| 캐시/브로커 | Redis | 7.2 | |
| 리버스 프록시 (옵션) | Nginx | 1.27+ | dev에서는 Vite dev server 사용 |
| DNS (테스트베드 한정) | dnsmasq | 2.90+ | `*.testbed.local` 해석 |

### 12.4.1 OS 가정

- 개발/시연 호스트: Linux (Ubuntu 22.04+) 또는 macOS 14+ 또는 Windows 11 + WSL2
- IPsec 테스트베드는 Linux 호스트에서 가장 안정적. macOS/Windows에서도 동작 가능하나 strongswan 컨테이너 권한 설정이 다를 수 있음

## 12.5 저장소 디렉터리 구조

루트 저장소는 문서/계약, 시스템 앱, 테스트베드, 보조 도구를 포함하는 monorepo 구조로 구성한다. 아래 트리는 구현 scaffold 대상 구조이며, 실제 구현 코드는 `system/` 아래에 두고 API 설계와 테스트 의도는 `docs/`, `test-contracts/`에 분리해 보관한다.

```
crypto-scanner/
├── README.md
├── docs/                      # 본 명세 문서들 (00~13.md)
│   └── api/
│       ├── openapi.yaml        # API 계약 source of truth
│       └── examples/           # OpenAPI externalValue 예시 JSON
├── test-contracts/             # 구현 전 TDD/acceptance 계약
│   └── api/
│       └── scenarios.md        # 자연어 API acceptance scenarios
├── system/                    # 시스템 스택 (백엔드 + 프론트 + DB + Redis)
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── backend/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── manage.py
│   │   ├── pqc_ras/           # Django project
│   │   │   ├── settings.py
│   │   │   ├── urls.py
│   │   │   ├── celery.py
│   │   │   └── wsgi.py
│   │   ├── apps/
│   │   │   ├── core/          # 공통 error/request id/pagination/csv parser
│   │   │   ├── targets/
│   │   │   ├── discoveries/
│   │   │   ├── jobs/          # AsyncJob 공통 lifecycle, ScanJob 생성/조회
│   │   │   ├── snapshots/     # CbomSnapshot, Edge, export/diff
│   │   │   ├── assets/        # Asset inventory/detail/context/qualitative
│   │   │   ├── risk/          # RiskScore, weights
│   │   │   ├── migration/     # Migration Plan
│   │   │   ├── agents/
│   │   │   ├── health/        # /api/health
│   │   │   ├── dashboard/     # /api/dashboard/summary
│   │   │   └── meta/          # /api/meta/*
│   │   ├── scanners/          # Network Scanner 구현
│   │   │   ├── base.py
│   │   │   ├── tls.py
│   │   │   ├── ssh.py
│   │   │   ├── ike.py
│   │   │   └── starttls.py
│   │   ├── cbom/              # CBOM 생성/검증
│   │   │   ├── builder.py
│   │   │   ├── validator.py
│   │   │   └── diff.py
│   │   ├── risk_engine/       # 위험도 계산
│   │   │   ├── algorithm_table.py
│   │   │   ├── factors.py
│   │   │   └── computer.py
│   │   ├── llm/               # LLM 추상화 + Mock
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── (provider 구현은 v2)
│   │   ├── tests/
│   │   │   ├── scanners/
│   │   │   ├── cbom/
│   │   │   ├── risk_engine/
│   │   │   └── llm/
│   │   └── fixtures/
│   │       └── initial_targets.json
│   └── frontend/
│       ├── Dockerfile
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       └── src/
│           ├── app/            # router, providers, layout shell
│           ├── api/            # fetch wrapper + generated OpenAPI types
│           ├── components/     # 공통 UI + layout
│           ├── features/       # dashboard/targets/assets/... feature modules
│           ├── pages/          # route entry components
│           ├── lib/            # format, utils, constants
│           ├── stores/         # Zustand store
│           └── styles/
├── testbed/                   # 테스트베드 (별도 docker-compose)
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── README.md
│   ├── dns/
│   │   └── dnsmasq.conf
│   ├── certs/
│   │   ├── generate.sh
│   │   └── (생성된 ca/, web/, mail/, db/, ... 디렉터리는 .gitignore)
│   ├── services/
│   │   ├── web/, pqc-tls/, ssh/, mqtt/, ipsec/, mail/, db/
│   └── agent/                 # Agent 베이스 (web/ssh/db에 탑재)
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── src/
│           ├── main.py
│           ├── register.py
│           ├── auth.py
│           ├── scanners/
│           └── schemas.py
└── tools/                     # 보조 스크립트
    ├── seed_targets.sh
    ├── reset_db.sh
    └── generate_test_data.sh
```

### 12.5.1 Backend app 내부 표준 구조

각 Django app은 API/router, schema, 조회 로직, mutation 로직을 분리한다. 모델이 없는 app(`health`, `dashboard`, 일부 `meta`)도 가능한 한 같은 레이아웃을 유지한다.

```
apps/<domain>/
├── apps.py
├── models.py          # 도메인 모델. 모델이 없으면 생략 가능
├── schemas.py         # Django Ninja request/response schema
├── api.py             # Ninja Router와 endpoint binding
├── selectors.py       # read/query 전용 로직
├── services.py        # write/use-case/transaction 로직
├── tasks.py           # Celery task. 비동기 작업이 없는 app은 생략 가능
├── errors.py          # 도메인별 예외가 필요할 때만
└── tests/
    ├── test_api_<scenario>.py
    └── factories.py
```

구현 규칙:

- `api.py`는 request parsing, schema binding, status code mapping에 집중한다.
- DB 변경과 transaction boundary는 `services.py`에 둔다.
- 목록/상세 조회와 prefetch/select 관련 최적화는 `selectors.py`에 둔다.
- 테스트 이름은 가능한 경우 `test_<scenario_id>_<short_name>` 형식으로 `test-contracts/api/scenarios.md`의 시나리오 ID와 연결한다. Python 함수명에서는 scenario id의 hyphen을 underscore로 바꾼다. 예: `API-JOB-009` -> `test_api_job_009_running_recompute_not_cancellable`.
- OpenAPI `operationId`와 Django Ninja router 함수명은 의미가 어긋나지 않게 유지한다.

### 12.5.2 Backend 공통 모듈 책임

```
apps/core/
├── errors.py          # ErrorResponse 변환, exception handler
├── pagination.py      # Page envelope 공통 처리
├── request_id.py      # X-Request-Id 생성/반향
├── query_params.py    # CSV query parser, repeated query 거절
├── responses.py       # 공통 response helpers
└── testing.py         # API test 공통 assertion/helper
```

`apps/core`는 도메인 모델을 소유하지 않는다. 다른 app이 공통 기능을 import할 수는 있지만, core가 특정 도메인 app을 import하지 않도록 순환 의존을 피한다.

`apps/dashboard`는 read-only aggregate app이다. 별도 모델을 소유하지 않고 `snapshots`, `risk`, `jobs`, `agents` selector를 조합해 `/api/dashboard/summary`를 제공한다. Dashboard 전용 write service는 두지 않는다.

### 12.5.3 Celery task 배치와 책임

Celery task는 Django app 내부 `tasks.py`에 둔다. `pqc_ras/celery.py`는 `app.autodiscover_tasks()`를 사용해 app-local task를 등록한다.

| Task 종류 | 위치 | 책임 |
|---|---|---|
| Scan 실행 | `apps/jobs/tasks.py` | `AsyncJob`/`ScanJob` 상태 전이를 조율하고 scanner service 호출 |
| Discovery 실행 | `apps/discoveries/tasks.py` | CIDR discovery 실행, endpoint 저장 service 호출 |
| Risk recompute | `apps/risk/tasks.py` | RiskScore 재계산 service 호출 |

Recompute는 별도 도메인 모델을 만들지 않고 `AsyncJob(kind=recompute)`로 표현한다. `/api/jobs`는 공통 async lifecycle 조회/취소와 scan job 생성만 소유하고, recompute 요청 생성과 실행은 `apps/risk`가 소유한다.

Celery task는 thin orchestrator로 제한한다. DB write, transaction boundary, 상태 전이, rollback 대상 변경은 각 app의 `services.py`에 둔다. API mutation에서 enqueue를 동반하는 변경은 7.6 트랜잭션 경계 규칙을 따른다.

`scanners/`, `cbom/`, `risk_engine/`, `llm/`은 Django app이 아닌 pure module로 유지한다. 이 모듈은 가능하면 DB에 직접 접근하지 않고 입력 객체/DTO를 받아 결과를 반환한다. 해당 모듈의 unit test는 `system/backend/tests/<module>/`에 둔다.

### 12.5.4 Frontend feature 내부 표준 구조

프론트엔드는 route와 feature를 분리한다. `pages/`는 라우팅 진입점이고, 실제 UI/쿼리/폼 로직은 `features/`에 둔다.

```
src/features/<feature>/
├── api.ts             # feature query/mutation wrapper
├── queries.ts         # TanStack Query keys/options
├── components/
├── hooks/
├── schemas.ts         # Zod form schema
└── types.ts           # feature-local view model type
```

프론트 구현 규칙:

- `src/api/generated/`는 `docs/api/openapi.yaml`에서 생성한 타입 전용 위치로 사용한다. v1에서는 `openapi-typescript`로 `src/api/generated/types.ts`를 생성하고, API 호출 wrapper는 수기로 작성한다.
- 사람이 직접 작성하는 fetch wrapper는 `src/api/client.ts`에 둔다.
- 화면 전용 조합 로직은 `features/*`에 두고, `pages/*`에는 route parameter 연결과 page-level composition만 남긴다.
- feature 간 공유 UI는 `components/common` 또는 `components/layout`으로 승격하되, 한 화면에서만 쓰는 컴포넌트는 feature 내부에 둔다.
- `components/charts`와 `components/graph`는 여러 feature에서 재사용되는 primitive만 둔다. 특정 화면 전용 차트/그래프 조합은 해당 `features/<feature>/components/`에 둔다.

## 12.6 환경변수

### 12.6.1 시스템 스택 (`system/.env`)

```ini
# Django
DJANGO_SECRET_KEY=<랜덤 50자>
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_TIMEZONE=Asia/Seoul

# Database
DATABASE_URL=postgres://pqc:pqc@db:5432/pqc

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Agent 인증
AGENT_BOOTSTRAP_TOKEN=<랜덤 32자, 테스트베드 BOOTSTRAP_TOKEN과 동일값>

# 호스트네임 해석 (테스트베드)
DNS_RESOLVER=host.docker.internal:5353
TESTBED_BRIDGE_HOST=host.docker.internal
TESTBED_BRIDGE_DNS_PORT=5353

# Frontend (Vite 빌드 시)
VITE_API_BASE_URL=http://localhost:8000/api

# LLM 정성 평가 (옵션)
QUALITATIVE_LLM_PROVIDER=mock-rulebook
# QUALITATIVE_LLM_PROVIDER=openai-compatible
# QUALITATIVE_LLM_MODEL=
# QUALITATIVE_LLM_API_KEY=
# QUALITATIVE_LLM_BASE_URL=https://api.openai.com/v1
QUALITATIVE_LLM_TIMEOUT_SECONDS=30

# 운영
LOG_LEVEL=INFO
WORKER_CONCURRENCY=3
```

### 12.6.2 테스트베드 (`testbed/.env`)

```ini
# 시스템 백엔드 URL (Agent의 자기등록 대상)
BACKEND_URL=http://host.docker.internal:8000
BOOTSTRAP_TOKEN=<system AGENT_BOOTSTRAP_TOKEN과 동일>

# Agent 동작
AGENT_LISTEN=0.0.0.0:9100
AGENT_LOG_LEVEL=INFO
AGENT_PUBLIC_HOST=127.0.0.1

# 테스트베드 네트워크
TESTBED_BIND_ADDR=127.0.0.1
DNS_PORT_HOST=5353
IPSEC_NATT_PORT=45000
# 브리지 subnet은 dnsmasq 정적 레코드와 함께 compose에 172.31.240.0/24로 고정

# 인증서 생성 시 사용
CERT_VALIDITY_DAYS=365
CERT_NEAR_EXPIRY_DAYS=15
```

### 12.6.3 Agent 환경변수 (런타임 주입)

| 변수 | 출처 | 설명 |
|---|---|---|
| `BACKEND_URL` | testbed/.env | 등록 endpoint base |
| `BOOTSTRAP_TOKEN` | testbed/.env | 사전 공유 토큰 |
| `AGENT_HOSTNAME` | docker-compose 서비스명 또는 명시 | 등록 시 사용 |
| `AGENT_LISTEN` | testbed/.env | 0.0.0.0:9100 |
| `AGENT_CAPABILITIES` | docker-compose | 쉼표 구분 (`agent.cert_store,agent.ssh_config`) — 비활성화 옵션 |

## 12.7 docker-compose 구성

### 12.7.1 시스템 스택 (`system/docker-compose.yml` 골격)

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    ports: ["8000:8000"]
    depends_on: [db, redis]
    networks: [pqc-system-net]

  worker:
    build: ./backend
    command: celery -A pqc_ras worker -c ${WORKER_CONCURRENCY}
    env_file: .env
    depends_on: [db, redis]
    networks: [pqc-system-net]
    extra_hosts:
      - "host.docker.internal:host-gateway"

  frontend:
    build: ./frontend
    env_file: .env
    ports: ["5173:5173"]
    depends_on: [backend]
    networks: [pqc-system-net]

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: pqc
      POSTGRES_USER: pqc
      POSTGRES_PASSWORD: pqc
    volumes: [db-data:/var/lib/postgresql/data]
    networks: [pqc-system-net]

  redis:
    image: redis:7.2
    networks: [pqc-system-net]

volumes:
  db-data:

networks:
  pqc-system-net:
    driver: bridge
```

### 12.7.2 테스트베드 (`testbed/docker-compose.yml` 골격)

```yaml
services:
  dns:
    image: jpillora/dnsmasq
    volumes: [./dns/dnsmasq.conf:/etc/dnsmasq.conf:ro]
    ports: ["${DNS_PORT_HOST}:53/udp"]
    networks: [pqc-testbed-net]

  web:
    build: ./services/web    # nginx + agent
    env_file: .env
    environment:
      AGENT_HOSTNAME: web.testbed.local
      AGENT_CAPABILITIES: agent.cert_store,agent.pkg_keyring,agent.app_cert_files,agent.app_config
    ports: ["4430:443", "9101:9100"]
    networks: [pqc-testbed-net]
    extra_hosts:
      - "host.docker.internal:host-gateway"

  pqc-tls:
    build: ./services/pqc-tls
    ports: ["4431:443"]
    networks: [pqc-testbed-net]

  ssh:
    build: ./services/ssh    # openssh + agent
    env_file: .env
    environment:
      AGENT_HOSTNAME: ssh.testbed.local
      AGENT_CAPABILITIES: agent.ssh_userkey,agent.ssh_config,agent.cert_store
    ports: ["2222:22", "9102:9100"]
    networks: [pqc-testbed-net]
    extra_hosts:
      - "host.docker.internal:host-gateway"

  mqtt:
    build: ./services/mqtt
    ports: ["8883:8883"]
    networks: [pqc-testbed-net]

  ipsec:
    build: ./services/ipsec
    cap_add: [NET_ADMIN, SYS_MODULE]
    ports: ["5000:500/udp", "45000:4500/udp"]
    networks: [pqc-testbed-net]

  mail:
    build: ./services/mail
    ports:
      - "2525:25"
      - "4465:465"
      - "5587:587"
      - "9993:993"
      - "9995:995"
    networks: [pqc-testbed-net]

  db:
    build: ./services/db    # postgres + agent
    env_file: .env
    environment:
      AGENT_HOSTNAME: db.testbed.local
      AGENT_CAPABILITIES: agent.cert_store,agent.keystore,agent.app_cert_files,agent.app_config
    ports: ["54320:5432", "9103:9100"]
    networks: [pqc-testbed-net]
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  pqc-testbed-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.31.240.0/24
```

### 12.7.3 호스트 포트 충돌 방지 정책

테스트베드 컨테이너는 호스트의 1024 미만 포트를 사용하지 않는다 (12.7.2 참조). 모든 노출 포트는 1024 이상이며, 충돌 시 `.env`에서 변경 가능.

## 12.8 첫 실행 가이드

### 12.8.1 사전 준비

```bash
# 저장소 클론
git clone <repo>
cd crypto-scanner

# 시스템 스택 .env 작성
cp system/.env.example system/.env
openssl rand -hex 32   # AGENT_BOOTSTRAP_TOKEN/BOOTSTRAP_TOKEN, DJANGO_SECRET_KEY 생성에 사용
# system/.env 편집

# 테스트베드 .env 작성 (system AGENT_BOOTSTRAP_TOKEN과 같은 값을 BOOTSTRAP_TOKEN에 사용)
cp testbed/.env.example testbed/.env
# testbed/.env 편집
```

### 12.8.2 실행 순서

```bash
# 1. 시스템 스택 기동 (백엔드가 먼저 떠야 Agent 등록 가능)
cd system
docker compose up -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py loaddata fixtures/initial_targets.json

# 2. 테스트베드 인증서 생성 + 기동
cd ../testbed
./certs/generate.sh
docker compose up -d

# 3. 동작 확인
curl http://localhost:8000/api/agents     # 3개 Agent 등록 확인
curl http://localhost:8000/api/targets    # 시드된 Target 확인
open http://localhost:5173                # 대시보드
```

### 12.8.3 첫 스캔 실행

대시보드(`http://localhost:5173`)에서:
1. `/scans/new` 진입
2. 시드된 Target 9개 모두 선택
3. Scanner는 모두 체크
4. [스캔 시작] → 진행 모니터링 → 완료 시 Snapshot 자동 진입

또는 CLI로:
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"target_ids": [1,2,3,4,5,6,7,8,9], "scanners": ["network","agent.cert_store","agent.ssh_config"]}'
```

## 12.9 개발 워크플로우

### 12.9.1 백엔드 로컬 개발

```bash
cd system

# 로컬 PostgreSQL/Redis는 docker-compose로 띄우고 백엔드만 로컬 실행 가능
# system/docker-compose.yml에서 backend, worker, frontend는 주석 처리하거나 scale 0으로 둔다.
docker compose up -d db redis

cd backend

# 가상환경 + 의존성
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 마이그레이션 + 실행
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# 별도 터미널에서 worker
celery -A pqc_ras worker -l INFO
```

### 12.9.2 프론트엔드 로컬 개발

```bash
cd system/frontend

npm install
npm run dev      # Vite dev server (5173)

# 백엔드 OpenAPI 타입 동기화
npm run generate:types
```

### 12.9.3 Agent 로컬 개발 (테스트베드 컨테이너 외부에서)

```bash
cd testbed/agent

python -m venv .venv
source .venv/bin/activate
pip install -e .

BACKEND_URL=http://localhost:8000 \
BOOTSTRAP_TOKEN=<TOKEN> \
AGENT_HOSTNAME=local-dev \
AGENT_CAPABILITIES=cert_store,ssh_config \
python -m agent.main
```

## 12.10 테스트 전략

### 12.10.1 테스트 종류

| 종류 | 도구 | 범위 |
|---|---|---|
| 단위 테스트 (백엔드) | pytest, pytest-django | 모델, 위험도 계산, CBOM 빌더, 스캐너 파서 |
| 단위 테스트 (프론트) | vitest + @testing-library/react | 컴포넌트, 훅 |
| 통합 테스트 | pytest + 실제 PostgreSQL/Redis (docker-compose) | API 엔드포인트 |
| E2E 테스트 (옵션, v2) | Playwright | 주요 UX 플로우 |
| 스캐너 검증 | 테스트베드 자체가 known-answer test | 스캔 결과 vs 기대 자산 매트릭스 (2.5) |

### 12.10.2 스캐너 검증 데이터

`testbed/expected_assets.json`에 9개 서비스에서 발견되어야 할 자산을 미리 정의하고, 스캔 후 자동 비교 (CI 통합 시).

## 12.11 로깅 / 관측성

### 12.11.1 로그 형식

`structlog`로 구조화 JSON. 필드:
- `timestamp`, `level`, `event`, `request_id`, `job_id`, `target_id`, `agent_id`, `error`

### 12.11.2 로그 수집

캡스톤 v1: 컨테이너 stdout만 (Docker logs).
v2 옵션: ELK 또는 Loki + Grafana.

### 12.11.3 메트릭 (옵션, v2)

Prometheus 메트릭 endpoint (`/metrics`). 주요 지표:
- `scan_job_duration_seconds`
- `assets_discovered_total{scanner_kind}`
- `risk_compute_duration_seconds`
- `agent_heartbeat_age_seconds`

## 12.12 보안 체크리스트 (캡스톤 v1 한정)

| 항목 | 정책 |
|---|---|
| 시스템 스택 외부 노출 | 호스트 8000(API), 5173(UI)만 노출. DB/Redis는 컨테이너 네트워크 내부 |
| 테스트베드 외부 노출 | 호스트 포트는 모두 1024+ 비표준 매핑 |
| Bootstrap 토큰 | docker-compose env로 주입, 저장소에 커밋 금지 (`.env.example`만 커밋) |
| Agent 토큰 | DB에 해시(SHA-256)로만 저장. 등록 응답으로 1회만 노출 |
| HTTPS | 본 v1은 HTTP. 운영 가정 시 nginx/traefik 앞단에 TLS termination |
| CORS | Backend의 `DJANGO_ALLOWED_HOSTS` + django-cors-headers로 허용 origin 제한 |
| 민감 데이터 마스킹 | UI에서 Bootstrap 토큰은 항상 마스킹 표시 |

## 12.13 라이선스 / 의존성 정리

각 의존성의 라이선스를 README에 명시. 본 캡스톤은 학술 목적이며 외부 배포 시 다음 점검:
- shadcn/ui (MIT)
- Bouncy Castle (MIT 호환)
- OQS Provider (MIT)
- pgpy (BSD-3)
- 본 시스템 자체 라이선스: 캡스톤 종료 후 결정 (TBD)

## 12.14 버전 관리 / Git 전략

| 항목 | 정책 |
|---|---|
| 브랜치 | `main` (보호), `feature/*`, `fix/*` |
| 커밋 메시지 | Conventional Commits 권장 (`feat:`, `fix:`, `docs:`) |
| PR 리뷰 | 캡스톤 5인 팀 내 리뷰 1인 이상 |
| CI | GitHub Actions 필수: OpenAPI lint, example JSON/schema 검증, 타입 생성, 백엔드/프론트 lint + 테스트 |
| 태그 | `v0.1.0`부터 시작, 캡스톤 종료 시 `v1.0.0` |

## 12.15 트러블슈팅 가이드 (자주 겪는 이슈)

| 증상 | 원인 | 해결 |
|---|---|---|
| Agent 등록 실패 (401) | Bootstrap token 불일치 | system `AGENT_BOOTSTRAP_TOKEN`과 testbed `BOOTSTRAP_TOKEN`이 동일한지 확인 |
| 테스트베드 호스트네임 해석 실패 | dnsmasq 미기동 또는 host.docker.internal 미지원 환경 | `extra_hosts: host.docker.internal:host-gateway` 추가, Linux는 docker-compose v2.20+ 필요 |
| TLS Probe 실패 (PQC 서버) | OQS OpenSSL 미설치 | Worker 이미지에 OQS provider 빌드 포함 또는 PQC 협상 비활성화 옵션 |
| IKE Probe 무응답 | strongswan capability 부족 | 테스트베드 ipsec 컨테이너에 `NET_ADMIN`, `SYS_MODULE` 권한 |
| 활성 Job 카운터 멈춤 | Redis 단절 | `docker compose ps redis` 확인, 재시작 |
| 마이그레이션 충돌 | 캡스톤 중 destructive migration 잦음 | `tools/reset_db.sh` 실행 (개발 한정) |
