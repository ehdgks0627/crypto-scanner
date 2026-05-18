# 06. 위험도 평가 모델 명세

## 6.1 개요

본 시스템은 발견된 암호자산에 **위험도 점수(Risk Score)** 와 **등급(Risk Tier)** 을 부여한다. 점수는 자산의 양자 취약성과 운영 컨텍스트를 결합한 휴리스틱 모델로 산출되며, 사용자는 결과를 토대로 PQC 전환 우선순위를 결정한다.

### 6.1.1 채택한 모델

발표자료에 제시된 정량 모델을 본 시스템의 휴리스틱으로 구체화한다.

```
Risk = Algorithm × Data × Exposure × Lifespan × Criticality
```

각 인자는 0 이상의 실수로, 곱셈 결과를 0~100 범위로 정규화하여 최종 점수로 변환한다.

### 6.1.2 결정사항 정리

| 항목 | 결정 |
|---|---|
| 점수 표현 | 0~100 점수 + 4단계 등급 (D-09, 7c) |
| 인자 결정 방법 | 휴리스틱(자동 추정) + 사용자 입력 (D-11) |
| 정성 분석 | LLM 인터페이스만 정의, 구현은 v2 (D-10, 18c) |
| 사용자 가중치 조정 | 지원 (Risk Assessment 페이지에서 슬라이더) |
| 평가 시점 | Scan Job 완료 직후 자동 산출 + 사용자 메타데이터 변경 시 재계산 |

## 6.2 인자 정의

### 6.2.1 Algorithm Factor (`A`)

자산이 사용하는 암호 알고리즘의 양자 취약성. **자동 추정** (사용자 입력 불필요).

| 알고리즘 분류 | A 값 | 비고 |
|---|---|---|
| RSA-1024, DSA-1024, DH-1024 | 1.0 | 이미 classical로도 위험 |
| RSA-2048, DSA-2048, DH-2048 (modp14) | 0.95 | 양자 취약, classical 강도 112bit |
| RSA-3072, DH-3072 (modp15) | 0.9 | 양자 취약, classical 강도 128bit |
| RSA-4096+ | 0.85 | 양자 취약 |
| ECDSA P-256, ECDH P-256 | 0.95 | 양자 취약 (Shor) |
| ECDSA P-384, ECDH P-384 | 0.9 | 양자 취약 |
| ECDSA P-521, ECDH P-521 | 0.85 | 양자 취약 |
| Ed25519, Ed448 | 0.9 | 양자 취약 |
| X25519, X448 | 0.9 | 양자 취약 |
| SHA-1 (signing) | 1.0 | 이미 classical로도 위험 |
| SHA-256, SHA-384, SHA-512 (hash only) | 0.05 | 양자 안전 (Grover로 50% 강도 감소만) |
| AES-128 (대칭) | 0.1 | Grover로 64bit 강도, 안전 마진 좁음 |
| AES-192/256 (대칭) | 0.05 | 양자 안전 |
| ChaCha20 | 0.05 | 양자 안전 |
| HMAC-* | 0.05 | 양자 안전 |
| ML-KEM-512/768/1024 | 0.0 | PQC 표준 |
| ML-DSA-44/65/87 | 0.0 | PQC 표준 |
| SLH-DSA-* | 0.0 | PQC 표준 |
| Falcon-* | 0.0 | PQC (선정됨) |
| Hybrid (X25519+ML-KEM-768 등) | 0.1 | 일시적 안전, classical 부분이 양자 취약 |
| **Unknown / 미식별** | 0.5 | 보수적 중간값 |

> 본 테이블은 시스템 코드에 정의된 사전 테이블이며, 사용자가 UI에서 조정 불가하다 (휴리스틱의 객관 영역). 새 알고리즘 추가는 시스템 업데이트로만 가능.

### 6.2.2 Data Factor (`D`)

자산이 보호하는 데이터의 민감도. **사용자 입력** 또는 **휴리스틱 추정** (Target 등록 시).

| 사용자 입력 값 | D 값 |
|---|---|
| `critical` | 1.0 |
| `high` | 0.8 |
| `medium` | 0.5 |
| `low` | 0.2 |
| (입력 없음) | 휴리스틱 추정 |

#### 휴리스틱 추정 규칙

사용자가 Target 등록 시 데이터 민감도를 입력하지 않은 경우, 다음 규칙으로 추정:

| 조건 | 추정 D |
|---|---|
| 프로토콜 = `db`, `postgresql` 류 | 0.8 (high) |
| 서비스 역할 = `auth`, `pki`, `kms` (사용자 명시 시) | 0.9 |
| 호스트네임에 `prod`, `production` 포함 | 0.7 |
| 이메일 (Mail) | 0.6 |
| 일반 웹 서비스 | 0.5 |
| 그 외 | 0.5 (medium) |

