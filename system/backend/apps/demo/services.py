from copy import deepcopy
from functools import lru_cache

from django.core.cache import cache


SESSION_CACHE_KEY = "final-demo-session-step"

STEPS = [
    {"id": "targets", "title": "대상 등록", "subtitle": "탐색 대상과 호스트 라벨을 확인합니다."},
    {"id": "agents", "title": "Agent 실행", "subtitle": "Discovery Agent와 Host Agent 결과를 합칩니다."},
    {"id": "cbom", "title": "Enriched CBOM", "subtitle": "표준 CBOM과 확장 컨텍스트를 함께 봅니다."},
    {"id": "risk", "title": "AI 위험도 평가", "subtitle": "DHS 6기준으로 P1/P2/P3를 산출합니다."},
    {"id": "migration", "title": "PQC 매핑 추천", "subtitle": "전환 후보와 권장 알고리즘을 확인합니다."},
    {"id": "verification", "title": "가용성 검증", "subtitle": "전환 이후 연결 가능성과 회귀 여부를 확인합니다."},
]

TARGETS = [
    {"id": "scope-01", "value": "10.0.0.0/24", "kind": "CIDR", "service": "사내 서브넷"},
    {"id": "scope-02", "value": "payments.demo.local", "kind": "Domain", "service": "외부 결제 API"},
    {"id": "scope-03", "value": "ssh.demo.local", "kind": "Domain", "service": "운영 SSH"},
    {"id": "scope-04", "value": "mail.demo.local", "kind": "Domain", "service": "메일 STARTTLS"},
    {"id": "scope-05", "value": "web.demo.local", "kind": "Domain", "service": "웹 TLS"},
    {"id": "scope-06", "value": "pqc.demo.local", "kind": "Domain", "service": "PQC TLS"},
    {"id": "scope-07", "value": "mqtt.demo.local", "kind": "Domain", "service": "MQTT TLS"},
    {"id": "scope-08", "value": "vpn.demo.local", "kind": "Domain", "service": "IPsec IKE"},
    {"id": "scope-09", "value": "db.demo.local", "kind": "Domain", "service": "DB TLS"},
    {"id": "scope-10", "value": "auth.demo.local", "kind": "Domain", "service": "인증 서버"},
    {"id": "scope-11", "value": "registry.demo.local", "kind": "Domain", "service": "패키지 저장소"},
    {"id": "scope-12", "value": "vault.demo.local", "kind": "Domain", "service": "비밀 관리"},
    {"id": "scope-13", "value": "monitoring.demo.local", "kind": "Domain", "service": "모니터링"},
]

HOST_LABELS = [
    {
        "host": "srv-01",
        "description": "외부 결제 API",
        "role": "edge-proxy",
        "data_classes": ["PII", "payment"],
        "partners": ["PG-A"],
        "retention": "7y",
    },
    {
        "host": "srv-02",
        "description": "인증 서버",
        "role": "auth",
        "data_classes": ["PII", "internal-only"],
        "partners": [],
        "retention": "5y",
    },
    {
        "host": "srv-03",
        "description": "운영 DB",
        "role": "db",
        "data_classes": ["payment", "internal-only"],
        "partners": [],
        "retention": "10y+",
    },
]

DISCOVERY_SUMMARY = {
    "total_assets": 47,
    "discovery_assets": 28,
    "host_assets": 24,
    "overlap_assets": 5,
    "active_keys": 44,
    "dormant_keys": 3,
    "algorithm_distribution": [
        {"label": "RSA", "count": 14, "quantum_vulnerable": True},
        {"label": "ECDSA", "count": 6, "quantum_vulnerable": True},
        {"label": "Ed25519", "count": 5, "quantum_vulnerable": True},
        {"label": "DH/X25519", "count": 8, "quantum_vulnerable": True},
        {"label": "AES/ChaCha20", "count": 9, "quantum_vulnerable": False},
        {"label": "SHA256/SHA512", "count": 5, "quantum_vulnerable": False},
    ],
}

