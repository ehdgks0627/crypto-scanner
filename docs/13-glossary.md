# 13. 용어 사전 (Glossary)

본 문서는 명세 전반에서 사용된 용어, 약어, 알고리즘 명칭을 알파벳/가나다 순으로 정의한다.

## 13.1 본 시스템 고유 용어

| 용어 | 정의 |
|---|---|
| **Agent** | 평가 대상 호스트에 옵션으로 배포되는 경량 프로세스. Network Scanner로 보이지 않는 자산(시스템 CA, 미사용 키, 설정 파일)을 추가 식별한다. 본 시스템에서는 옵션 capability이며 필수가 아니다. (4장 참고) |
| **Agent Token** | Agent 등록 시 백엔드가 발급하는 UUID 토큰. 이후 Agent ↔ Worker 통신의 Bearer 인증에 사용. DB에는 해시로만 저장. |
| **Asset** | 스캔 결과 발견된 개별 객체. 암호자산(Algorithm/Certificate/Key/Protocol/Keystore) 또는 비암호 자산(Host/Service/Data) 모두 포함. |
| **Asset Class** | 자산의 최상위 분류. `crypto` / `host` / `service` / `data` 중 하나. |
| **Asset Type** | 자산의 세부 종류. `algorithm` / `certificate` / `key` / `protocol` / `keystore` / `device` / `service` / `data`. |
| **Bootstrap Token** | 시스템 스택과 테스트베드가 공유하는 사전 공유 시크릿. Agent의 최초 등록 요청에 사용된다. 등록 후에는 Agent Token이 발급되어 그것을 사용. |
| **CBOM** | Cryptography Bill of Materials. 시스템에 사용된 암호자산의 명세서. CycloneDX 1.6의 CBOM 사양을 기반으로 한다. (5장 참고) |
| **CBOM Snapshot** | 1회의 Scan Job 완료 시 생성되는 CBOM 문서. 영구 보관되며 시간순 비교(Diff)에 사용된다. |
| **Discovery** | CIDR 대역에 대한 자동 호스트/포트 스캔 작업. 결과로 DiscoveredEndpoint가 생성되며 사용자가 Target으로 promote할 수 있다. |
| **Discovered Endpoint** | Discovery로 발견된 (IP, port) 쌍과 부가 메타. Target과는 다르다 (Target은 사용자가 등록한 자산). |
| **Migration Plan** | 자산별 PQC 전환 권고와 영향 분석을 담은 보고서. v1은 권고만, v2에서 실제 전환 실행. |
| **Natural Key** | 자산의 자연 식별자. 스냅샷 간 동일성 판정에 사용. 인증서는 SHA-256 fingerprint, 키는 알고리즘+blob hash 등. |
| **PQC RAS** | "PQC Risk Assessment System"의 약어. 본 시스템 코드명. |
| **Promote** | Discovery로 발견된 endpoint를 Target으로 등록하는 행위. |
| **Risk Score** | 자산의 양자 위협 위험도. 0~100 정수. Algorithm × Data × Exposure × Lifespan × Criticality 인자의 곱셈 모델로 산출. |
| **Risk Tier** | Risk Score를 4단계로 매핑한 등급. Critical / High / Medium / Low. |
| **Scan Job** | 사용자가 트리거한 1회의 스캔 작업. 1개 이상의 Target × 1개 이상의 Scanner 조합으로 구성. 완료 시 Snapshot 1개 생성. |
| **Scanner** | 자산을 식별하는 단위 모듈. `network` / `agent.cert_store` / `agent.ssh_userkey` 등 8종. |
| **Snapshot** | CBOM Snapshot의 줄임말. |
| **Target** | 사용자가 등록한 스캔 대상. (host, port, transport) 단위. Discovery 결과를 promote하거나 직접 등록. |
| **Testbed** | 의도적으로 다양한 양자취약 알고리즘을 노출하는 검증 환경. 시스템 스택과 별개의 docker-compose. (2장 참고) |

## 13.2 외부 표준 / 기술 용어

