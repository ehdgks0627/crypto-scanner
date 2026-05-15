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
