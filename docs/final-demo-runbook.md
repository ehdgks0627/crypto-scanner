# 최종 시연 실행 체크리스트

## 1. 초기화

```bash
./demo-reset.sh
```

필요하면 전체 DB를 먼저 비운다.

```bash
DEMO_FLUSH_DB=1 ./demo-reset.sh
```

배포 서버에서 Docker Compose만 사용하려면 다음처럼 실행한다.

```bash
DEMO_RUNNER=compose ./demo-reset.sh
```

## 2. 접속

- 기본 로컬 URL: `http://localhost:8088/demo`
- 배포 URL: `https://pqc.sprout.kr/demo`

사이드바의 `최종 시연` 메뉴로도 진입할 수 있다.

## 3. 진행 순서

1. 대상 등록: 탐색 대상 13개와 `srv-01` 라벨을 확인한다.
2. Agent 실행: Discovery Agent 28개, Host Agent 24개, 중복 5개를 확인한다.
3. Enriched CBOM: 총 47개 자산과 `srv-01:443/tls` JSON을 확인한다.
4. AI 위험도 평가: P1 12개, P2 8개, P3 27개 및 `srv-01` 9.2/P1을 확인한다.
5. PQC 매핑 추천: P1/P2 기반 추천 20개를 확인하고 export 한다.
6. 가용성 검증: handshake 100%, latency 42ms -> 54ms, failure 0건을 확인한다.

각 단계는 화면 오른쪽 위 `다음 단계` 버튼으로 진행한다.

## 4. 발표 백업 녹화

```bash
DEMO_URL=https://pqc.sprout.kr/demo ./record-demo.sh
```

기본 녹화 시간은 300초이다. 조정이 필요하면 `DEMO_RECORD_SECONDS`를 사용한다.

```bash
DEMO_RECORD_SECONDS=420 ./record-demo.sh
```

## 5. 발표 직전 점검

- `./demo-reset.sh` 실행 완료
- `/demo` 페이지 접속 가능
- `다음 단계` 버튼으로 6단계까지 진행 가능
- CBOM, PQC 추천, 가용성 검증 export 버튼 동작
- 백업 영상 생성 완료
