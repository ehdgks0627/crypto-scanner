# Comparison Claim Evidence

이 문서는 발표 비교표에서 우리 시스템의 기능을 `○`로 표시할 때 필요한 구현 근거를 정리한다. 수치가 필요한 항목은 별도 JSON 근거 파일과 테스트로 고정한다.

## 16.1 Host Agent 내부 점검

`호스트 내부 점검(잠든 키 포함)` 주장은 데모 시드 기준으로 다음 근거에 한정해 말한다.

| 근거 | 값 |
| --- | ---: |
| Host Agent 후보 호스트 | 10개 |
| Agent 활성화 스캔 대상 | 10개 |
| Host Agent scanner 종류 | 8개 |
| Host Agent 실행 로그 | 80개 |
| 잠든 개인키 자산 | 3개 |

구조화된 근거는 `docs/kpi/host-agent-evidence.json`에 둔다. 테스트는 이 파일의 범위와 실제 데모 시드 상수를 비교하고, `seed_testbed_demo --reset` 실행 후 최신 스냅샷에 Host Agent 실행 로그와 잠든 개인키 자산이 생성되는지 확인한다.

발표에서는 다음 수준으로 제한한다.

> 네트워크에서 보이지 않는 호스트 내부 인증서, 키 파일, SSH 설정, 애플리케이션 TLS 설정은 Host Agent가 보완적으로 수집합니다. 데모 기준으로 Agent 대상 10개 호스트에서 내부 점검 로그가 생성되고, 사용되지 않는 개인키 3개를 원문 없이 메타데이터로 식별합니다.

주의할 점은 이 항목이 모든 운영체제와 모든 애플리케이션 설정을 완전하게 커버한다는 의미가 아니라는 것이다. 현재 근거는 테스트베드와 구현된 scanner capability 범위에 대한 실제 동작 증거이다.

## 16.2 AI 자동 위험 평가

`AI 자동 위험 평가` 주장은 OpenAI 호환 LLM provider를 사용할 수 있는 코드 경로와 구조화 저장 경로가 구현되어 있다는 의미로 제한한다. 외부 API 키가 설정되지 않은 시연 환경에서는 동일한 prompt, parser, 저장 모델을 사용하되 결정론적 rulebook 응답 또는 fallback 응답으로 동작한다.

구조화된 근거는 `docs/kpi/llm-risk-evidence.json`에 둔다. 테스트는 다음 흐름을 확인한다.

| 근거 | 확인 내용 |
| --- | --- |
| LLM provider adapter | OpenAI Chat Completions 형식으로 `/chat/completions` 요청을 만든다 |
| Prompt schema | `qualitative-risk-v7` prompt에 자산, 컨텍스트, 운영 맥락, risk 정보를 포함한다 |
| Response parser | 자유 텍스트 안의 JSON을 추출해 `summary`, `threat_scenarios`, DHS 6기준, `confidence`로 정규화한다 |
| Persistence | provider 응답을 `QualitativeAssessment`로 저장하고 provider/model/usage metadata를 남긴다 |
| Fallback | provider 오류나 파싱 실패가 전체 작업을 막지 않고 rulebook fallback으로 완료된다 |

발표에서는 다음 수준으로 제한한다.

> 위험평가는 단순 점수 계산에 그치지 않고, 자산 메타데이터와 운영 맥락을 LLM prompt로 구성해 DHS 6기준 형태의 정성 분석 결과로 저장합니다. 외부 LLM이 설정되어 있으면 OpenAI 호환 API 응답을 사용하고, 미설정 또는 실패 시에는 동일한 저장 경로로 rulebook fallback을 사용해 파이프라인이 멈추지 않게 했습니다.

주의할 점은 라이브 발표에서 실제 외부 LLM 호출을 보여주지 않는다면 “실제 상용 LLM이 시연 중 호출되었다”고 말하면 안 된다는 것이다. 정확한 표현은 “외부 LLM provider 연동 경로가 구현되어 있고, 테스트에서 provider 응답이 구조화 저장되는 것을 검증했다”이다.

## 16.3 오픈 및 시연 가능성

`오픈 · 시연 가능` 주장은 공개 리포지토리 접근성과 라이브 대시보드 접근성이 확인되었다는 의미로 제한한다. 구조화된 근거는 `docs/kpi/open-demo-evidence.json`에 둔다.

확인한 항목은 다음과 같다.

