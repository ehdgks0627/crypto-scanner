# Context-Aware PQC Risk Assessment System

NIST SP 1800-38B의 *Quantum Readiness: Cryptographic Discovery* 방법론을 구현한 도구입니다. 운영 환경의 암호자산을 자동 식별하여 CycloneDX **CBOM**으로 정리하고, 양자 취약성·운영 컨텍스트 기반 위험도 평가를 통해 **PQC 전환 우선순위**를 도출합니다.

## 와이어프레임 미리보기

전체 화면 와이어프레임은 단일 HTML로 빌드되어 있으며, 아래 링크로 브라우저에서 바로 확인할 수 있습니다.

- **[와이어프레임 열기 (htmlpreview)](https://htmlpreview.github.io/?https://github.com/ehdgks0627/crypto-scanner/blob/main/docs/wireframes.html)**
- 백업 링크 (htmlpreview가 느릴 때): [raw.githack 버전](https://raw.githack.com/ehdgks0627/crypto-scanner/main/docs/wireframes.html)
- 로컬에서 보려면 `docs/wireframes.html`을 직접 열면 됩니다.

GitHub은 저장소 내 HTML을 보안상 직접 렌더링하지 않으므로, 위 프록시 링크를 사용합니다.

## 시스템 개요

4단계 파이프라인 구성:

```
증거 수집 → 자산 식별 → 위험도 평가 → 전환 계획
(Evidence)  (Asset ID)   (Risk)      (Migration)
```

핵심 결정사항:

- **Network Scanner (필수) + Agent (옵션)** — 외부 스캔이 기본, Agent는 capability 확장
- **CBOM Snapshot** — 스캔 1회당 CycloneDX 1.6 기반 스냅샷 1개, 영구 보관 및 diff 비교
- **Risk Score** — 0–100 점수 + Critical/High/Medium/Low 등급
- **Migration Plan** — v1은 권고안/시뮬레이션, 실제 전환 실행은 v2
- **스택** — Backend: Django + Django Ninja + Celery + Redis + PostgreSQL 16 / Frontend: React 18 + TS + Vite + TanStack Query + shadcn/ui

## 문서 구성

| 파일 | 내용 |
|---|---|
| [00-overview.md](docs/00-overview.md) | 프로젝트 정보, 범위, 결정사항 요약 |
| [01-architecture.md](docs/01-architecture.md) | 컴포넌트 아키텍처, 데이터 흐름, 배포 토폴로지 |
| [02-testbed.md](docs/02-testbed.md) | 테스트베드 9종 서비스 명세, 의도된 취약점 매트릭스 |
| [03-network-scanner.md](docs/03-network-scanner.md) | Network Scanner 동작 명세, 프로토콜별 식별 로직 |
| [04-agent.md](docs/04-agent.md) | Agent 동작, 통신 프로토콜, 인증, 등록/트리거 흐름 |
| [05-cbom-schema.md](docs/05-cbom-schema.md) | CBOM 스키마 (CycloneDX 1.6 + 확장 필드) |
| [06-risk-model.md](docs/06-risk-model.md) | 위험도 평가 수식, 휴리스틱 테이블, 등급 매핑 |
| [07-data-model.md](docs/07-data-model.md) | DB 스키마 (Django models, ER 다이어그램) |
| [08-api-contract.md](docs/08-api-contract.md) | REST API 전체 (엔드포인트, 요청/응답 스키마) |
| [09-frontend-pages.md](docs/09-frontend-pages.md) | 페이지별 UI 구성, 컴포넌트, 라우팅 |
| [10-ux-flows.md](docs/10-ux-flows.md) | 주요 사용자 플로우 시퀀스 다이어그램 |
| [11-migration-plan.md](docs/11-migration-plan.md) | Migration Plan 페이지 명세 |
| [12-tech-stack.md](docs/12-tech-stack.md) | 라이브러리, 버전, 디렉토리 구조 |
| [13-glossary.md](docs/13-glossary.md) | 전체 용어 정의 |

## 기준 표준

- NIST SP 1800-38B — Quantum Readiness: Cryptographic Discovery
- CycloneDX 1.6 — CBOM (Cryptography Bill of Materials)
- NIST IR 8547 — PQC 전환 가이드
