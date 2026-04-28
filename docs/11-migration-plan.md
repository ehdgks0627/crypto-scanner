# 11. Migration Plan 명세

## 11.1 개요

Migration Plan은 발견된 양자취약 자산에 대한 **권장 PQC 전환 전략**을 자동 생성하여 보고서 형태로 제공한다. 본 캡스톤(v1)에서는 **권고/시뮬레이션만 수행**하며 실제 전환 실행은 v2(D2 단계)로 미룬다.

### 11.1.1 결정사항 정리

| 항목 | 결정 |
|---|---|
| 범위 | 권고안 + 시뮬레이션 보고서만 (D-14, 8c) |
| 권고 결정 방식 | **사전 정의 룰 매핑** (단순/명시적) + 자산 컨텍스트 보정 |
| LLM 사용 | 정성 분석 텍스트 생성에만 사용 (Mock, 6.6과 동일 인터페이스) |
| 사용자 수동 선택 | 자산별 권고 알고리즘을 사용자가 변경 가능 (v2 옵션) |
| 보고서 형식 | Markdown (v1), PDF (v2) |
| Plan 영속화 | 사용자가 "Plan에 추가"한 자산 목록은 클라이언트 상태로만 유지 (v1). 서버 영속화는 v2 |

### 11.1.2 v1 / v2 범위 분리

| 기능 | v1 | v2 |
|---|---|---|
| 자산별 권고 알고리즘 산출 | ✓ | (확장) |
| 영향 분석 (서비스/호스트 집계) | ✓ | |
| Markdown 보고서 다운로드 | ✓ | |
| 권고 알고리즘 사용자 변경 | (읽기 전용) | ✓ |
| Plan 서버 영속화 + 버전 관리 | ✗ | ✓ |
| 실제 전환 실행 (인증서 재발급, 설정 수정, 재시작) | ✗ | ✓ (D2) |
| PDF 보고서 | ✗ | ✓ |
| 우선순위 자동 스케줄링 | ✗ | ✓ |

## 11.2 권고 알고리즘 결정 룰

### 11.2.1 자산 종류별 후보 매핑

| 현재 알고리즘 | 1차 후보 (Hybrid) | 2차 후보 (Replace) |
|---|---|---|
| RSA-1024/2048/3072/4096 (서명) | RSA-2048 + ML-DSA-65 (hybrid cert) | ML-DSA-65 |
| ECDSA P-256 (서명) | ECDSA P-256 + ML-DSA-65 (hybrid cert) | ML-DSA-65 |
| ECDSA P-384/521 (서명) | ECDSA P-384 + ML-DSA-87 (hybrid cert) | ML-DSA-87 |
| Ed25519 (서명) | Ed25519 + ML-DSA-65 | ML-DSA-65 |
| RSA (KEM/Encryption) | X25519 + ML-KEM-768 (hybrid KEM) | ML-KEM-768 |
| DH (modp14/modp15) | X25519 + ML-KEM-768 | ML-KEM-768 |
| ECDH P-256 | X25519 + ML-KEM-768 | ML-KEM-768 |
| ECDH P-384/521 | X448 + ML-KEM-1024 | ML-KEM-1024 |
| X25519 / X448 | X25519 + ML-KEM-768 | ML-KEM-768 |
| SHA-1 (signing) | (해시는 양자 영향 적지만 SHA-1은 classical로도 약함) | SHA-256+ |
| SHA-256/384/512 | (변경 불필요) | (변경 불필요) |
| AES-128 | AES-256 | AES-256 |
| AES-192/256 | (변경 불필요) | (변경 불필요) |
| Hybrid (이미 PQC 포함) | (변경 불필요) | 순수 PQC로 단순화 (옵션) |
| ML-KEM-*, ML-DSA-*, SLH-DSA-*, Falcon-* | (변경 불필요) | (변경 불필요) |

> 본 매핑은 현 시점(2026-04 기준)의 NIST 표준화 결과(FIPS 203/204/205)와 IETF의 hybrid 권고를 바탕으로 한다. 후보 알고리즘은 시스템 설정에 사전 정의된 코드 상수로 관리되며 향후 표준 변동 시 갱신.

### 11.2.2 전략 선택 룰 (Hybrid vs Replace)

자산의 운영 컨텍스트를 기반으로 1차/2차 중 추천 전략을 결정한다.