| 용어 | 정의 |
|---|---|
| **ALPN** | Application-Layer Protocol Negotiation. TLS 핸드셰이크에서 상위 프로토콜(HTTP/2, MQTT, IMAP 등)을 협상하는 확장 (RFC 7301). 본 시스템의 프로토콜 식별 Tier 1. |
| **CBOM** | Cryptography Bill of Materials. SBOM의 암호 자산 확장. |
| **CIDR** | Classless Inter-Domain Routing. IP 주소 대역 표기법 (`172.31.240.0/24`). |
| **CRQC** | Cryptographically Relevant Quantum Computer. RSA-2048이나 ECC 등 고전 공개키 암호를 실시간 해독 가능한 수준의 양자컴퓨터. |
| **CycloneDX** | OWASP의 SBOM/CBOM 표준. 본 시스템은 1.6 사양을 채택. |
| **DH (Diffie-Hellman)** | 유한체 기반 키 교환 알고리즘. 양자 위협에 취약. |
| **dnsmasq** | 가벼운 DNS/DHCP 서버. 테스트베드에서 `*.testbed.local` 영역의 호스트네임 해석에 사용. |
| **ECDH** | Elliptic Curve Diffie-Hellman. 타원곡선 기반 키 교환. 양자 위협에 취약. |
| **ECDSA** | Elliptic Curve Digital Signature Algorithm. 타원곡선 기반 서명. 양자 위협에 취약. |
| **Ed25519 / Ed448** | Edwards-curve Digital Signature Algorithm. 양자 위협에 취약하지만 클래식 환경에서 효율적. |
| **HNDL** | Harvest Now, Decrypt Later. 현재 암호화된 데이터를 수집해 두었다가 미래에 양자컴퓨터로 복호화하는 공격 모델. |
| **Hybrid (PQC)** | 고전 알고리즘과 PQC 알고리즘을 결합한 방식 (예: X25519 + ML-KEM-768). 호환성 유지와 미래 대비를 동시에 달성. |
| **IKE / IKEv2** | Internet Key Exchange. IPsec의 키 교환 프로토콜. UDP 500/4500. 본 시스템의 IKE Probe는 IKE_SA_INIT만 수행. |
| **IPsec** | Internet Protocol Security. IP 계층 보안 프로토콜 (RFC 4301 외). VPN에 주로 사용. |
| **JKS** | Java KeyStore. Java 환경의 키/인증서 보관 파일 형식. |
| **KEM** | Key Encapsulation Mechanism. 키 캡슐화 메커니즘. 양자안전 키 교환의 표준 모델. |
| **KEX_INIT** | SSH 프로토콜의 초기 알고리즘 협상 메시지. 본 시스템 SSH Probe가 이 단계까지만 진행. |
| **MQTT** | Message Queuing Telemetry Transport. IoT용 발행/구독 프로토콜. 본 시스템은 8883/TCP에서 TLS 위 MQTT를 식별. |
| **NAT-T** | NAT Traversal. UDP 4500을 사용하는 IPsec NAT 우회 방식. 본 시스템 IKE Probe의 폴백. |
| **OQS** | Open Quantum Safe 프로젝트. liboqs 및 OQS Provider를 통해 PQC 알고리즘을 OpenSSL에 통합. |
| **PQC** | Post-Quantum Cryptography. 양자 컴퓨터에 대해서도 안전한 것으로 알려진 암호 알고리즘. |
| **SARIF** | Static Analysis Results Interchange Format. 정적 분석 결과 표준 (NIST 1800-38B의 정적 분석 출력 형식). 본 시스템은 v1에서 채택하지 않음. |
| **SBOM** | Software Bill of Materials. 소프트웨어 구성요소 명세. CBOM의 모태. |
| **Shor's Algorithm** | 양자 컴퓨터에서 정수 인수분해와 이산로그 문제를 다항시간에 푸는 알고리즘. RSA, DH, ECC를 모두 무력화한다. |
| **SNI** | Server Name Indication. TLS handshake에서 클라이언트가 접근할 서버 호스트네임을 알리는 확장 (RFC 6066). |
| **STARTTLS** | 평문 프로토콜 위에서 TLS로 업그레이드하는 명령. SMTP/IMAP/POP3에서 사용. |
| **TLS / DTLS** | Transport Layer Security / Datagram TLS. 본 시스템은 TLS 1.0~1.3 모두 식별, DTLS는 v2. |

## 13.3 NIST PQC 표준 알고리즘

