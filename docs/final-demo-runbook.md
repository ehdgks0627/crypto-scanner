# 실제 사이트 시연 실행 체크리스트

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

- 기본 로컬 URL: `http://localhost:8088/dashboard`
- 배포 URL: `https://pqc.sprout.kr/dashboard`
- 인증: 운영 프록시나 API 토큰을 배포 서버에 붙인 경우 발표 전에 먼저 로그인한다.
- 예상 소요 시간: 발표자가 화면을 따라 설명하는 전체 시연은 보통 5분 이내이다.

첫 화면은 실제 대시보드이다. 별도 `/demo` 전용 화면은 사용하지 않는다.

## 3. 진행 순서

1. 대시보드에서 `시연 데이터 로드`를 눌러 가데이터를 주입한다.
2. 탐색 대상 화면에서 CIDR, 특정 IP / 도메인 입력 UI와 발견 작업 목록을 설명한다.
3. 발견 상세에서 엔드포인트 승인 흐름을 설명하고, 이미 주입된 스캔 대상 목록을 확인한다.
4. 스캔 실행 화면에서 스캔 대상과 스캐너 선택 흐름을 설명한다.
5. 식별 자산 화면에서 CBOM 스냅샷, 자산 상세, 알고리즘/인증서/키 정보를 확인한다.
6. 위험평가와 Review Targets 화면에서 우선 전환 검토 대상을 확인한다.
7. 가용성 검사 화면에서 연결 성공 여부, 지연, 실패율 등 검증 지표를 확인한다.

## 4. 발표 백업 녹화

```bash
DEMO_URL=https://pqc.sprout.kr/dashboard ./record-demo.sh
```

기본 녹화 시간은 300초이다. 조정이 필요하면 `DEMO_RECORD_SECONDS`를 사용한다.

```bash
DEMO_RECORD_SECONDS=420 ./record-demo.sh
```

녹화 결과는 기본적으로 `demo-recordings/demo-YYYYmmdd-HHMMSS.mp4`에 저장된다. 발표 장애 시에는 가장 최신 mp4 파일을 대체 영상으로 사용한다.

## 5. 발표 직전 점검

- `./demo-reset.sh` 실행 완료
- `/dashboard` 페이지 접속 가능
- 대시보드의 `시연 데이터 로드` 버튼 동작
- 탐색 대상, 스캔 대상, 식별 자산, 위험평가, Review Targets, 가용성 검사 화면 접속 가능
- 백업 영상 생성 완료: `demo-recordings/` 아래 최신 mp4 확인
