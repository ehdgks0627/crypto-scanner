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

## 17.3 백악관 NSM-10 암호 인벤토리 의무

`백악관 NSM-10 (2022) — 연방기관 암호 자산 목록 제출 의무화` 표현은 범위를 좁혀 사용한다. 구조화된 근거는 `docs/kpi/white-house-nsm10-inventory-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 원 출처 | The White House, `National Security Memorandum ... Vulnerable Cryptographic Systems` |
| 문서 번호 | NSM-10 |
| 발행일 | 2022-05-04 |
| 공식 아카이브 | `https://bidenwhitehouse.archives.gov/briefing-room/statements-releases/2022/05/04/national-security-memorandum-on-promoting-united-states-leadership-in-quantum-computing-while-mitigating-risks-to-vulnerable-cryptographic-systems/` |
| 확인된 주장 | FCEB 기관장은 NSM-10 발행 1년 내 및 이후 매년 CISA Director와 National Cyber Director에게 CRQC에 취약한 IT 시스템 인벤토리를 제출해야 함 |
| 포함 정보 | 인벤토리는 IT 시스템에서 사용하는 현재 암호 방식, 관리자 프로토콜, 업그레이드가 필요한 디지털 서명 관련 소프트웨어/펌웨어, 기타 핵심 자산 정보를 포함해야 함 |

발표에서는 다음 수준으로 제한한다.

> 백악관 NSM-10은 PQC 전환을 연방정부 차원의 장기 과제로 지정하고, FCEB 기관이 CRQC에 취약한 IT 시스템 인벤토리를 CISA와 National Cyber Director에게 제출하도록 요구했습니다. 이 인벤토리에는 현재 사용 중인 암호 방식 정보가 포함됩니다.

주의할 점은 NSM-10을 “모든 공공·민간 조직이 모든 암호자산 목록을 제출해야 한다”는 의미로 설명하면 안 된다는 것이다. 직접 요구 범위는 FCEB 기관과 CRQC 취약 IT 시스템 인벤토리이며, 세부 제출 항목과 첫 제출 일정은 OMB M-23-02에서 더 구체화된다.

## 17.4 국내 범국가 양자내성암호 전환 마스터플랜

`국정원 · KISA (2023) — 양자내성암호 마스터플랜` 표현은 기관 역할을 구분해 사용한다. 구조화된 근거는 `docs/kpi/korea-pqc-master-plan-evidence.json`에 둔다.

확인한 범위는 다음과 같다.

| 항목 | 확인 내용 |
| --- | --- |
| 공식 확인 출처 | KISA 암호이용활성화 `양자내성암호` 페이지 |
| 공식 URL | `https://seed.kisa.or.kr/kisa/ngc/pqc.do` |
| 확인된 주장 | 국내에서는 2023년 7월 관계 부처 협력으로 `汎국가 양자내성암호 전환 마스터플랜`을 공표함 |
| 후속 사업 | 2025년부터 `양자내성암호 시범전환 사업`을 추진해 전환이 필요한 국가 산업 분야 전반에 PQC 도입을 지원함 |
| 기관 표현 | 2023년 발표 주체는 국정원·과기정통부로 설명하고, KISA는 공식 확인 및 후속 시범전환 사업 관련 기관으로 설명함 |

발표에서는 다음 수준으로 제한한다.

> 한국도 2023년 7월 `범국가 양자내성암호 전환 마스터플랜`을 공표하고, 이후 KISA 등을 통해 양자내성암호 시범전환과 가이드 개발을 추진하고 있습니다. 이는 PQC 전환이 해외 표준만의 문제가 아니라 국내에서도 준비 중인 정책 과제라는 근거입니다.

주의할 점은 이 계획을 “모든 조직에 특정 기한까지 PQC 전환을 직접 의무화한 법적 명령”처럼 설명하면 안 된다는 것이다. 또한 KISA 공식 페이지는 마스터플랜의 존재와 후속 사업을 확인하는 공식 근거이며, 2023년 발표 주체 자체는 국정원·과기정통부로 분리해 말하는 편이 정확하다.
