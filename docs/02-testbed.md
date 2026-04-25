# 02. 테스트베드 명세 (Testbed Specification)

## 2.1 목적

테스트베드는 **의도적으로 다양한 양자취약 알고리즘을 노출**하여 식별 엔진의 검증 환경을 제공한다. 실제 운영 환경에 가까우면서도 식별 가능한 자산의 다양성을 최대화하는 것이 핵심이다.

## 2.1.1 운영 모델: Network 기본 + Agent 옵션

본 시스템이 가정하는 실제 기업 환경은 다음과 같다.

- **현실 가정**: 평가 대상 시스템(고객사)에 Agent를 배포하는 것은 **고객사 협조에 의존**한다. 보안 정책, 변경 통제, 운영 부담 등으로 항상 가능하지 않다.
- **기본 동작**: 따라서 본 시스템의 기본 식별 경로는 **외부에서의 Network Scan**이다. 별도 협조 없이 즉시 시작 가능해야 한다.
- **확장 동작**: 고객사가 Agent 배포에 동의한 호스트에 한해 Agent를 추가 설치하면, 인증서 저장소·미사용 키·설정 파일 등 네트워크로 보이지 않는 자산을 추가로 식별할 수 있다.

테스트베드는 이 두 시나리오를 한 환경에서 모두 시연하기 위해 **일부 서비스에는 Agent를 탑재하고, 일부에는 탑재하지 않는다**.

## 2.2 서비스 일람

| # | 서비스 | 호스트네임 | 포트 | 베이스 이미지 | Agent | 시연 시나리오 |
|---|---|---|---|---|---|---|
| 1 | HTTPS Web Server | `web.testbed.local` | 443/TCP | `nginx:1.27-alpine` | ✓ | 협조 가능 호스트 (Agent로 시스템 CA·미사용 인증서까지 식별) |
| 2 | PQC-enabled TLS Server | `pqc-tls.testbed.local` | 443/TCP | OQS Provider 기반 빌드 | ✗ | 외부 시점 스캔만 (전환 후 자산 참조 예시) |
| 3 | SSH Server | `ssh.testbed.local` | 22/TCP | `linuxserver/openssh-server` | ✓ | 협조 가능 호스트 (사용자 키·`authorized_keys`·`sshd_config` 정책 식별) |
| 4 | MQTT Broker | `mqtt.testbed.local` | 8883/TCP | `eclipse-mosquitto:2` | ✗ | 외부 시점 스캔만 |
| 5 | IPsec Gateway | `ipsec.testbed.local` | 500, 4500/UDP | `strongswan/strongswan` | ✗ | 외부 시점 스캔만 (IKE_SA_INIT 분석) |
| 6 | Mail Server | `mail.testbed.local` | 25, 465, 587, 993, 995/TCP | postfix+dovecot 자체 구성 | ✗ | 외부 시점 스캔만 (멀티 포트, 포트별 cert 다양성) |
| 7 | Database Server | `db.testbed.local` | 5432/TCP | `postgres:16` (TLS 활성) | ✓ | 협조 가능 호스트 (keystore·약한 키 파일까지 식별) |

**Agent 탑재 그룹** (3개): web, ssh, db
**Agent 미탑재 그룹** (4개): pqc-tls, mqtt, ipsec, mail

> **System CA Certificates** 와 **Package Repository Certificates** 는 별도 서비스가 아니라, **Agent가 탑재된 호스트에서 추가로 발견되는 자산 타입**이다. Agent 미탑재 호스트에서는 단순히 발견되지 않는 것이며, "식별 불가" 같은 별도 표기를 하지 않는다 (CBOM에는 발견된 자산만 들어간다).

## 2.3 네트워크 구성

### 2.3.1 IP/호스트 매핑 (예시)

| 호스트네임 | 컨테이너명 | 내부 IP |
|---|---|---|
| `dns.testbed.local` | `tb-dns` | 172.20.0.2 |
| `web.testbed.local` | `tb-web` | 172.20.0.10 |
| `pqc-tls.testbed.local` | `tb-pqc-tls` | 172.20.0.11 |
| `ssh.testbed.local` | `tb-ssh` | 172.20.0.12 |
| `mqtt.testbed.local` | `tb-mqtt` | 172.20.0.13 |
| `ipsec.testbed.local` | `tb-ipsec` | 172.20.0.14 |
| `mail.testbed.local` | `tb-mail` | 172.20.0.15 |
| `db.testbed.local` | `tb-db` | 172.20.0.16 |

### 2.3.2 호스트 노출 포트