| 항목 | URL | 결과 |
| --- | --- | --- |
| GitHub 리포지토리 | `https://github.com/ehdgks0627/crypto-scanner` | HTTP 200, public metadata 확인 |
| Raw README | `https://raw.githubusercontent.com/ehdgks0627/crypto-scanner/main/README.md` | HTTP 200 |
| Live health API | `https://pqc.sprout.kr/api/health` | HTTP 200, api/database/redis/worker `ok` |
| Live dashboard | `https://pqc.sprout.kr/dashboard` | HTTP 200, `PQC Risk Assessment` title 확인 |

발표에서는 다음 수준으로 제한한다.

> 리포지토리는 공개 접근 가능하고, 발표용 대시보드는 `pqc.sprout.kr/dashboard`에서 열 수 있습니다. 발표 직전에는 health check를 다시 실행해 API, DB, Redis, worker 상태를 확인합니다.

주의할 점은 이 근거가 영구적인 가동률을 보장하지 않는다는 것이다. 또한 로컬 브랜치가 `origin/main`보다 앞선 상태라면 새 커밋이 아직 배포되지 않았을 수 있으므로, 발표 직전에는 push 이후 health/dashboard 확인을 다시 수행해야 한다.

## 16.4 소요 시간 분 단위 측정

`소요 시간 "분" 단위` 주장은 데모 시드의 작업 timestamp에서 자동 계산되는 값에 한정한다. 구조화된 근거는 `docs/kpi/runtime-minutes-evidence.json`에 둔다.

| 측정 항목 | 값 | 산출 방식 |
| --- | ---: | --- |
| Discovery 실행 시간 | 2분 | Discovery `AsyncJob.started_at/finished_at` 차이 |
| 자동 자산화 실행 시간 | 6분 | 최신 CBOM 스냅샷과 연결된 Scan Job timestamp 차이 |
| Risk recompute 실행 시간 | 1분 | Recompute `AsyncJob.started_at/finished_at` 차이 |
| 전체 파이프라인 | 9분 | Discovery + Scan + Recompute 합산 |

발표에서는 다음 수준으로 제한한다.

> 현재 데모 데이터 기준으로 자동 자산화는 6분, 탐색부터 위험 재계산까지의 전체 파이프라인은 9분으로 기록되어 대시보드에서 분 단위로 확인할 수 있습니다.

주의할 점은 이 값이 데모 시드의 timestamp 기반 측정값이라는 것이다. 실제 운영 환경에서는 대상 수, 네트워크 지연, 타임아웃, 선택한 scanner 조합, Agent 응답성에 따라 달라질 수 있다.

## 16.5 코드 정적 분석 표기

`코드 정적 분석` 항목은 `○`가 아니라 `△`로 표시한다. 현재 구현은 일반 소스코드 저장소를 분석하는 SAST가 아니라, Host Agent가 접근 가능한 파일과 설정을 정적으로 읽어 암호자산 후보를 수집하는 수준이다. 구조화된 근거는 `docs/kpi/static-analysis-evidence.json`에 둔다.

지원되는 범위는 다음과 같다.

| 범위 | 지원 방식 |
| --- | --- |
| 애플리케이션 TLS 설정 | `agent.app_config`가 nginx, Apache, Postfix, PostgreSQL, JWKS, properties 파일을 읽음 |
| 인증서 파일 | `agent.app_cert_files`, `agent.cert_store`가 인증서 파일을 파싱 |
| 개인키 파일 | `agent.private_key_files`가 원문 없이 알고리즘, 크기, 지문, dormant 여부를 수집 |
| Keystore 및 패키지 키 | `agent.keystore`, `agent.pkg_keyring`이 알려진 경로의 키 저장소와 서명키를 점검 |
| SSH 설정/사용자 키 | `agent.ssh_config`, `agent.ssh_userkey`가 SSH 정책과 authorized_keys를 점검 |

발표에서는 다음 수준으로 제한한다.

> 소스코드 정적 분석은 완전 지원이 아니라 제한적 지원입니다. 현재는 Host Agent가 설정 파일, 인증서 파일, 개인키 파일, keystore를 읽어 암호 사용 증거를 찾는 수준이므로 비교표에서는 △로 표기합니다.

주의할 점은 이 기능을 언어별 crypto API 호출 추적, dataflow 분석, 일반 SAST, 자동 수정 패치 생성으로 설명하면 안 된다는 것이다.

