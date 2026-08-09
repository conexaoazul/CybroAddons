#!/usr/bin/env python3
"""Static audit for access_roles registry hooks that mutate Odoo state at load time."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "access_roles" / "models"
MUTATION_NAMES = {
    "create", "write", "unlink",
    "get_all_buttons", "get_all_filters", "get_all_groupby", "get_all_tabs",
    "_update_role_groups_view",
}


def dotted_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def audit_file(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings = []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for fn in [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            if fn.name != "_register_hook":
                continue
            mutations = []
            for call in [n for n in ast.walk(fn) if isinstance(n, ast.Call)]:
                name = dotted_name(call.func)
                leaf = name.rsplit(".", 1)[-1]
                if leaf in MUTATION_NAMES:
                    mutations.append({"call": name, "line": call.lineno})
            findings.append({
                "file": str(path.relative_to(ROOT)),
                "class": cls.name,
                "line": fn.lineno,
                "mutations": mutations,
                "risk": "HIGH" if mutations else "LOW",
            })
    return findings


def main() -> int:
    findings = []
    for path in sorted(MODELS.glob("*.py")):
        findings.extend(audit_file(path))
    high = [item for item in findings if item["risk"] == "HIGH"]
    report = {
        "module": "access_roles",
        "register_hooks": len(findings),
        "mutating_register_hooks": len(high),
        "status": "RUNTIME_REPRODUCTION_REQUIRED" if high else "NO_STATIC_HAZARD",
        "findings": findings,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