호스트 머신에서 노출되는 포트는 시스템 스택이 외부에서 접근하기 위한 통로다.

| 호스트 포트 | 컨테이너 | 용도 |
|---|---|---|
| 5353/UDP | tb-dns | dnsmasq |
| 4430/TCP | tb-web | HTTPS (호스트 443 충돌 회피) |
| 4431/TCP | tb-pqc-tls | PQC TLS |
| 2222/TCP | tb-ssh | SSH |
| 8883/TCP | tb-mqtt | MQTT over TLS |
| 5000/UDP, 4500/UDP | tb-ipsec | IKE/IPsec |
| 2525, 4465, 5587, 9993, 9995 /TCP | tb-mail | Mail (호스트 충돌 회피) |
| 54320/TCP | tb-db | PostgreSQL |

> 시스템 스택의 Network Scanner는 dnsmasq를 통해 호스트네임 → 내부 IP를 직접 사용하므로, 위 호스트 포트는 외부 디버깅/검증용이다. 단, 시스템 스택을 호스트 머신에서 실행하는 경우 위 포트를 사용한다. **상세는 12장 배포 가이드 참고.**

## 2.4 의도된 취약점 매트릭스 (Vulnerability Matrix)

각 서비스는 식별 엔진 검증을 위해 **다양한 알고리즘 조합**을 노출한다. 이는 실제 운영 환경의 취약점이 아니라, **테스트 데이터로서 의도된 다양성**이다.

### 2.4.1 HTTPS Web Server (`web.testbed.local`)

| 항목 | 설정 |
|---|---|
| TLS 버전 | TLS 1.2 + TLS 1.3 둘 다 활성 |
| 가상 호스트 #1 | `web.testbed.local` — RSA-2048 leaf cert, RSA-4096 intermediate, RSA-4096 root |
| 가상 호스트 #2 | `web-ec.testbed.local` (SAN으로 추가) — ECDSA P-256 leaf, ECDSA P-384 intermediate, RSA-4096 root |
| Cipher suite (TLS 1.2) | `ECDHE-RSA-AES256-GCM-SHA384`, `ECDHE-ECDSA-AES128-GCM-SHA256`, `DHE-RSA-AES256-GCM-SHA384` |
| Cipher suite (TLS 1.3) | `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256` |
| ALPN | `h2`, `http/1.1` |

### 2.4.2 PQC-enabled TLS Server (`pqc-tls.testbed.local`)

| 항목 | 설정 |
|---|---|
| 구현 | OQS Provider 기반 nginx 또는 oqs-openssl |
| TLS 버전 | TLS 1.3 |
| KEM | `X25519`, `ML-KEM-768`, `X25519MLKEM768` (hybrid) |
| 인증서 | ML-DSA-65 leaf (서명 알고리즘), 또는 RSA-2048+ML-DSA-65 hybrid 인증서 |
| ALPN | `http/1.1` |
| 비고 | **시스템 스택은 이 서비스를 "전환 후" 자산의 참조 예시로 활용** |

### 2.4.3 SSH Server (`ssh.testbed.local`)

| 항목 | 설정 |
|---|---|
| 호스트 키 | RSA-2048 + ECDSA P-256 + Ed25519 모두 활성 |
| KEX 알고리즘 | `curve25519-sha256`, `ecdh-sha2-nistp256`, `diffie-hellman-group14-sha256` |
| 사용자 키 | 인증된 키 파일에 RSA + ECDSA + Ed25519 키 모두 등록 (Agent 식별용) |
| 인증 방식 | publickey, password 둘 다 활성 (테스트용) |

### 2.4.4 MQTT Broker (`mqtt.testbed.local`)

| 항목 | 설정 |
|---|---|
| 포트 | 8883 (TLS only, 평문 1883은 비활성) |
| TLS | TLS 1.2 + TLS 1.3 |
| 인증서 | RSA-2048 leaf (자체 서명 인증서로 단독 체인) |
| ALPN | `mqtt` (식별 엔진 Tier 1 검증용) |
| 클라이언트 인증 | 비활성 (단순화) |

### 2.4.5 IPsec Gateway (`ipsec.testbed.local`)

| 항목 | 설정 |
|---|---|
| 구현 | strongSwan |
| IKE 버전 | IKEv2 |
| IKE Proposal #1 | `aes256-sha256-modp2048` (DH Group 14, 양자취약) |
| IKE Proposal #2 | `aes256-sha384-ecp256` (ECDH P-256, 양자취약) |
| IKE Proposal #3 | `aes256-sha512-x25519` (X25519, 양자취약하나 PQC hybrid 후보) |
| 인증 | RSA-2048 인증서 기반 + PSK 폴백 |
| ESP Proposal | `aes256-sha256` |

