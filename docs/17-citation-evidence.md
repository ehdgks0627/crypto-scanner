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
