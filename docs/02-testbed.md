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

테스트베드는 200~300명 규모 IT 회사의 PoC를 가정해 **25개 서비스**로 구성한다. 실제 프로토콜 동작이 중요한 7개는 전용 fixture로 유지하고, 나머지 18개는 가벼운 공통 TLS fixture로 서비스 경계·호스트명·인증서·Agent 식별 시나리오를 제공한다.

### 2.2.1 Core protocol fixtures

| # | 서비스 | 호스트네임 | 포트 | 베이스 이미지 | Agent | 시연 시나리오 |
|---|---|---|---|---|---|---|
| 1 | HTTPS Web Server | `web.testbed.local` | 443/TCP | `nginx:1.27-alpine` | ✓ | 협조 가능 호스트 (Agent로 시스템 CA·미사용 인증서까지 식별) |
| 2 | PQC-enabled TLS Server | `pqc-tls.testbed.local` | 443/TCP | OQS Provider 기반 빌드 예정, 현재 nginx placeholder | ✗ | 외부 시점 스캔만 (전환 후 자산 참조 예시) |
| 3 | SSH Server | `ssh.testbed.local` | 22/TCP | `linuxserver/openssh-server` 계열 fixture | ✓ | 협조 가능 호스트 (사용자 키·`authorized_keys`·`sshd_config` 정책 식별) |
| 4 | MQTT Broker | `mqtt.testbed.local` | 8883/TCP | `eclipse-mosquitto:2` | ✗ | 외부 시점 스캔만 |
| 5 | IPsec Gateway | `ipsec.testbed.local` | 500, 4500/UDP | `strongx509/strongswan` (digest pin) | ✗ | 외부 시점 스캔만 (IKE_SA_INIT 분석) |
| 6 | Mail Server | `mail.testbed.local` | 25, 465, 587, 993, 995/TCP | 자체 경량 fixture | ✗ | 외부 시점 스캔만 (멀티 포트, 포트별 cert 다양성) |
| 7 | Database Server | `db.testbed.local` | 5432/TCP | `postgres:16` (TLS 활성) | ✓ | 협조 가능 호스트 (keystore·약한 키 파일까지 식별) |

### 2.2.2 Enterprise TLS fixtures

| # | 서비스 | 호스트네임 | 포트 | Fixture | Agent | 시연 시나리오 |
|---|---|---|---|---|---|---|
| 8 | API Gateway | `api-gateway.testbed.local` | 8443/TCP | TLS fixture | ✓ | 공개 API/mTLS 종단, JWT signing key |
| 9 | Admin Console | `admin-console.testbed.local` | 443/TCP | TLS fixture | ✗ | 권한 관리 콘솔 |
| 10 | Mobile API | `mobile-api.testbed.local` | 443/TCP | TLS fixture | ✗ | 외부 모바일 API |
| 11 | OIDC Provider | `auth-oidc.testbed.local` | 443/TCP | TLS fixture | ✓ | OIDC JWKS/signing key |
| 12 | SAML Identity Provider | `saml-idp.testbed.local` | 443/TCP | TLS fixture | ✓ | SAML signing/encryption cert |
| 13 | Legacy MySQL TLS | `mysql-legacy.testbed.local` | 3306/TCP | TLS fixture | ✗ | TLS 1.2 + RSA-1024 legacy DB |
| 14 | Redis Cache TLS | `redis-cache.testbed.local` | 6380/TCP | TLS fixture | ✗ | Cache TLS endpoint |
| 15 | Kafka Broker TLS | `kafka-broker.testbed.local` | 9093/TCP | TLS fixture | ✗ | Event bus TLS endpoint |
| 16 | Internal gRPC Service | `internal-grpc.testbed.local` | 8443/TCP | TLS fixture | ✗ | 내부 서비스 TLS |
| 17 | Service Mesh mTLS Control Plane | `service-mesh-mtls.testbed.local` | 15017/TCP | TLS fixture | ✗ | TLS 1.3 mTLS control plane |
| 18 | CI Runner Control | `gitlab-runner.testbed.local` | 9443/TCP | TLS fixture | ✗ | CI/CD runner control endpoint |
| 19 | Container Registry | `container-registry.testbed.local` | 5000/TCP | TLS fixture | ✓ | Registry cert + image signing key |
| 20 | Artifact Repository | `artifact-repo.testbed.local` | 8443/TCP | TLS fixture | ✗ | Package/artifact repository |
| 21 | Vault KMS | `vault.testbed.local` | 8200/TCP | TLS fixture | ✓ | KMS/transit key metadata |
| 22 | Backup Encryption Service | `backup-service.testbed.local` | 8443/TCP | TLS fixture | ✓ | 장기 보관 백업 암호화 키 |
| 23 | Monitoring | `monitoring.testbed.local` | 9090/TCP | TLS fixture | ✗ | 운영 관측 엔드포인트 |
| 24 | Logging Search | `logging.testbed.local` | 9200/TCP | TLS fixture | ✗ | 로그 검색 엔드포인트 |
| 25 | Legacy Java App | `legacy-java-app.testbed.local` | 8443/TCP | TLS fixture | ✓ | JKS/RSA-1024 legacy app |