### 2.4.6 Mail Server (`mail.testbed.local`)

| 포트 | 서비스 | TLS 모드 | 노출 자산 |
|---|---|---|---|
| 25 | SMTP | STARTTLS (opportunistic) | TLS 1.2, RSA-2048 cert |
| 465 | SMTPS | Implicit TLS | TLS 1.3, RSA-2048 cert |
| 587 | Submission | STARTTLS (required) | TLS 1.2/1.3, RSA-2048 cert |
| 993 | IMAPS | Implicit TLS | TLS 1.3, ECDSA P-256 cert (의도적으로 다른 알고리즘) |
| 995 | POP3S | Implicit TLS | TLS 1.2, RSA-2048 cert |

> 의도: 같은 서비스 내에서도 포트별로 다른 cert/version 사용. 식별 엔진의 멀티 포트 처리 검증.

### 2.4.7 Database Server (`db.testbed.local`)

| 항목 | 설정 |
|---|---|
| 구현 | PostgreSQL 16 |
| TLS | 필수 (`ssl=on`) |
| 인증서 | **RSA-1024 leaf** (의도적으로 약한 키, 약한 키 검출 검증) + 자체 서명 |
| TLS 버전 | TLS 1.2 (의도적으로 1.3 비활성) |
| 인증 | password (scram-sha-256) |

### 2.4.8 System CA Certificates (Agent 탑재 호스트 한정)

Agent가 탑재된 호스트(web, ssh, db) 내부의 시스템 CA 저장소를 추가로 식별한다. 미탑재 호스트에서는 이 자산이 단순히 보고되지 않는다.

스캔 경로:

| OS 계열 | 경로 |
|---|---|
| Debian/Ubuntu | `/etc/ssl/certs/ca-certificates.crt`, `/usr/local/share/ca-certificates/` |
| Alpine | `/etc/ssl/certs/`, `/usr/local/share/ca-certificates/` |
| RHEL/CentOS | `/etc/pki/tls/certs/`, `/etc/pki/ca-trust/source/anchors/` |

추가로 의도적으로 심을 인증서:
- 자체 발급 사내 CA 인증서 (RSA-4096) 1개를 Agent 탑재 컨테이너에 설치
- 만료 임박 인증서 1개 (식별 엔진의 만료일 메타데이터 추출 검증용)

### 2.4.9 Package Repository Certificates (Agent 탑재 호스트 한정)

Agent가 탑재된 호스트 내부의 패키지 리포지토리 키 저장소를 추가로 식별한다.

스캔 경로:

| OS 계열 | 경로 |
|---|---|
| Debian/Ubuntu | `/etc/apt/keyrings/`, `/etc/apt/trusted.gpg.d/`, `/etc/apt/trusted.gpg` |
| Alpine | `/etc/apk/keys/` |
| RHEL/CentOS | `/etc/pki/rpm-gpg/` |

심볼 의도:
- OpenPGP 공개키 (RSA-4096, EdDSA 등 다양한 알고리즘 혼재)
- 식별 엔진의 OpenPGP 키 파싱 검증

### 2.4.10 SSH 사용자 키 / 설정 (Agent 탑재 호스트 한정)

SSH 호스트(`ssh.testbed.local`)의 Agent가 추가로 식별:
- `~/.ssh/authorized_keys` 내 등록된 사용자 공개키 (RSA + ECDSA + Ed25519 혼합)
- `/etc/ssh/sshd_config`의 `KexAlgorithms`, `Ciphers`, `MACs`, `HostKeyAlgorithms` 정책 라인
- 미사용 호스트 키 파일 (예: `/etc/ssh/ssh_host_dsa_key.pub` 같은 레거시 잔재)

### 2.4.11 미사용 인증서 / 키스토어 (Agent 탑재 호스트 한정)