### 6.2.3 Exposure Factor (`E`)

자산의 외부 노출 정도. **자동 추정 + 사용자 override 가능**.

| 노출 분류 | E 값 |
|---|---|
| `public_internet` (공인 IP) | 1.0 |
| `dmz` (사용자 명시) | 0.7 |
| `internal_network` | 0.4 |
| `air_gapped` (사용자 명시) | 0.1 |
| (미상) | 0.5 |

#### 자동 추정 규칙

- Target IP가 RFC 1918 사설 대역 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) → `internal_network`
- 그 외 IPv4/IPv6 → `public_internet`
- IPv6 ULA (fc00::/7) → `internal_network`
- localhost/loopback → `internal_network`

> 본 캡스톤의 테스트베드는 모두 `internal_network`로 분류되지만, 시연 시 일부 Target을 사용자가 수동으로 `public_internet`으로 override할 수 있다.

### 6.2.4 Lifespan Factor (`L`)

자산이 보호하는 데이터의 보호 기간 (HNDL 공격 관점). **사용자 입력 필수** (Target 등록 시).

| 입력 값 (years) | L 값 |
|---|---|
| ≥ 25년 | 1.0 |
| 15~24년 | 0.85 |
| 10~14년 | 0.7 |
| 5~9년 | 0.5 |
| 1~4년 | 0.3 |
| < 1년 | 0.1 |
| (입력 없음) | 0.5 (5년 가정) |

> Lifespan은 NIST SP 1800-38B의 `harvest-now-decrypt-later` 위험 평가의 핵심 인자다. 데이터가 오래 보호되어야 할수록 양자 위협 시점에 도달할 가능성이 높다.

### 6.2.5 Criticality Factor (`C`)

자산이 속한 시스템/서비스의 중요도. **사용자 입력** 또는 **휴리스틱 추정** (Target 등록 시).

| 사용자 입력 값 | C 값 |
|---|---|
| `critical` | 1.0 |
| `high` | 0.75 |
| `medium` | 0.5 |
| `low` | 0.25 |
| (입력 없음) | 휴리스틱 추정 |

#### 휴리스틱 추정 규칙

| 조건 | 추정 C |
|---|---|
| 서비스 역할 = `auth`, `pki`, `kms`, `payment` | 1.0 |
| 서비스 역할 = `database` | 0.8 |
| 서비스 역할 = `mail`, `vpn`, `messaging` | 0.6 |
| 서비스 역할 = `web-frontend`, `api-gateway` | 0.7 |
| 그 외 / 미상 | 0.5 |

## 6.3 점수 산출 공식

### 6.3.1 원시 점수 (Raw Score)

```
raw = A × avg(D, E, L, C)
```

각 인자는 0~1 범위이므로 raw도 0~1.

### 6.3.2 정규화 (0~100)

```
score = round(raw × 100)
```

### 6.3.3 가중치 조정 (옵션)

Risk Assessment 페이지에서 사용자가 인자별 가중치를 조정 가능 (기본 모두 1.0).

```
X' = clamp(0.5 + (X - 0.5) × wX, 0, 1)
weighted_raw = A' × avg(D', E', L', C')
score = round(weighted_raw × 100)
```

각 가중치 `w_*`는 0.5 ~ 2.0 범위에서 슬라이더로 조정. 기본값 1.0.

> 0.5를 중립점으로 두는 이유: 가중치 1.0이 기본 동작과 동일하게 유지되며, 1.0 초과는 중립점에서 멀어진 신호를 강화하고 1.0 미만은 완화한다. A 계수는 PQC 적용 여부를 반영하는 gate로 사용하고, D/E/L/C는 운영 맥락을 평균해 특정 한 항목만으로 전체 점수가 과도하게 눌리지 않도록 한다.

### 6.3.4 등급 매핑 (Tier)

| Score 범위 | Tier |
|---|---|
| 80 ~ 100 | **Critical** |
| 60 ~ 79 | **High** |
| 30 ~ 59 | **Medium** |
| 0 ~ 29 | **Low** |

> 임계치는 시스템 설정으로 변경 가능. 위 값은 기본값.

## 6.4 자산 종류별 적용 규칙

모든 자산이 모든 인자를 의미 있게 가지지는 않는다. 자산 종류별로 적용 규칙이 다르다.

### 6.4.1 Algorithm Asset