AGENT_LOGS = {
    "discovery": [
        "CIDR 10.0.0.0/24 탐색 시작",
        "TLS endpoints: 9개 응답 확인",
        "STARTTLS mail endpoints: 4개 응답 확인",
        "SSH host key: 3개 수집",
        "IKE proposal: 2개 수집",
        "Discovery Agent 자산 28개 정리 완료",
    ],
    "host": [
        "srv-01 trust store 스캔 완료",
        "srv-01 nginx TLS 설정 파싱 완료",
        "srv-02 SSH 사용자 키 수집 완료",
        "srv-03 JKS/PKCS#12 저장소 스캔 완료",
        "사용되지 않는 개인키 파일 3개 탐지",
        "Host Agent 자산 24개 정리 완료",
    ],
}

VERIFICATION = {
    "overall_status": "PASS",
    "handshake_success_rate": 100,
    "latency_before_ms": 42,
    "latency_after_ms": 54,
    "throughput_before_rps": 2400,
    "throughput_after_rps": 2380,
    "compatibility_before": 100,
    "compatibility_after": 98,
    "failure_count": 0,
    "cbom_changes": 12,
    "checks": [
        {"name": "기능", "status": "PASS", "value": "TLS handshake 100%"},
        {"name": "응답 지연", "status": "PASS", "value": "p95 42ms -> 54ms"},
        {"name": "호환", "status": "PASS", "value": "100% -> 98%"},
        {"name": "회귀", "status": "PASS", "value": "실패 경로 0건"},
    ],
}


def reset_session() -> None:
    cache.set(SESSION_CACHE_KEY, 0, timeout=None)


def advance_session() -> dict:
    current = _current_step_index()
    cache.set(SESSION_CACHE_KEY, min(current + 1, len(STEPS) - 1), timeout=None)
    return demo_session()


def demo_session() -> dict:
    step_index = _current_step_index()
    return {
        "scenario": "final_presentation_demo",
        "current_step": step_index,
        "current_step_id": STEPS[step_index]["id"],
        "is_complete": step_index == len(STEPS) - 1,
        "resource_ids": {
            "target_set": "demo-targets-v1",
            "discovery": "demo-discovery-v1",
            "scan": "demo-scan-v1",
            "snapshot": "demo-cbom-v1",
            "assessment": "demo-assessment-v1",
            "migration": "demo-migration-v1",
            "verification": "demo-verification-v1",
        },
        "last_error": None,
        "can_retry": True,
        "steps": _step_states(step_index),
        "targets": deepcopy(TARGETS),
        "host_labels": deepcopy(HOST_LABELS),
        "agent_run": _agent_run(step_index),
        "assets": _assets_for_step(step_index),
        "risk": _risk_for_step(step_index),
        "migration": _migration_for_step(step_index),
        "verification": _verification_for_step(step_index),
    }


def demo_events() -> list[dict]:
    step_index = _current_step_index()
    events = []
    if step_index >= 0:
        events.append({"step": "targets", "message": "대상 13개와 srv-01 라벨 준비 완료", "progress": 100})
    if step_index >= 1:
        events.extend(
            {"step": "agents", "message": message, "progress": min(100, (index + 1) * 16)}
            for index, message in enumerate(AGENT_LOGS["discovery"] + AGENT_LOGS["host"])
        )
    if step_index >= 2:
        events.append({"step": "cbom", "message": "Enriched CBOM 47행 생성 완료", "progress": 100})
    if step_index >= 3:
        events.append({"step": "risk", "message": "DHS 6기준 평가 47/47 완료", "progress": 100})
    if step_index >= 4:
        events.append({"step": "migration", "message": "PQC 매핑 추천 20개 생성 완료", "progress": 100})
    if step_index >= 5:
        events.append({"step": "verification", "message": "가용성 검증 PASS, 실패 경로 0건", "progress": 100})
    return events


def _current_step_index() -> int:
    value = cache.get(SESSION_CACHE_KEY)
    if value is None:
        reset_session()
        return 0
    try:
        return max(0, min(int(value), len(STEPS) - 1))
    except (TypeError, ValueError):
        reset_session()
        return 0


def _step_states(step_index: int) -> list[dict]:
    states = []
    for index, step in enumerate(STEPS):
        if index < step_index:
            status = "completed"
            progress = 100
        elif index == step_index:
            status = "ready" if index == 0 else "completed"
            progress = 100
        else:
            status = "locked"
            progress = 0
        states.append({**step, "index": index, "status": status, "progress": progress})
    return states