**Agent 탑재 그룹** (10개): web, ssh, db, api-gateway, auth-oidc, saml-idp, container-registry, vault, backup-service, legacy-java-app
**Agent 미탑재 그룹** (15개): 그 외 서비스

> **System CA Certificates** 와 **Package Repository Certificates** 는 별도 서비스가 아니라, **Agent가 탑재된 호스트에서 추가로 발견되는 자산 타입**이다. Agent 미탑재 호스트에서는 단순히 발견되지 않는 것이며, "식별 불가" 같은 별도 표기를 하지 않는다 (CBOM에는 발견된 자산만 들어간다).

## 2.3 네트워크 구성

### 2.3.1 IP/호스트 매핑 (예시)

| 호스트네임 | 컨테이너명 | 내부 IP |
|---|---|---|
| `dns.testbed.local` | `tb-dns` | 172.31.240.2 |
| `web.testbed.local` | `tb-web` | 172.31.240.10 |
| `pqc-tls.testbed.local` | `tb-pqc-tls` | 172.31.240.11 |
| `ssh.testbed.local` | `tb-ssh` | 172.31.240.12 |
| `mqtt.testbed.local` | `tb-mqtt` | 172.31.240.13 |
| `ipsec.testbed.local` | `tb-ipsec` | 172.31.240.14 |
| `mail.testbed.local` | `tb-mail` | 172.31.240.15 |
| `db.testbed.local` | `tb-db` | 172.31.240.16 |
| `api-gateway.testbed.local` | `tb-api-gateway` | 172.31.240.21 |
| `admin-console.testbed.local` | `tb-admin-console` | 172.31.240.22 |
| `mobile-api.testbed.local` | `tb-mobile-api` | 172.31.240.23 |
| `auth-oidc.testbed.local` | `tb-auth-oidc` | 172.31.240.24 |
| `saml-idp.testbed.local` | `tb-saml-idp` | 172.31.240.25 |
| `mysql-legacy.testbed.local` | `tb-mysql-legacy` | 172.31.240.26 |
| `redis-cache.testbed.local` | `tb-redis-cache` | 172.31.240.27 |
| `kafka-broker.testbed.local` | `tb-kafka-broker` | 172.31.240.28 |
| `internal-grpc.testbed.local` | `tb-internal-grpc` | 172.31.240.29 |
| `service-mesh-mtls.testbed.local` | `tb-service-mesh-mtls` | 172.31.240.30 |
| `gitlab-runner.testbed.local` | `tb-gitlab-runner` | 172.31.240.31 |
| `container-registry.testbed.local` | `tb-container-registry` | 172.31.240.32 |
| `artifact-repo.testbed.local` | `tb-artifact-repo` | 172.31.240.33 |
| `vault.testbed.local` | `tb-vault` | 172.31.240.34 |
| `backup-service.testbed.local` | `tb-backup-service` | 172.31.240.35 |
| `monitoring.testbed.local` | `tb-monitoring` | 172.31.240.36 |
| `logging.testbed.local` | `tb-logging` | 172.31.240.37 |
| `legacy-java-app.testbed.local` | `tb-legacy-java-app` | 172.31.240.38 |

### 2.3.2 호스트 노출 포트

호스트 머신에서 노출되는 포트는 시스템 스택이 외부에서 접근하기 위한 통로다.

| 호스트 포트 | 컨테이너 | 용도 |
|---|---|---|
| 5353/UDP | tb-dns | dnsmasq |
| 4430/TCP | tb-web | HTTPS (호스트 443 충돌 회피) |
| 4431/TCP | tb-pqc-tls | PQC TLS |
| 2222/TCP | tb-ssh | SSH |
| 8883/TCP | tb-mqtt | MQTT over TLS |
| 5000/UDP, 45000/UDP | tb-ipsec | IKE/IPsec (`45000`은 호스트 VPN 충돌 회피용 NAT-T host port) |
| 2525, 4465, 5587, 9993, 9995 /TCP | tb-mail | Mail (호스트 충돌 회피) |
| 54320/TCP | tb-db | PostgreSQL |
| 9111~9117/TCP | enterprise agent sidecars | API/OIDC/SAML/Registry/Vault/Backup/Legacy Java mock agents |