| 알고리즘 | 표준 | 용도 | 비고 |
|---|---|---|---|
| **ML-KEM-512** | FIPS 203 | KEM (Key Encapsulation) | NIST Level 1 |
| **ML-KEM-768** | FIPS 203 | KEM | NIST Level 3, 본 시스템 권장 1차 |
| **ML-KEM-1024** | FIPS 203 | KEM | NIST Level 5 |
| **ML-DSA-44** | FIPS 204 | 서명 | NIST Level 2 |
| **ML-DSA-65** | FIPS 204 | 서명 | NIST Level 3, 본 시스템 권장 1차 |
| **ML-DSA-87** | FIPS 204 | 서명 | NIST Level 5 |
| **SLH-DSA-SHA2-128s/128f** | FIPS 205 | 서명 (해시 기반) | 작은 키 큰 서명 |
| **SLH-DSA-SHA2-192s/192f** | FIPS 205 | 서명 (해시 기반) | |
| **SLH-DSA-SHA2-256s/256f** | FIPS 205 | 서명 (해시 기반) | |
| **Falcon** (FN-DSA, 표준화 진행) | FIPS 206 (예정) | 서명 | 본 시스템 권장 후보에서는 ML-DSA를 우선 |

> 본 명세서는 NIST IR 8547 및 FIPS 203/204/205 (2024)를 기준으로 한다.

## 13.4 양자취약 알고리즘 (식별 대상)

| 알고리즘 | 양자 위협 |
|---|---|
| RSA-1024/2048/3072/4096 | Shor's algorithm으로 인수분해 문제 풀이 |
| DSA | 동일 |
| Diffie-Hellman (DH, modp14/15/16/...) | Shor's algorithm으로 이산로그 풀이 |
| ECDH | Shor's algorithm으로 EC 이산로그 풀이 |
| ECDSA | 동일 |
| Ed25519, Ed448 | 동일 |
| X25519, X448 | 동일 |

