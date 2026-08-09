#!/usr/bin/env python3
"""Static evidence generator for access_roles registry-hook concurrency risk.

This tool does not copy or depend on upstream proprietary code. It inspects the
current repository and reports model files that perform registry rebuild work
inside ``_register_hook``. Runtime reproduction remains a separate QA gate.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "access_roles" / "models"
OUT_DIR = ROOT / "artifacts" / "access-roles-concurrency"

WRITE_METHODS = {"create", "write", "unlink"}
REBUILD_PREFIXES = ("get_all_", "_update_")


def attr_name(node: ast.AST) -> str | None:
    return node.attr if isinstance(node, ast.Attribute) else None


def inspect_file(path: Path) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings = []
    for item in ast.walk(tree):
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name != "_register_hook":
            continue
        calls = []
        for child in ast.walk(item):
            if isinstance(child, ast.Call):
                name = attr_name(child.func)
                if name:
                    calls.append(name)
        findings.append({
            "line": item.lineno,
            "calls": sorted(set(calls)),
            "direct_write_calls": sorted(set(calls) & WRITE_METHODS),
            "rebuild_calls": sorted(
                name for name in set(calls)
                if name.startswith(REBUILD_PREFIXES)
            ),
        })
    return {"path": str(path.relative_to(ROOT)), "hooks": findings}


def main() -> int:
    files = sorted(MODELS_DIR.glob("*.py"))
    evidence = [inspect_file(path) for path in files]
    risky = [
        row for row in evidence
        if any(hook["direct_write_calls"] or hook["rebuild_calls"] for hook in row["hooks"])
    ]
    payload = {
        "module": "access_roles",
        "risk": "registry-hook-concurrent-write",
        "candidate_files": risky,
        "runtime_reproduction_required": bool(risky),
        "source": "clean-room static analysis of current 19.0 branch",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "audit.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print("# access_roles concurrency audit")
    print(f"Candidate files: {len(risky)}")
    for row in risky:
        print(f"- {row['path']}")
        for hook in row["hooks"]:
            if hook["direct_write_calls"] or hook["rebuild_calls"]:
                print(
                    f"  - line {hook['line']}: rebuild={hook['rebuild_calls']} "
                    f"writes={hook['direct_write_calls']}"
                )
    print("Runtime multi-worker reproduction required before applying a lock strategy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
