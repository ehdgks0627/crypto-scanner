# Citation Evidence

이 문서는 발표 자료에서 사용하는 외부 인용과 출처 표현을 고정한다. 인용은 원문 확인 범위 안에서만 사용하고, 표준 문서나 기관 공식 입장처럼 과장하지 않는다.

## 17.1 CSNP / QRAMM Toolkit 인용

슬라이드의 "You can't migrate what you can't find." 문구는 `CSNP CryptoScan README (QRAMM Toolkit)` 출처로 표기한다. 구조화된 근거는 `docs/kpi/csnp-qramm-quote-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 원 출처 | `csnp/cryptoscan` README |
| 고정 커밋 | `3af1302cfa897eafce6c8992f888313bbf25ada0` |
| QRAMM 맥락 | README가 CryptoScan을 QRAMM Toolkit의 일부로 소개함 |
| 도구 범위 | CryptoScan은 source code cryptographic discovery 역할로 설명됨 |
| 인용 문구 | "You can't migrate what you can't find." |
| 주변 맥락 | codebase, configuration, dependency 안의 암호 알고리즘 가시성 부족 문제를 설명함 |

발표에서는 다음 수준으로 제한한다.

> CSNP의 CryptoScan README는 QRAMM Toolkit 맥락에서 "You can't migrate what you can't find."라고 설명합니다. 이 문구는 PQC 전환의 출발점이 암호 사용 위치를 먼저 찾는 일이라는 점을 보여주는 인용으로 사용합니다.

주의할 점은 이 문구가 NIST SP 1800-38의 직접 인용이 아니며, QRAMM 표준 문서 전체의 공식 문구로 확인된 것도 아니라는 것이다. 정확한 표현은 `CSNP CryptoScan README (QRAMM Toolkit)`이다.

## 17.2 CISA 2024 마이그레이션 기간 표현

`CISA (2024) — 평균 마이그레이션 5~10년` 표현은 직접 인용으로 사용하지 않는다. 구조화된 근거는 `docs/kpi/cisa-migration-timeline-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 원 출처 | CISA, `Strategy for Migrating to Automated Post-Quantum Cryptography Discovery and Inventory Tools` |
| 발행일 | 2024-08-15 |
| 공식 페이지 | `https://www.cisa.gov/resources-tools/resources/strategy-migrating-automated-post-quantum-cryptography-discovery-and-inventory-tools` |
| 공식 PDF | `https://www.cisa.gov/sites/default/files/2024-09/Strategy-for-Migrating-to-Automated-PQC-Discovery-and-Inventory-Tools.pdf` |
| 확인된 주장 | CISA는 PQC 전환을 장기 전환으로 보고, 자동 암호 발견 및 인벤토리 도구로 전환 진행 상황을 추적해야 한다고 설명함 |
| 확인되지 않은 주장 | CISA 2024 문서가 평균 마이그레이션 기간을 5~10년으로 측정하거나 보고했다는 직접 근거는 확인하지 못함 |

발표에서는 다음 수준으로 제한한다.

> CISA의 2024 전략 문서는 PQC 전환을 단기간 작업이 아니라 장기간 추적해야 하는 전환 과제로 보고, 자동 암호 발견 및 인벤토리 도구를 통해 진행 상황을 관리하도록 제안합니다.

주의할 점은 `5~10년`이라는 숫자를 유지하려면 별도 출처를 붙여야 한다는 것이다. CISA 2024 문서는 우리 프로젝트의 `탐색 → 목록화 → 전환 진행 추적` 필요성을 뒷받침하는 근거로 사용하고, 평균 기간 수치의 직접 출처처럼 설명하지 않는다.
