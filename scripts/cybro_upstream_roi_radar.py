#!/usr/bin/env python3
"""Rank CybroAddons upstream PRs by likely operational value for Conexao Azul.

The radar is intentionally heuristic. It narrows the review surface and emits
machine-readable evidence; humans/agents still validate compatibility, license,
security, overlap with Odoo/OCA/BlueApps, and real QA before adoption.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UPSTREAM = "CybroOdoo/CybroAddons"
API_ROOT = "https://api.github.com"

# High weights encode the current ops strategy: platform/revenue/automation first,
# cosmetics last. Terms are matched against PR title + body.
SIGNALS: dict[str, tuple[int, str]] = {
    "api": (9, "platform-api"),
    "rest": (9, "platform-api"),
    "webhook": (9, "platform-api"),
    "oauth": (9, "security-identity"),
    "token": (8, "security-identity"),
    "security": (9, "security-identity"),
    "audit": (9, "governance-audit"),
    "access": (7, "security-identity"),
    "permission": (7, "security-identity"),
    "dashboard": (8, "observability-kpi"),
    "report": (6, "observability-kpi"),
    "kpi": (8, "observability-kpi"),
    "subscription": (10, "revenue-billing"),
    "recurring": (10, "revenue-billing"),
    "billing": (10, "revenue-billing"),
    "payment": (10, "revenue-billing"),
    "invoice": (7, "revenue-billing"),
    "stripe": (10, "revenue-billing"),
    "helpdesk": (8, "support-sla"),
    "sla": (9, "support-sla"),
    "ticket": (7, "support-sla"),
    "crm": (9, "revenue-crm"),
    "lead": (8, "revenue-crm"),
    "sale": (7, "revenue-crm"),
    "portal": (8, "portal-self-service"),
    "website": (5, "portal-self-service"),
    "inventory": (6, "erp-operations"),
    "stock": (6, "erp-operations"),
    "purchase": (6, "erp-operations"),
    "project": (5, "delivery-ops"),
    "timesheet": (6, "delivery-ops"),
    "automation": (9, "automation"),
    "workflow": (8, "automation"),
    "cron": (7, "automation"),
    "queue": (8, "automation"),
    "notification": (6, "automation"),
    "whatsapp": (9, "messaging"),
    "mail": (5, "messaging"),
    "document": (6, "documents"),
    "signature": (8, "documents"),
    "performance": (8, "reliability-performance"),
    "cache": (7, "reliability-performance"),
    "fix": (2, "reliability-performance"),
    "bug": (2, "reliability-performance"),
    "theme": (-5, "cosmetic"),
    "color": (-5, "cosmetic"),
    "font": (-5, "cosmetic"),
}

HIGH_VALUE_BUCKETS = {
    "platform-api",
    "security-identity",
    "governance-audit",
    "observability-kpi",
    "revenue-billing",
    "support-sla",
    "revenue-crm",
    "automation",
    "messaging",
    "portal-self-service",
}


@dataclass
class RankedPR:
    number: int
    title: str
    url: str
    state: str
    updated_at: str
    score: int
    buckets: list[str]
    signals: list[str]
    action: str


def request_json(url: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "conexaoazul-blueops-cybro-radar",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code}: {detail}") from exc


def fetch_prs(limit: int) -> list[dict[str, Any]]:
    per_page = min(max(limit, 1), 100)
    params = urllib.parse.urlencode(
        {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
        }
    )
    return request_json(f"{API_ROOT}/repos/{UPSTREAM}/pulls?{params}")[:limit]


def rank(pr: dict[str, Any]) -> RankedPR:
    text = f"{pr.get('title', '')} {pr.get('body') or ''}".lower()
    score = 0
    buckets: set[str] = set()
    matched: list[str] = []

    for term, (weight, bucket) in SIGNALS.items():
        if term in text:
            score += weight
            buckets.add(bucket)
            matched.append(term)

    # Prefer PRs explicitly targeting the current Odoo line.
    base = (pr.get("base") or {}).get("ref", "")
    if base == "19.0":
        score += 12
        matched.append("base:19.0")
    elif base.startswith("18."):
        score += 3
        matched.append("base:18.x")
    elif base and not base.startswith("19."):
        score -= 3

    # Merged code is useful donor evidence; open PRs are useful frontier signals.
    if pr.get("merged_at"):
        score += 4
        matched.append("merged")
    elif pr.get("state") == "open":
        score += 2
        matched.append("open")

    high_value_hits = len(buckets & HIGH_VALUE_BUCKETS)
    if high_value_hits >= 2:
        score += min(high_value_hits * 2, 8)

    action = "IGNORE"
    if score >= 24:
        action = "EXTRACT_OR_REIMPLEMENT"
    elif score >= 14:
        action = "REVIEW_FOR_PORT"
    elif score >= 8:
        action = "WATCH"

    return RankedPR(
        number=int(pr["number"]),
        title=str(pr.get("title", "")),
        url=str(pr.get("html_url", "")),
        state=str(pr.get("state", "")),
        updated_at=str(pr.get("updated_at", "")),
        score=score,
        buckets=sorted(buckets),
        signals=sorted(set(matched)),
        action=action,
    )


def render_markdown(rows: list[RankedPR], generated_at: str) -> str:
    lines = [
        "# CybroAddons Upstream ROI Radar",
        "",
        f"Generated: `{generated_at}`",
        f"Upstream: `{UPSTREAM}`",
        "",
        "> This is a prioritization radar, not an automatic adoption decision. "
        "Before porting, compare against Odoo 19 native, OCA and BlueApps, then run license/security/QA gates.",
        "",
        "| Rank | PR | Score | Action | Buckets | Updated |",
        "|---:|---|---:|---|---|---|",
    ]
    for idx, row in enumerate(rows, 1):
        buckets = ", ".join(row.buckets) or "-"
        title = row.title.replace("|", "\\|")
        lines.append(
            f"| {idx} | [#{row.number} {title}]({row.url}) | {row.score} | "
            f"`{row.action}` | {buckets} | {row.updated_at[:10]} |"
        )

    lines.extend(
        [
            "",
            "## Adoption contract",
            "",
            "1. Prefer Odoo 19 native capability when functionally equivalent.",
            "2. Prefer maintained OCA 19.0 implementation when it reduces long-term ownership.",
            "3. Treat CybroAddons as donor code: extract the differentiating capability rather than importing avoidable dependency chains.",
            "4. For every adopted capability record source PR/SHA, license, destination module, overlap decision and QA evidence.",
            "5. Never merge a port based only on this score; security-sensitive and revenue-critical code requires explicit validation.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out-dir", default="artifacts/cybro-radar")
    args = parser.parse_args()

    prs = fetch_prs(args.limit)
    ranked = sorted((rank(pr) for pr in prs), key=lambda item: (item.score, item.updated_at), reverse=True)
    top = ranked[: max(args.top, 1)]
    generated_at = datetime.now(timezone.utc).isoformat()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "upstream": UPSTREAM,
        "count_scanned": len(prs),
        "ranked": [row.__dict__ for row in top],
    }
    (out_dir / "radar.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (out_dir / "radar.md").write_text(render_markdown(top, generated_at), encoding="utf-8")

    print(render_markdown(top, generated_at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