## 16.6 PQC 전환 범위 표기

`PQC 전환` 항목은 실제 운영 환경의 키나 설정을 자동 변경하는 의미로 설명하지 않는다. 현재 구현은 자산별 알고리즘 매핑 추천, 영향도 산정, 보고서 다운로드, CBOM annotation 부착까지이며, 실행 자동화는 향후 확장 범위다. 구조화된 근거는 `docs/kpi/migration-scope-evidence.json`에 둔다.

지원되는 범위는 다음과 같다.

| 범위 | 지원 방식 |
| --- | --- |
| 알고리즘 매핑 추천 | `migration_engine/mapping_rules.json`의 규칙을 통해 현재 알고리즘과 자산 용도에 맞는 PQC 후보를 산출 |
| LLM 후보 선택 | Review Targets의 `AI 추천`은 Enriched CBOM과 허용 후보군을 LLM에 전달하고, 응답이 후보 목록 안에 있을 때만 목표 알고리즘에 적용 |
| 전환 후보 검토 | `GET /api/snapshots/{snapshot_id}/migration-plan`으로 자산별 권고, 단계, 근거, 차단 요인, 검증 항목을 반환 |
| 영향도 산정 | `GET /api/snapshots/{snapshot_id}/migration-plan/impact`로 선택 자산 기준 호스트, 서비스, 예상 작업량을 계산 |
| 보고서 생성 | 프론트엔드가 선택 자산과 영향도 데이터를 Markdown 보고서로 직렬화 |
| CBOM 첨부 | CBOM export에 `migration.*` property와 migration plan annotation을 포함 |

발표에서는 다음 수준으로 제한한다.

> PQC 전환은 자동 실행이 아니라 매핑 추천과 검토 단계까지 구현했습니다. 시스템은 정책 기반 후보군을 만들고, 필요한 경우 Enriched CBOM을 바탕으로 LLM이 허용 후보 중 전환 전략을 선택하도록 합니다. 다만 인증서 재발급, 키 교체, 서비스 설정 변경은 수행하지 않습니다.

주의할 점은 이 기능을 운영 서버의 OpenSSL 설정 변경, oqs-provider 배포, 인증서 자동 재발급, 서비스 재시작, 롤백 자동화로 설명하면 안 된다는 것이다.

## 16.7 CryptoScan 비교 사실 확인

`CryptoScan (csnp/cryptoscan)`은 코드베이스, 설정 파일, 의존성 매니페스트를 정적으로 스캔해 암호 사용과 양자 위험을 찾는 도구로 확인했다. 비교표에서는 `코드 정적 분석` 계열 도구로 분류하고, 네트워크 엔드포인트 Discovery나 가용성 검사 도구로 설명하지 않는다. 구조화된 근거는 `docs/kpi/cryptoscan-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 공식 설명 | README가 “codebase” 안의 cryptographic algorithm 발견을 전면 설명 |
| 툴킷 내 역할 | QRAMM Toolkit 표에서 CryptoScan은 source code discovery, TLS-Analyzer는 TLS/SSL configuration analysis로 분리 |
| 입력 대상 | 로컬 디렉터리, 단일 파일, 원격 Git 저장소 |
| 분석 방식 | Git URL은 임시 디렉터리로 clone한 뒤 디렉터리/파일을 스캔 |
| 출력 | JSON, SARIF, CBOM 등 |
| 추가 범위 | 설정 파일, 의존성 매니페스트, source code context, quantum risk classification |

발표에서는 다음 수준으로 제한한다.

> CryptoScan은 코드베이스와 설정, 의존성에서 암호 사용을 찾는 정적 분석 도구입니다. 반면 우리 시스템은 운영 서비스의 네트워크 탐색, Host Agent 기반 런타임 자산 수집, CBOM 스냅샷, 가용성 검사까지 하나의 흐름으로 묶은 점을 차별점으로 둡니다.

주의할 점은 CryptoScan을 TLS/SSH/IKE 네트워크 탐색, 핸드셰이크 측정, 전환 후 가용성 검사 도구로 설명하면 안 된다는 것이다. 같은 QRAMM Toolkit 안에서도 TLS/SSL 설정 분석은 별도 TLS-Analyzer로 분리되어 있다.

## 16.8 IBM CBOMkit 비교 사실 확인

`IBM CBOMkit`은 CBOM 생성, 조회, 저장, 정책 검증을 위한 도구 모음이며, 암호자산 탐지는 소스코드, Git 저장소, 파일시스템, 컨테이너 이미지 분석에 기반하는 것으로 확인했다. 비교표에서는 CBOM 생성/관리와 정적 자산 탐지 계열로 분류하고, 네트워크 트래픽 분석 도구로 설명하지 않는다. 구조화된 근거는 `docs/kpi/cbomkit-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| IBM 원 출처 | IBM/CBOM README가 CBOMkit, Sonar Cryptography Plugin, CBOM Viewer, CBOMkit-theia, CBOMkit-action을 CBOM 관련 도구로 열거 |
| CBOMkit 본체 | CBOM 생성, Viewer, Compliance Check, Database/REST API 제공 |
| 입력 대상 | Git URL, PURL, 업로드된 CBOM |
| 소스코드 분석 | CBOMkit-hyperion/Sonar Cryptography Plugin이 소스코드 내 cryptographic usage를 식별 |
| 파일/이미지 분석 | CBOMkit-theia가 directory와 container image에서 인증서, 키, secret, OpenSSL 설정 등을 탐지 |
| 미확인 범위 | pcap 수집, packet capture, live TLS/SSH/IKE handshake 측정, 네트워크 트래픽 분석 |