- **A**: 6.2.1 테이블 직접 적용
- **D, E, L, C**: 자산이 속한 서비스/데이터의 값을 상속 (5.6 dependencies 그래프를 따라)
- 알고리즘 자산이 여러 서비스에서 공유되는 경우, 각 서비스별로 별개 자산으로 본다 (Network Scanner는 서비스별 자산을 분리 생성)

### 6.4.2 Certificate Asset

- **A**: 인증서의 SubjectPublicKey 알고리즘 + 서명 알고리즘 중 더 위험한 값
- **D, E, L, C**: 인증서가 사용되는 서비스의 컨텍스트 상속
- 추가 보정:
  - 만료 임박 (30일 이내): A에 +0.05
  - 이미 만료: A에 +0.1, 단 score는 100 cap
  - 자체 서명 (self-signed) 루트가 아닌 경우: A에 +0.05

### 6.4.3 Key Asset

- **A**: 키 알고리즘 + 키 길이 기준 (6.2.1)
- **D, E, L, C**: 키가 부착된 인증서/keystore의 컨텍스트 상속
- 사용자 키 (`ssh_userkey`)는 해당 호스트의 컨텍스트 상속

### 6.4.4 Protocol Asset

- **A**: 프로토콜이 사용한 알고리즘들의 **최댓값** (가장 위험한 인자가 전체 결정)
  - 예: TLS 1.3에서 X25519 + AES-256-GCM + Ed25519 → max(0.9, 0.05, 0.9) = 0.9
- **D, E, L, C**: Service의 컨텍스트 상속
- 추가 보정:
  - TLS 버전 < 1.2: A에 +0.05
  - 알려진 취약 cipher (RC4, 3DES, EXPORT-*): A에 +0.1

### 6.4.5 Keystore Asset

- **A**: 내부 entry들의 알고리즘 중 최댓값
- **D, E, L, C**: 호스트 컨텍스트 상속

### 6.4.6 Non-Cryptographic Assets (Host, Service, Data)

비암호 자산 자체는 위험도 점수를 가지지 않는다. 단, 컨텍스트 인자(D, E, L, C)의 **값을 보유**하며, 암호자산이 의존성을 통해 상속한다.

## 6.5 컨텍스트 상속 알고리즘

자산 간 의존성 그래프를 따라 컨텍스트(D, E, L, C)를 전파한다.

```
inherit(asset):
    # 1. 자산이 직접 보유한 컨텍스트가 있으면 그것을 사용
    if asset has explicit (D, E, L, C):
        return (D, E, L, C)

    # 2. 의존하는 자산들의 컨텍스트를 수집
    parents = traverse dependencies (다중 단계 가능)
    contexts = []
    for p in parents:
        if p is Service or Data or Host:
            contexts.append(p.context)

    # 3. 다중 컨텍스트는 인자별 최댓값 채택 (보수적)
    if contexts:
        return max-by-factor(contexts)

    # 4. 부모 없으면 휴리스틱 default
    return default_context()
```

**원칙: 보수적 평가** — 한 자산이 여러 서비스에 사용된다면, 가장 민감/중요한 서비스 기준으로 평가한다.

## 6.6 정성 평가 (LLM, 18c)

정량 점수와 별개로, 자산별 LLM 기반 정성 분석 텍스트를 제공한다. 현재 구현은 기본적으로 결정론적 `mock-rulebook`을 사용하며, 환경변수로 OpenAI 호환 Chat Completions provider를 설정하면 실제 LLM 호출 결과를 같은 파서와 저장 경로로 처리한다.

### 6.6.1 인터페이스

```python
class LlmRiskAnalyzer(Protocol):
    def analyze(
        self,
        asset: AssetSnapshot,
        context: ContextFactors,
        related_assets: list[AssetSnapshot],
    ) -> QualitativeAssessment: ...

@dataclass
class QualitativeAssessment:
    summary: str               # 2~3문장 요약
    threat_scenarios: list[str]  # 구체적 공격 시나리오
    migration_recommendation: str
    confidence: float
    generated_at: datetime
    provider: str              # "mock" | "openai-gpt-4" | ...
```

### 6.6.2 Provider 구현

기본 구현 `mock-rulebook`은 정량 점수와 알고리즘 패밀리에 기반한 템플릿 문자열을 반환한다. 실제 provider 사용 시에는 `QUALITATIVE_LLM_PROVIDER=openai-compatible`, `QUALITATIVE_LLM_MODEL`, `QUALITATIVE_LLM_API_KEY`, `QUALITATIVE_LLM_BASE_URL`을 설정한다. provider 응답이 파싱 실패하거나 호출에 실패하면 같은 휴리스틱 결과로 폴백하여 전체 파이프라인은 계속 진행된다.

