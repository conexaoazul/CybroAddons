#!/usr/bin/env python3
"""Static probe for write-capable access_roles registry hooks on Odoo 19.

This is intentionally dependency-free so it can run in GitHub Actions and on
self-hosted runners before a runtime contention test is attempted.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "access_roles" / "models"
TARGETS = {
    "button_registry.py",
    "filter_registry.py",
    "groupby_registry.py",
    "tab_registry.py",
    "res_groups.py",
}
WRITE_CALLS = {"create", "write", "unlink"}


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def inspect(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hooks = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "_register_hook":
            continue
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = dotted_name(child.func)
                if name:
                    calls.append(name)
        hooks.append({
            "line": node.lineno,
            "calls": calls,
            "direct_write_calls": sorted({
                call for call in calls if call.rsplit(".", 1)[-1] in WRITE_CALLS
            }),
        })
    return {"file": str(path.relative_to(ROOT)), "hooks": hooks}


def main() -> int:
    findings = [inspect(MODEL_DIR / name) for name in sorted(TARGETS)]
    hook_count = sum(len(item["hooks"]) for item in findings)
    result = {
        "module": "access_roles",
        "odoo_target": "19.0",
        "registry_hook_count": hook_count,
        "risk": "HIGH" if hook_count >= 2 else "LOW",
        "reason": (
            "Multiple registry hooks independently trigger registry rebuild "
            "work during module/registry loading; multi-worker runtime QA is required."
            if hook_count >= 2
            else "No multi-hook registry rebuild pattern detected."
        ),
        "findings": findings,
    }
    print(json.dumps(result, indent=2))
    if hook_count < 5:
        raise SystemExit(
            f"Expected the current 19.0 baseline to expose 5 registry hooks; found {hook_count}. "
            "Update this probe if the architecture has intentionally changed."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