```
strategy_recommendation(asset):
    if algorithm.classical_strength_bits < 100:
        # RSA-1024 등 이미 약한 키 → 즉시 replace
        primary = "replace"
    elif asset.lifespan_years >= 10:
        # 장기 보호 데이터 → hybrid (호환성 + 미래 대비)
        primary = "hybrid"
    elif asset.exposure == "public_internet" and asset.criticality in {"high", "critical"}:
        # 공개 인터넷 + 중요 → 호환성 우선 hybrid
        primary = "hybrid"
    elif asset.service_role in {"pki", "auth", "kms", "payment"}:
        # 보안 중심 시스템 → hybrid (보수적)
        primary = "hybrid"
    else:
        # 일반 케이스 → hybrid (안전한 기본값)
        primary = "hybrid"

    return primary
```

### 11.2.3 자산 종류별 적용

| 자산 종류 | 권고 적용 |
|---|---|
| **Algorithm** | 위 매핑 직접 적용. 한 알고리즘이 여러 자산에 사용되면 자산별로 권고가 별개로 산출됨 (컨텍스트 다름) |
| **Certificate** | SubjectPublicKey 알고리즘 + 서명 알고리즘 각각에 권고. 인증서 재발급 단위로 묶음 |
| **Key** | 키 알고리즘에 권고. 인증서에 임베드된 키는 인증서 재발급에 포함 |
| **Protocol** | 프로토콜이 사용한 알고리즘들 중 양자취약한 것에 권고. 프로토콜 자체는 변경 없음 (TLS 1.3 유지) |
| **Keystore** | keystore 형식은 유지, 내부 entry 알고리즘별 권고 |
| **Non-Crypto (Host/Service/Data)** | 권고 대상 아님 (영향 분석에만 사용) |

### 11.2.4 사유(Rationale) 텍스트

각 권고에는 결정 사유를 자동 생성된 텍스트로 부착한다.

템플릿 예시:

```
"이 자산은 {algorithm} 알고리즘을 사용하며, 양자 컴퓨터의 {threat}에 의해 무력화될 수 있습니다.
보호 기간이 {lifespan}년이고 {criticality} 중요도의 자산이므로,
{strategy} 전략을 통해 {target_algorithm}으로의 전환이 권고됩니다."
```

LLM Mock(6.6)에서 더 풍부한 텍스트 생성 가능하지만, 본 v1에서는 결정론적 템플릿을 기본으로 사용. LLM 결과가 캐시되어 있으면 그것을 우선 표시.

## 11.3 영향 분석 (Impact Analysis)

선택된 자산들에 대해 다음을 자동 집계한다.

### 11.3.1 집계 항목

| 항목 | 설명 |
|---|---|
| 영향 받는 호스트 수 | 자산이 위치한 unique hostname |
| 영향 받는 서비스 수 | 자산이 의존성 그래프에서 연결된 unique service |
| 인증서 재발급 건수 | Certificate 자산 중 leaf 위치한 것의 수 (intermediate/root는 별도 카운트) |
| 설정 변경 건수 | Protocol/Algorithm 자산 중 사용자 설정 파일과 연결된 것 (Agent의 ssh_config/app_config로 발견된 자산) |
| 키 재생성 건수 | Key 자산 중 새로 생성이 필요한 것 |
| 추정 다운타임 | 호스트당 표준값: 5분 (정적 룰. v2에서 정교화) |

### 11.3.2 집계 알고리즘

```python
def impact_analysis(selected_assets):
    hosts = set()
    services = set()
    cert_reissues = 0
    config_changes = 0
    key_regens = 0

    for asset in selected_assets:
        # 호스트/서비스 수집 (의존성 그래프 traversal)
        for parent in traverse_up(asset, edge_types={"hosts", "uses_cert", "uses_algorithm"}):
            if parent.asset_class == "host":
                hosts.add(parent.bom_ref)
            elif parent.asset_class == "service":
                services.add(parent.bom_ref)

        # 작업량 카운트
        if asset.asset_type == "certificate" and asset.properties.get("internal:chain_position") == "leaf":
            cert_reissues += 1
        if asset.properties.get("internal:agent_capability") in {"ssh_config", "app_config"}:
            config_changes += 1
        if asset.asset_type == "key":
            key_regens += 1

    return ImpactAnalysis(
        hosts=hosts,
        services=services,
        cert_reissues=cert_reissues,
        config_changes=config_changes,
        key_regens=key_regens,
        estimated_downtime_min=len(hosts) * 5,
    )
```