```python
def analyze(self, asset, context, related_assets):
    score = compute_risk(asset, context)
    family = asset.algorithm_family

    if score >= 80:
        summary = f"{family}는 양자 컴퓨터에 의해 높은 확률로 무력화될 수 있는 알고리즘이며, 이 자산은 운영 컨텍스트상 즉각적인 PQC 전환이 권고됩니다."
    elif score >= 60:
        summary = f"{family}는 양자 위협에 노출되어 있습니다. 데이터 보호 기간을 고려하여 전환 계획 수립이 필요합니다."
    elif score >= 30:
        summary = f"{family}는 양자 위협에 취약하나, 즉각적 위험은 낮습니다."
    else:
        summary = "현재 시점에서 양자 위협으로 인한 즉각적 위험은 낮습니다."

    return QualitativeAssessment(
        summary=summary,
        threat_scenarios=["Harvest-Now-Decrypt-Later", ...],
        migration_recommendation="Hybrid (X25519+ML-KEM-768)" if family in {"RSA","ECDH"} else "ML-DSA-65",
        confidence=0.5,
        provider="mock",
        generated_at=now(),
    )
```

### 6.6.3 호출 시점

- 사용자가 Asset Detail 페이지에서 "정성 분석 요청" 버튼 클릭 시 (지연 호출)
- 결과는 Asset당 1개 DB 레코드로 저장한다. 재요청 시 기존 레코드를 갱신해 반환한다.

## 6.7 위험도 데이터 영속화

### 6.7.1 RiskScore 레코드

각 자산 × 스냅샷 조합당 1개의 위험도 레코드.

```python
@dataclass
class RiskScore:
    id: int
    asset_id: int
    snapshot_id: int
    factor_a: float
    factor_d: float
    factor_e: float
    factor_l: float
    factor_c: float
    raw: float
    score: int                 # 0~100
    tier: RiskTier             # CRITICAL | HIGH | MEDIUM | LOW
    weights: dict[str, float]  # 가중치 스냅샷 (재현성)
    computed_at: datetime
    qualitative: QualitativeAssessment | None
```

### 6.7.2 CBOM에서의 표현

CBOM의 자산 컴포넌트 `properties`에 `risk:*` 네임스페이스로 부착된다.

```json
{
  "type": "crypto-asset",
  "bom-ref": "alg-rsa-2048-tls-web",
  "properties": [
    {"name": "risk:score", "value": "84"},
    {"name": "risk:tier", "value": "critical"},
    {"name": "risk:factor_a", "value": "0.95"},
    {"name": "risk:factor_d", "value": "0.8"},
    {"name": "risk:factor_e", "value": "0.4"},
    {"name": "risk:factor_l", "value": "0.85"},
    {"name": "risk:factor_c", "value": "0.75"}
  ]
}
```

## 6.8 재계산 트리거

다음 이벤트에서 위험도가 재계산된다.

| 이벤트 | 영향 범위 |
|---|---|
| Scan Job 완료 | 해당 Snapshot의 모든 자산 |
| Target 컨텍스트 수정 (D, L, C) | 해당 Target의 자산들 (모든 활성 Snapshot) |
| Asset 컨텍스트 override | 해당 Asset만 |
| 가중치 조정 (Risk Assessment 페이지) | 사용자가 "재계산" 버튼 클릭 시, 사용자가 선택한 Snapshot의 모든 자산 |
| 알고리즘 테이블 시스템 업데이트 | 명세 외 (시스템 운영 작업) |

> 재계산은 비동기 작업으로 큐잉되며, 진행 상황은 Job 시스템으로 노출된다.

## 6.9 Top-N 우선순위 산출

Risk Assessment 페이지의 핵심 기능은 "Top-N 위험 자산" 리스트.

```
SELECT asset, risk_score
FROM RiskScore
WHERE snapshot_id = :snapshot
ORDER BY score DESC, factor_l DESC, factor_c DESC
LIMIT :n
```

동점 처리:
- 1차 정렬: `score`
- 2차: `factor_l` (HNDL 위협 우선)
- 3차: `factor_c` (시스템 중요도)
- 4차: `asset.created_at` (오래된 자산 우선, FIFO)

## 6.10 위험도 히스토리

스냅샷 간 위험도 변화 추적 (17b CBOM Diff와 연계).

- Asset Detail 페이지에 "Risk Score Trend" 라인 차트
- X축: Snapshot 시간, Y축: Score
- 자산 동일성 판정은 5.9.2의 자연 키 사용