> AES-128 이상, SHA-256 이상은 양자 안전 분류 (Grover's algorithm으로 50% 강도 감소만 발생).

## 13.5 약어 일람 (NIST 1800-38B 부록 A 일부 + 본 시스템 추가)

| 약어 | 풀이 |
|---|---|
| **API** | Application Programming Interface |
| **ALPN** | Application-Layer Protocol Negotiation |
| **CARAF** | Crypto Agility Risk Assessment Framework |
| **CBOM** | Cryptography Bill of Materials |
| **CI/CD** | Continuous Integration / Continuous Delivery |
| **CIDR** | Classless Inter-Domain Routing |
| **CISA** | Cybersecurity & Infrastructure Security Agency (US) |
| **CRQC** | Cryptographically Relevant Quantum Computer |
| **CSF** | Cybersecurity Framework |
| **CWE** | Common Weakness Enumeration |
| **DH** | Diffie-Hellman |
| **DNS** | Domain Name System |
| **DRF** | Django REST Framework |
| **DTLS** | Datagram Transport Layer Security |
| **ECDH** | Elliptic Curve Diffie-Hellman |
| **ECDSA** | Elliptic Curve Digital Signature Algorithm |
| **EdDSA** | Edwards-curve Digital Signature Algorithm |
| **EDR** | Endpoint Detection and Response |
| **FIPS** | Federal Information Processing Standard |
| **GRC** | Governance, Risk, and Compliance |
| **HNDL** | Harvest Now, Decrypt Later |
| **HSM** | Hardware Security Module |
| **HTTPS** | Hypertext Transfer Protocol Secure |
| **IANA** | Internet Assigned Numbers Authority |
| **IDE** | Integrated Development Environment |
| **IKE / IKEv2** | Internet Key Exchange (Version 2) |
| **IPsec** | Internet Protocol Security |
| **JKS** | Java KeyStore |
| **JSON** | JavaScript Object Notation |
| **KEM** | Key Encapsulation Mechanism |
| **KEX** | Key Exchange |
| **LLM** | Large Language Model |
| **mTLS** | Mutual TLS |
| **ML-DSA** | Module-Lattice-Based Digital Signature Algorithm |
| **ML-KEM** | Module-Lattice-Based Key Encapsulation Mechanism |
| **MQTT** | Message Queuing Telemetry Transport |
| **NAT-T** | Network Address Translation Traversal |
| **NCCoE** | National Cybersecurity Center of Excellence |
| **NIST** | National Institute of Standards and Technology |
| **NSA** | National Security Agency |
| **NSM** | National Security Memorandum |
| **OASIS** | Organization for the Advancement of Structured Information Standards |
| **OID** | Object Identifier |
| **OMB** | Office of Management and Budget |
| **OQS** | Open Quantum Safe |
| **OWASP** | Open Worldwide Application Security Project |
| **PASTA** | Process of Attack Simulation and Threat Analysis |
| **PKCS** | Public-Key Cryptography Standard |
| **PKI** | Public Key Infrastructure |
| **POP3 / POP3S** | Post Office Protocol 3 (Secure) |
| **PQC** | Post-Quantum Cryptography |
| **PQ-RAS** | PQC Risk Assessment System (본 시스템) |
| **RBAC** | Role-Based Access Control |
| **RDP** | Remote Desktop Protocol |
| **RFC** | Request for Comments |
| **SARIF** | Static Analysis Results Interchange Format |
| **SBOM** | Software Bill of Materials |
| **SDLC** | Software Development Life Cycle |
| **SDK** | Software Development Kit |
| **SIEM** | Security Information and Event Management |
| **SLH-DSA** | Stateless Hash-based Digital Signature Algorithm |
| **SMF** | System Management Facility (IBM) |
| **SMTP / SMTPS** | Simple Mail Transfer Protocol (Secure) |
| **SNI** | Server Name Indication |
| **SP** | Special Publication |
| **SSDF** | Secure Software Development Framework |
| **SSH** | Secure Shell |
| **TLS** | Transport Layer Security |
| **VPN** | Virtual Private Network |
| **XML** | Extensible Markup Language |
| **zERT** | z/OS Encryption Readiness Technology (IBM) |

## 13.6 본 시스템 결정사항 ID 일람

`00-overview.md`의 결정사항 표에 사용된 ID들의 빠른 참조 매핑.

| ID | 핵심 |
|---|---|
| D-01 | 시스템과 테스트베드 분리 docker-compose |
| D-02 | REST 폴링 (5초) |
| D-03 | PostgreSQL 16 + 큰 CBOM은 파일 |
| D-04 | 싱글 유저, 인증 없음 |
| D-05 | CIDR 디스커버리 + 사용자 선택 등록 |
| D-06 | 1 Job, 스캐너 다중 선택 |
| D-07 | Network 필수 + Agent 옵션 |
| D-07a | Agent 통신 Hybrid (Push 등록 + Pull 트리거) |
| D-08 | 스캔 1회당 1 Snapshot |
| D-09 | 0~100 점수 + 4단계 등급 |
| D-10 | LLM은 인터페이스만, 구현은 v2 |
| D-11 | 컨텍스트는 Target 등록 시 + Asset override |
| D-12 | 비암호 자산 포함 |
| D-13 | 인증서 체인 leaf/intermediate/root 모두 별개 자산 |
| D-14 | Migration은 권고/시뮬레이션만 |
| D-15 | Django + Ninja + Celery + Redis |
| D-16 | React 18 + TS + Vite + TanStack Query + shadcn |
| D-17 | 테스트베드 측 dnsmasq 사용 |
| D-18 | 라이트/다크 토글 |
| D-19 | UI/명세서 한국어 |

## 13.7 참고 문서 / 표준

| 문서 | 출처 |
|---|---|
| NIST SP 1800-38B (Cryptographic Discovery) | https://www.nccoe.nist.gov/crypto-agility-considerations-migrating-post-quantum-cryptographic-algorithms |
| NIST IR 8547 (Transition to PQC Standards) | https://doi.org/10.6028/NIST.IR.8547.ipd |
| NIST CSWP 39 (Crypto Agility) | https://doi.org/10.6028/NIST.CSWP.39 |
| NIST FIPS 203 (ML-KEM) | https://doi.org/10.6028/NIST.FIPS.203 |
| NIST FIPS 204 (ML-DSA) | https://doi.org/10.6028/NIST.FIPS.204 |
| NIST FIPS 205 (SLH-DSA) | https://doi.org/10.6028/NIST.FIPS.205 |
| CycloneDX CBOM Authoritative Guide | https://cyclonedx.org/guides/OWASP_CycloneDX-Authoritative-Guide-to-CBOM-en.pdf |
| Canadian National Quantum-Readiness Best Practices | https://ised-isde.canada.ca/site/spectrum-management-telecommunications/sites/default/files/attachments/2023/cfdir-quantum-readiness-best-practices-v03.pdf |
| IETF Hybrid KEMs | https://datatracker.ietf.org/doc/draft-irtf-cfrg-hybrid-kems/ |
| IETF Terminology for PQ Traditional Hybrid Schemes | https://datatracker.ietf.org/doc/draft-ietf-pquip-pqt-hybrid-terminology/ |