## 11.4 데이터 모델 (Migration Recommendation)

본 v1에서는 영속화하지 않으며, API 응답 시 즉시 계산하여 반환한다 (read-only).

### 11.4.1 응답 객체

```python
@dataclass
class MigrationRecommendation:
    asset_id: int
    asset_name: str
    asset_type: str
    risk_score: int
    risk_tier: str

    current: AlgorithmInfo
    recommendation: Recommendation
    alternatives: list[Recommendation]

@dataclass
class AlgorithmInfo:
    algorithm: str             # "RSA-2048"
    key_size_bits: int | None
    quantum_vulnerable: bool

@dataclass
class Recommendation:
    strategy: str              # "hybrid" | "replace" | "no_change"
    target_algorithm: str      # "RSA-2048 + ML-DSA-65 (hybrid certificate)"
    rationale: str
    confidence: float          # 0.0~1.0, 룰 기반은 0.7~0.9 범위
    trade_off: str | None      # alternatives의 경우 trade-off 설명
```

## 11.5 보고서 생성

### 11.5.1 트리거

`/snapshots/{id}/migration` 페이지에서:
1. 사용자가 자산을 다중 선택 (또는 필터로 한정)
2. [📥 보고서 다운로드] 클릭
3. 클라이언트 또는 백엔드에서 Markdown 파일 생성

### 11.5.2 v1 구현 방식

**클라이언트 측 생성을 기본으로 한다.** 서버 저장/렌더링 API를 추가하지 않고, 이미 받은 `migration-plan` 응답과 `migration-plan/impact` 응답을 가공하여 Markdown으로 직렬화 후 Blob 다운로드.

```typescript
function generateMarkdownReport(
  snapshotId: number,
  selectedItems: MigrationRecommendation[],
  impact: ImpactAnalysis,
): string {
  // ...returns markdown string
}
```

> v2에서 PDF가 필요하면 백엔드에 `POST /api/snapshots/{id}/migration-plan/report` 추가하고 서버에서 PDF 렌더링.

### 11.5.3 보고서 구조

```markdown
# PQC Migration Plan Report

생성 일시: 2026-04-25 11:30:00
대상 Snapshot: #56 (2026-04-25 10:05)
대상 자산 수: 23

## 1. 요약

본 보고서는 양자 위협에 노출된 자산에 대한 전환 권고를 담고 있습니다.
- Critical: 8건
- High: 15건

영향 받는 호스트: 6
영향 받는 서비스: 9
인증서 재발급: 12건
설정 변경: 4건
추정 다운타임: 30분 (호스트당 5분 가정)

## 2. 자산별 권고

### 2.1 cert-leaf-db-rsa1024 (CRITICAL · 92)

- 자산 타입: certificate
- 위치: db.testbed.local:5432
- 현재 알고리즘: RSA-1024
- **권고**: ML-DSA-65 (replace)
- 대안: RSA-2048 + ML-DSA-65 (hybrid certificate)
- 사유: RSA-1024는 classical 환경에서도 이미 약하며, 양자 환경에서는 즉각 무력화됩니다.

### 2.2 cert-leaf-mail-rsa2048 (CRITICAL · 88)

- 자산 타입: certificate
- 위치: mail.testbed.local:993
- 현재 알고리즘: RSA-2048
- **권고**: RSA-2048 + ML-DSA-65 (hybrid certificate)
- 대안: ML-DSA-65 (replace)
- 사유: 보호 기간이 10년으로 길고, 메일 서비스의 호환성 유지가 필요합니다.

(...반복...)

## 3. 영향 분석

### 영향 받는 호스트
- web.testbed.local
- mail.testbed.local
- db.testbed.local
- ipsec.testbed.local
- ssh.testbed.local
- mqtt.testbed.local

### 영향 받는 서비스
- HTTPS @ web (2 자산)
- IMAPS @ mail (1 자산)
- SMTPS @ mail (1 자산)
- Submission @ mail (1 자산)
- POP3S @ mail (1 자산)
- PostgreSQL @ db (3 자산)
- IKEv2 @ ipsec (4 자산)
- SSH @ ssh (2 자산)
- MQTT @ mqtt (1 자산)

## 4. 작업량 요약

| 항목 | 건수 |
|---|---|
| 인증서 재발급 (leaf) | 12 |
| 인증서 재발급 (intermediate) | 2 |
| 키 재생성 | 8 |
| 서비스 설정 변경 | 4 |
| 추정 다운타임 (호스트당 5분) | 30분 |

## Appendix A. 위험도 인자 가중치 (재계산 시 적용된 값)

- Algorithm Factor: 1.0
- Data Factor: 1.0
- Exposure Factor: 1.0
- Lifespan Factor: 1.5
- Criticality Factor: 1.0

## Appendix B. 참고 표준

- NIST FIPS 203 (ML-KEM)
- NIST FIPS 204 (ML-DSA)
- NIST FIPS 205 (SLH-DSA)
- NIST SP 1800-38B (Cryptographic Discovery)
- IETF draft-irtf-cfrg-hybrid-kems
```