def _agent_run(step_index: int) -> dict:
    if step_index < 1:
        return {**DISCOVERY_SUMMARY, "status": "pending", "progress": 0, "logs": {"discovery": [], "host": []}}
    return {**DISCOVERY_SUMMARY, "status": "completed", "progress": 100, "logs": deepcopy(AGENT_LOGS)}


def _assets_for_step(step_index: int) -> list[dict]:
    return demo_assets() if step_index >= 2 else []


def _risk_for_step(step_index: int) -> dict:
    if step_index < 3:
        return {"status": "pending", "summary": {"P1": 0, "P2": 0, "P3": 0}, "example": None}
    return {
        "status": "completed",
        "summary": {"P1": 12, "P2": 8, "P3": 27},
        "example": _srv_01_risk(),
    }


def _migration_for_step(step_index: int) -> dict:
    if step_index < 4:
        return {"status": "pending", "recommendation_count": 0, "items": []}
    items = []
    for asset in demo_assets():
        if asset["priority"] not in {"P1", "P2"}:
            continue
        items.append(
            {
                "asset_id": asset["id"],
                "current_algorithm": asset["algorithm"],
                "recommended_algorithm": _recommended_algorithm(asset),
                "priority": asset["priority"],
                "reason": "장기 보호 가치와 양자 취약 공개키 사용이 확인되어 전환 후보로 분류됨",
            }
        )
    return {"status": "completed", "recommendation_count": len(items), "items": items}


def _verification_for_step(step_index: int) -> dict:
    if step_index < 5:
        return {"status": "pending"}
    return {"status": "completed", **deepcopy(VERIFICATION)}


@lru_cache(maxsize=1)
def demo_assets() -> tuple[dict, ...]:
    categories = [
        ("RSA", 14, "RSA-2048"),
        ("ECDSA", 6, "ECDSA-P256"),
        ("Ed25519", 5, "Ed25519"),
        ("DH/X25519", 8, "X25519"),
        ("AES/ChaCha20", 9, "AES-256-GCM"),
        ("SHA256/SHA512", 5, "SHA-256"),
    ]
    priorities = ["P1"] * 12 + ["P2"] * 8 + ["P3"] * 27
    assets = [
        {
            "id": "srv-01:443/tls",
            "host": "srv-01",
            "domain": "api.payments.example.com",
            "name": "TLS Endpoint",
            "asset_type": "certificate",
            "algorithm_group": "RSA",
            "algorithm": "RSA-2048",
            "key_size": 2048,
            "expires": "2027-03-12",
            "role": "edge-proxy",
            "neighbors": ["payments-api", "redis-cache"],
            "data_tags": ["PII", "payment"],
            "retention": "7y",
            "discovered_by": ["discovery_agent", "host_agent"],
            "priority": "P1",
            "risk_score": 9.2,
            "dormant": False,
            "quantum_vulnerable": True,
        }
    ]
    category_index = 0
    used_in_category = 1
    for number in range(2, 48):
        while used_in_category >= categories[category_index][1]:
            category_index += 1
            used_in_category = 0
        group, _, algorithm = categories[category_index]
        priority = priorities[number - 1]
        host = f"srv-{((number - 1) % 13) + 1:02d}"
        discovered_by = _discovered_by_for_number(number)
        assets.append(
            {
                "id": f"{host}:{_port_for_group(group)}:{_asset_suffix(group, used_in_category + 1)}",
                "host": host,
                "domain": f"{host}.demo.local",
                "name": _asset_name(group, number),
                "asset_type": _asset_type(group),
                "algorithm_group": group,
                "algorithm": algorithm,
                "key_size": _key_size(algorithm),
                "expires": _expiration_for_number(number),
                "role": _role_for_number(number),
                "neighbors": _neighbors_for_number(number),
                "data_tags": _data_tags_for_priority(priority),
                "retention": _retention_for_priority(priority),
                "discovered_by": discovered_by,
                "priority": priority,
                "risk_score": _risk_score_for_priority(priority, number),
                "dormant": number in {8, 21, 34},
                "quantum_vulnerable": group in {"RSA", "ECDSA", "Ed25519", "DH/X25519"} and priority != "P3",
            }
        )
        used_in_category += 1
    return tuple(assets)