> 시스템 스택의 Network Scanner는 dnsmasq를 통해 호스트네임 → 내부 IP를 직접 사용하므로, 위 호스트 포트는 외부 디버깅/검증용이다. 단, 시스템 스택을 호스트 머신에서 실행하는 경우 위 포트를 사용한다. **상세는 12장 배포 가이드 참고.**
> Enterprise TLS fixture 서비스들은 기본적으로 호스트 포트를 열지 않는다. 동일 Docker 호스트에서 dnsmasq와 고정 bridge IP로 접근하는 것을 기준으로 한다.

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

### 2.4.12 Enterprise TLS Fixture 자산

18개 확장 서비스는 모두 공통 nginx TLS fixture를 사용한다. 목적은 실제 제품 전체를 무겁게 띄우는 것이 아니라, 200~300명 IT 회사에서 흔한 **서비스 경계와 암호 자산 위치**를 재현하는 것이다.

| 서비스군 | 대표 호스트 | 네트워크 자산 | Agent 추가 자산 |
|---|---|---|---|
| Public/API | `api-gateway`, `admin-console`, `mobile-api` | RSA/ECDSA TLS cert, 공개/DMZ exposure | API Gateway의 JWKS, mTLS trust bundle |
| Identity | `auth-oidc`, `saml-idp` | TLS cert | OIDC JWKS, SAML signing/encryption cert |
| Data platform | `mysql-legacy`, `redis-cache`, `kafka-broker` | TLS cert, legacy RSA-1024, ECDSA P-256 | 없음 |
| Internal platform | `internal-grpc`, `service-mesh-mtls` | TLS/mTLS control-plane cert, TLS 1.3 policy | 없음 |
| DevOps/Supply chain | `gitlab-runner`, `container-registry`, `artifact-repo` | TLS cert | Registry image signing key |
| Secrets/Backup | `vault`, `backup-service` | RSA-4096/RSA-2048 TLS cert | KMS/transit key reference, backup encryption key metadata |
| Observability | `monitoring`, `logging` | TLS cert | 없음 |
| Legacy app | `legacy-java-app` | TLS 1.2, RSA-1024 cert | JKS keystore, TLS properties |

## 2.5 알고리즘 다양성 요약 (Algorithm Coverage Matrix)

| 알고리즘 | 사용처 |
|---|---|
| RSA-1024 | DB Server, Legacy MySQL, Legacy Java App (의도적 약한 키) |
| RSA-2048 | HTTPS, MQTT, Mail, IPsec, SSH host key, API/OIDC/SAML/Backup/Observability fixtures |
| RSA-4096 | HTTPS root CA, MQTT, Package Repo (PGP), Vault/KMS fixture |
| ECDSA P-256 | HTTPS (web-ec), Mail (993), SSH host key, Admin Console, Kafka, Service Mesh, Registry |
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
│   └── api-gateway/, auth-oidc/, saml-idp/, vault/, ... # enterprise fixtures
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
│   ├── db/                   # Agent 탑재
│       ├── Dockerfile
│       └── postgresql.conf, pg_hba.conf
│   └── tls-fixture/          # 18개 enterprise TLS fixture 공통 nginx template
└── agent/
    └── mock_agent.py          # 내장 Agent 및 enterprise sidecar Agent 공통 mock
```

## 2.7 Agent 탑재 방식 (탑재 호스트 한정)

Agent를 탑재할 core 3개 호스트(web, ssh, db)는 컨테이너 내부 멀티 프로세스 방식을 사용한다. Enterprise TLS fixture 중 Agent가 필요한 7개 호스트는 서비스 컨테이너를 가볍게 유지하기 위해 mock agent sidecar를 사용한다.

| 방식 | 설명 | 채택 |
|---|---|---|
| **사이드카 컨테이너** | Agent를 별도 컨테이너로 띄움 | ✓ Enterprise fixture 7개에 채택 |
| **컨테이너 내부 멀티 프로세스** | 서비스 컨테이너의 Dockerfile에 Agent 추가, supervisord/dumb-init로 동시 실행 | ✓ Core 3개에 채택 |

> Core 서비스는 파일시스템 직접 접근을 보여주기 위해 컨테이너 내부 멀티 프로세스를 유지한다. Enterprise fixture는 서비스 수가 많으므로 sidecar mock으로 Agent 등록·heartbeat·scan API 계약을 검증한다.

> 미탑재 호스트는 베이스 이미지 또는 공통 TLS fixture만 실행한다.

> Agent 상세는 `04-agent.md` 참고.

## 2.8 부트스트랩 절차

테스트베드 시작 시 자동 수행되는 작업:

1. `certs/generate.sh` 실행 → 모든 의도된 인증서 생성 (CA 포함, 키 길이/곡선 다양화)
2. dnsmasq 컨테이너 시작
3. 각 서비스 컨테이너 시작
4. **Agent 탑재 호스트 10개** 의 Agent가 백엔드의 `/api/agents/register` 호출 (백엔드 URL은 환경변수로 주입)
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