발표에서는 다음 수준으로 제한한다.

> IBM CBOMkit은 CBOM을 만들고 보고 정책 검증까지 이어주는 도구 모음입니다. 소스코드, Git 저장소, 파일시스템, 컨테이너 이미지에서 암호자산을 찾는 기능은 확인되지만, 패킷 캡처 기반 네트워크 트래픽 분석이나 live handshake 검사는 확인되지 않았습니다.

주의할 점은 CBOMkit을 네트워크 Discovery, TLS/SSH/IKE probe, 가용성 검사 도구로 설명하면 안 된다는 것이다. 우리 시스템과 비교할 때는 “운영 네트워크에서 실제 서비스 엔드포인트를 탐색하고 연결 가능성을 검사하는 흐름”을 차별점으로 둔다.

## 16.9 SandboxAQ AQtive Guard 비교 사실 확인

`SandboxAQ AQtive Guard`는 상용 플랫폼으로 분류한다. 공식 자료에서는 데모/무료체험 기반 접근, AI 기반 분석, 위험 우선순위화, cryptographic posture management, live network traffic/TLS handshake/runtime tracing, PQC impact simulation을 명시한다. 따라서 비교표에서는 `AI 평가`, `상용 플랫폼`, `cryptographic inventory`, `runtime/network visibility` 항목을 `○`로 인정하고, 오픈소스 또는 공개 시연형 PoC로 설명하지 않는다. 구조화된 근거는 `docs/kpi/aqtive-guard-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 접근 방식 | Book a Demo, Get a Demo, Free Trial 중심의 상용 제품 접근 |
| 공개 소스 여부 | 공식 자료와 GitHub 검색 기준 공개 제품 소스 리포지토리는 확인하지 못함 |
| AI 평가 | AI-powered insights, risk analysis, context-aware risk, security knowledge graph correlation 명시 |
| 암호자산 관리 | cryptographic inventory, keys/certificates/operations, CBOM/compliance reporting, PQC migration planning |
| 네트워크/runtime | live network traffic, TLS handshakes, runtime cryptographic operations, network cipher suites 명시 |
| remediation | impact simulation, key rotation, algorithm replacement, automated remediation/lifecycle management 명시 |

발표에서는 다음 수준으로 제한한다.

> AQtive Guard는 SandboxAQ의 상용 보안 플랫폼으로, AI 기반 위험 분석과 암호자산 관리, 네트워크/runtime 가시성까지 공식적으로 제공한다고 설명되어 있습니다. 우리 프로젝트는 이 상용 제품을 대체한다고 주장하지 않고, NIST SP 1800-38 절차를 공개 리포지토리와 재현 가능한 테스트베드에서 직접 실험해볼 수 있게 만든 시연형 구현이라는 점을 차별점으로 둡니다.

주의할 점은 AQtive Guard를 단순 정적 스캐너로 낮춰 설명하면 안 된다는 것이다. 반대로 우리 시스템이 상용 제품의 네트워크/runtime 분석, 자동 remediation, 운영 규모를 능가한다고 말해서도 안 된다.