### 11.5.4 파일명

`migration-plan-snapshot-<id>-<yyyymmdd-hhmm>.md`

## 11.6 Migration Plan API (8.10 보강)

### 11.6.1 `GET /api/snapshots/{sid}/migration-plan`

자산별 권고 목록. 선택 자산 합산 영향 분석은 11.6.2의 별도 API로 조회한다.

쿼리 파라미터:
- `min_score`, `tier`, `asset_type`, `target_id`
- `asset_ids` (콤마 구분, 특정 자산 한정)
- `offset`, `limit`

응답: 8.10.1 명세 그대로.

### 11.6.2 `GET /api/snapshots/{sid}/migration-plan/impact`

선택된 자산들에 대한 영향 분석만 별도 조회.

쿼리 파라미터:
- `asset_ids` (콤마 구분, 필수)

응답:
```json
{
  "selected_count": 23,
  "hosts": ["web.testbed.local", "mail.testbed.local", "db.testbed.local"],
  "services": ["svc-web-https", "svc-mail-imaps", ...],
  "cert_reissues": 12,
  "config_changes": 4,
  "key_regens": 8,
  "estimated_downtime_min": 30
}
```

### 11.6.3 (v2) `POST /api/snapshots/{sid}/migration-plan/save`

사용자 정의 Migration Plan을 영속화. v1 미구현.

## 11.7 사용자 흐름과의 연계

10.9의 F7 Migration Plan 플로우와 함께 사용된다. v1에서 사용자는:

1. 페이지 진입 시 자동 권고 일람 확인
2. 필터(tier, type, target)로 좁히기
3. 자산 행 [상세] 펼쳐서 사유/대안 확인
4. [Plan에 추가] 클릭으로 클라이언트 상태에 누적
5. 영향 분석 박스가 실시간 갱신
6. [📥 보고서 다운로드]로 Markdown 다운로드

## 11.8 PQC-enabled TLS Server (테스트베드)와의 연계

테스트베드의 `pqc-tls.testbed.local` 서비스는 **이미 PQC가 적용된 자산의 참조 예시**다. 이 서비스에서 발견된 자산은 Migration Plan에서:

- `current.algorithm`이 ML-KEM-768, ML-DSA-65 등 PQC인 경우 → `recommendation.strategy = "no_change"`
- 사용자에게 "이 자산은 이미 PQC로 보호됩니다" 메시지 표시

이는 v1 보고서/UI가 양자 안전 자산도 정확히 분류함을 보여주는 시연 가치가 있다.

## 11.9 한계와 후속 과제

### 11.9.1 v1의 명시적 한계

- 권고 알고리즘은 사전 정의 룰 기반. 도메인 특화(예: 임베디드 환경의 ML-KEM-512 선택)는 반영되지 않음
- 추정 다운타임은 정적값. 실제는 서비스 종류/규모에 따라 변동
- 보고서는 Markdown만. 인쇄/공식 문서 형식은 v2

### 11.9.2 v2 후속 과제 (D2 단계)

- 실제 전환 실행: 인증서 재발급 (CA 호출 또는 OpenSSL/Bouncy Castle), 서비스 설정 자동 수정 (Ansible-style), 재시작 오케스트레이션
- 전환 전후 검증 (자동 재스캔 → diff 확인 → 회귀 검출)
- 실패 시 롤백
- 단계적 적용 (canary, blue-green)
- 사용자 정의 권고 알고리즘 매핑 UI
- PDF 보고서 + 회사 로고/서식
