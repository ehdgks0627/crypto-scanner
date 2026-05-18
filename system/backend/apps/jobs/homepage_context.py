from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any


CONTEXT_FIELDS = ("sensitivity", "lifespan_years", "criticality", "exposure", "service_role")


@dataclass(frozen=True)
class RoleRule:
    role: str
    keywords: tuple[str, ...]
    sensitivity: str
    criticality: str
    exposure: str
    lifespan_years: int


ROLE_RULES = (
    RoleRule(
        "customer_portal",
        ("customer portal", "my account", "account dashboard", "invoice", "billing", "order history", "profile"),
        "high",
        "high",
        "public_internet",
        10,
    ),
    RoleRule(
        "authentication",
        ("login", "log in", "sign in", "sso", "oauth", "oidc", "identity", "password", "mfa", "multi-factor"),
        "high",
        "high",
        "dmz",
        10,
    ),
    RoleRule(
        "admin_console",
        ("admin", "administrator", "management console", "control panel", "operations console"),
        "high",
        "high",
        "internal_network",
        5,
    ),
    RoleRule(
        "developer_api",
        ("api", "openapi", "swagger", "developer", "graphql", "webhook"),
        "medium",
        "high",
        "dmz",
        5,
    ),
    RoleRule(
        "file_service",
        ("download", "upload", "document", "file", "storage", "repository", "artifact"),
        "high",
        "medium",
        "dmz",
        10,
    ),
    RoleRule(
        "monitoring",
        ("grafana", "prometheus", "metrics", "monitoring", "observability", "dashboard"),
        "medium",
        "medium",
        "internal_network",
        3,
    ),
    RoleRule(
        "public_web",
        ("home", "welcome", "about", "contact", "support", "portal"),
        "medium",
        "medium",
        "dmz",
        3,
    ),
)


def infer_homepage_context(
    *,
    url: str,
    status_code: int,
    content_type: str | None,
    body: bytes | str,
) -> dict[str, Any] | None:
    text = _decode_body(body)
    if not text.strip():
        return None
    title = _extract_title(text)
    description = _extract_meta(text, "description")
    keywords = _extract_meta(text, "keywords")
    searchable = _normalize_text(" ".join([title or "", description or "", keywords or "", _visible_text(text)]))
    if not searchable:
        return None

    rule, matched = _best_rule(searchable)
    if rule is None:
        return None
    confidence = _confidence(rule, matched, searchable, content_type)
    return {
        "service_role": rule.role,
        "sensitivity": rule.sensitivity,
        "criticality": rule.criticality,
        "exposure": rule.exposure,
        "lifespan_years": rule.lifespan_years,
        "homepage_inference": {
            "source": "homepage",
            "method": "html_keyword_inference",
            "url": url,
            "status_code": status_code,
            "content_type": content_type or "",
            "title": _truncate(title, 160),
            "description": _truncate(description, 240),
            "signals": matched[:8],
            "confidence": confidence,
        },
    }


def _decode_body(body: bytes | str) -> str:
    if isinstance(body, str):
        return body
    return body.decode("utf-8", errors="replace")


def _extract_title(text: str) -> str:
    match = re.search(r"<title[^>]*>(?P<value>.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    return _clean_text(match.group("value")) if match else ""


def _extract_meta(text: str, name: str) -> str:
    pattern = (
        r"<meta[^>]+(?:name|property)=[\"'](?:og:)?"
        + re.escape(name)
        + r"[\"'][^>]+content=[\"'](?P<value>.*?)[\"'][^>]*>"
    )
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_text(match.group("value"))
    reverse_pattern = (
        r"<meta[^>]+content=[\"'](?P<value>.*?)[\"'][^>]+(?:name|property)=[\"'](?:og:)?"
        + re.escape(name)
        + r"[\"'][^>]*>"
    )
    reverse = re.search(reverse_pattern, text, flags=re.IGNORECASE | re.DOTALL)
    return _clean_text(reverse.group("value")) if reverse else ""


def _visible_text(text: str) -> str:
    without_scripts = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return _clean_text(without_tags)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _best_rule(text: str) -> tuple[RoleRule | None, list[str]]:
    best_rule = None
    best_matches: list[str] = []
    for rule in ROLE_RULES:
        matches = [keyword for keyword in rule.keywords if keyword in text]
        if len(matches) > len(best_matches):
            best_rule = rule
            best_matches = matches
    return best_rule, best_matches


def _confidence(rule: RoleRule, matches: list[str], text: str, content_type: str | None) -> float:
    base = 0.42 + min(len(matches), 4) * 0.11
    if "text/html" in (content_type or "").lower():
        base += 0.05
    if rule.role in {"customer_portal", "authentication", "admin_console"} and any(
        marker in text for marker in ("login", "sign in", "password", "customer", "account")
    ):
        base += 0.07
    return round(min(base, 0.92), 2)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."