각 Agent 탑재 호스트에 의도적으로 미사용 자산을 심어 Agent의 가치를 입증:
- `web`: `/etc/nginx/ssl/legacy-rsa1024.pem` (서비스에 미연결, 약한 키)
- `db`: `/var/lib/postgresql/keystore.p12` (PKCS#12 keystore, 내부에 RSA-2048 키)

## 2.5 알고리즘 다양성 요약 (Algorithm Coverage Matrix)

| 알고리즘 | 사용처 |
|---|---|
| RSA-1024 | DB Server (의도적 약한 키) |
| RSA-2048 | HTTPS, MQTT, Mail, IPsec, SSH host key |
| RSA-4096 | HTTPS root CA, MQTT, Package Repo (PGP) |
| ECDSA P-256 | HTTPS (web-ec), Mail (993), SSH host key |
| ECDSA P-384 | HTTPS intermediate (web-ec) |
| Ed25519 | SSH host key, Package Repo (PGP) |
| DH (modp2048) | IPsec (Group 14) |
| ECDH P-256 | IPsec (ecp256), TLS ECDHE |
| X25519 | IPsec, TLS 1.3, SSH KEX |
| ML-KEM-768 | PQC-TLS Server |
| ML-DSA-65 | PQC-TLS Server |
| AES-128/256 GCM | TLS, IPsec ESP (대칭은 양자 안전 분류, 식별만 함) |
| ChaCha20-Poly1305 | TLS 1.3 cipher suite |

## 2.6 테스트베드 자체 docker-compose 구조

```
testbed/
├── docker-compose.yml
├── .env
├── dns/
│   └── dnsmasq.conf
├── certs/
│   ├── generate.sh           # 모든 인증서 일괄 생성
│   ├── ca/                   # 자체 CA
│   ├── web/, web-ec/, mqtt/, mail/, db/, ipsec/, pqc-tls/
├── services/
│   ├── web/                  # Agent 탑재
│   │   ├── Dockerfile        # nginx + agent
│   │   └── nginx.conf
│   ├── pqc-tls/              # Agent 미탑재
│   │   ├── nginx.conf
│   │   └── Dockerfile (oqs-provider 기반)
│   ├── ssh/                  # Agent 탑재
│   │   ├── Dockerfile
│   │   └── sshd_config
│   ├── mqtt/                 # Agent 미탑재
│   │   └── mosquitto.conf
│   ├── ipsec/                # Agent 미탑재
│   │   ├── ipsec.conf
│   │   └── ipsec.secrets
│   ├── mail/                 # Agent 미탑재
│   │   └── postfix/, dovecot/ 설정
│   └── db/                   # Agent 탑재
│       ├── Dockerfile
│       └── postgresql.conf, pg_hba.conf
└── agent/
    ├── Dockerfile             # Agent 베이스 (탑재 호스트 3개에서 사용)
    ├── agent.py
    └── requirements.txt
```

## 2.7 Agent 탑재 방식 (탑재 호스트 한정)

Agent를 탑재할 3개 호스트(web, ssh, db)에 한해, 두 가지 방식이 가능하다.

| 방식 | 설명 | 채택 |
|---|---|---|
| **사이드카 컨테이너** | 같은 네트워크 namespace에 Agent를 별도 컨테이너로 띄움 | 서비스 컨테이너의 파일시스템 접근을 위해 volume share 필요. 복잡함 |
| **컨테이너 내부 멀티 프로세스** | 서비스 컨테이너의 Dockerfile에 Agent 추가, supervisord/dumb-init로 동시 실행 | ✓ **채택** |

> 단순성과 파일시스템 직접 접근을 위해 **컨테이너 내부 멀티 프로세스**로 통일한다. Agent 탑재 호스트 3개의 베이스 이미지를 약간 확장하여 Agent를 함께 실행한다.

> 미탑재 호스트(pqc-tls, mqtt, ipsec, mail)는 베이스 이미지를 그대로 사용한다.

> Agent 상세는 `04-agent.md` 참고.

## 2.8 부트스트랩 절차

테스트베드 시작 시 자동 수행되는 작업:

1. `certs/generate.sh` 실행 → 모든 의도된 인증서 생성 (CA 포함, 키 길이/곡선 다양화)
2. dnsmasq 컨테이너 시작
3. 각 서비스 컨테이너 시작
4. **Agent 탑재 호스트(web, ssh, db)** 의 Agent가 백엔드의 `/api/agents/register` 호출 (백엔드 URL은 환경변수로 주입)
5. 백엔드가 Agent를 등록하고 토큰 발급 → Agent에 응답으로 전달

> 시스템 스택이 먼저 떠 있어야 Agent 등록이 성공한다. **시스템 스택 → 테스트베드 순으로 기동.**
> Agent 미탑재 호스트는 등록 단계 없이 그냥 기동만 한다.

## 2.9 테스트베드 운영 명령 (예시)

```bash
# 시스템 스택 먼저 기동
cd system/
docker compose up -d

# 테스트베드 기동
cd ../testbed/
./certs/generate.sh
docker compose up -d

# 테스트베드 종료
docker compose down -v
```