def _discovered_by_for_number(number: int) -> list[str]:
    if number <= 5:
        return ["discovery_agent", "host_agent"]
    if number <= 28:
        return ["discovery_agent"]
    return ["host_agent"]


def _port_for_group(group: str) -> int:
    return {
        "RSA": 443,
        "ECDSA": 8443,
        "Ed25519": 22,
        "DH/X25519": 500,
        "AES/ChaCha20": 5432,
        "SHA256/SHA512": 9443,
    }[group]


def _asset_suffix(group: str, ordinal: int) -> str:
    return group.lower().replace("/", "-").replace(" ", "-") + f"-{ordinal:02d}"


def _asset_name(group: str, number: int) -> str:
    labels = {
        "RSA": "RSA service certificate",
        "ECDSA": "ECDSA service certificate",
        "Ed25519": "SSH host key",
        "DH/X25519": "Key agreement profile",
        "AES/ChaCha20": "Symmetric encryption setting",
        "SHA256/SHA512": "Hash/signature policy",
    }
    return f"{labels[group]} #{number:02d}"


def _asset_type(group: str) -> str:
    return {
        "RSA": "certificate",
        "ECDSA": "certificate",
        "Ed25519": "ssh_host_key",
        "DH/X25519": "key_agreement",
        "AES/ChaCha20": "configuration",
        "SHA256/SHA512": "configuration",
    }[group]


def _key_size(algorithm: str) -> int | None:
    if "2048" in algorithm:
        return 2048
    if "256" in algorithm:
        return 256
    if algorithm == "Ed25519":
        return 256
    if algorithm == "X25519":
        return 255
    return None


def _expiration_for_number(number: int) -> str:
    year = 2027 + (number % 3)
    month = ((number * 3) % 12) + 1
    day = ((number * 7) % 27) + 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _role_for_number(number: int) -> str:
    roles = ["edge-proxy", "auth", "db", "mail", "vpn", "monitoring", "registry", "dev"]
    return roles[number % len(roles)]


def _neighbors_for_number(number: int) -> list[str]:
    neighbors = [
        ["payments-api", "redis-cache"],
        ["auth-db", "session-cache"],
        ["internal-api", "message-bus"],
        ["backup-service"],
    ]
    return neighbors[number % len(neighbors)]


def _data_tags_for_priority(priority: str) -> list[str]:
    if priority == "P1":
        return ["PII", "payment"]
    if priority == "P2":
        return ["internal-only"]
    return ["operational"]


def _retention_for_priority(priority: str) -> str:
    return {"P1": "7y", "P2": "5y", "P3": "1y"}[priority]


def _risk_score_for_priority(priority: str, number: int) -> float:
    if priority == "P1":
        return round(8.3 + (number % 8) * 0.1, 1)
    if priority == "P2":
        return round(6.2 + (number % 7) * 0.1, 1)
    return round(2.4 + (number % 12) * 0.1, 1)


def _srv_01_risk() -> dict:
    return {
        "asset_id": "srv-01:443/tls",
        "score": 9.2,
        "priority": "P1",
        "criteria": {
            "value": {"level": "HIGH", "reason": "외부 결제 API의 진입점으로 서비스 가치가 높음"},
            "data": {"level": "HIGH", "reason": "PII와 결제 데이터를 보호하는 통신 경로임"},
            "scope": {"level": "HIGH", "reason": "외부에서 내부 결제 API로 이어지는 양방향 경로임"},
            "sharing": {"level": "MED", "reason": "PG-A 파트너 연동이 존재함"},
            "critical": {"level": "HIGH", "reason": "결제 처리 경로의 장애 영향이 큼"},
            "lifetime": {"level": "HIGH", "reason": "보존 기간 7년으로 HNDL 위험이 큼"},
        },
    }


def _recommended_algorithm(asset: dict) -> str:
    group = asset["algorithm_group"]
    if group in {"RSA", "DH/X25519"} and asset["asset_type"] in {"key_agreement", "configuration"}:
        return "ML-KEM-768"
    if group in {"RSA", "ECDSA", "Ed25519"}:
        return "ML-DSA-65"
    return "SLH-DSA-SHA2-128s"
