#!/usr/bin/env python3
"""Read-only brand/contact audit of CybroAddons Odoo 19 marketing pages.

Usage: python3 scripts/cybro_brand_contact_audit.py [--strict] [--json]

The original author's attribution is not a contact-routing error. This tool
deliberately does not rewrite code, install modules, or scan credentials.
"""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRIORITY_MODULES = (
    "pos_receipt_invoice_send_whatsapp",
    "survey_whatsapp_integration",
    "website_extra_social_media",
    "website_floating_whatsapp_icon",
    "whatsapp_chat_layout",
    "whatsapp_mail_messaging",
    "whatsapp_product_inquiry",
    "whatsapp_redirect",
)
REQUIRED_CONTACTS = (
    'href="https://wa.me/551151924469"',
    'href="mailto:suporte@conexaoazul.com"',
    'href="https://www.conexaoazul.com/en/ajuda/"',
)
LEGACY_PATTERNS = {
    "vendor_whatsapp": re.compile(r"wa\.me/919074270811", re.I),
    "empty_email": re.compile(r'href=["\']mailto:["\']', re.I),
    "empty_skype": re.compile(r'href=["\']skype:["\']', re.I),
    "vendor_logo": re.compile(r"Cybrosys(?: R)?\.png", re.I),
}
RUNTIME_PATTERNS = {
    "literal_whatsapp": re.compile(r"wa\.me/\d{8,}", re.I),
    "empty_email": LEGACY_PATTERNS["empty_email"],
    "vendor_support_endpoint": re.compile(r"support\.cybrosys\.com", re.I),
    "old_vendor_number": re.compile(r"919074270811", re.I),
}
CODE_SUFFIXES = {".py", ".xml", ".js", ".css", ".scss"}


def audit(root):
    marketing = {}
    runtime = {}
    modules = [
        p for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and (p / "__manifest__.py").is_file()
    ]
    for module in sorted(modules):
        marketing_file = module / "static" / "description" / "index.html"
        if marketing_file.is_file():
            content = marketing_file.read_text(encoding="utf-8", errors="replace")
            marketing[module.name] = {
                name: bool(pattern.search(content))
                for name, pattern in LEGACY_PATTERNS.items()
            }
        for path in module.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in CODE_SUFFIXES:
                continue
            if "tests" in path.parts or ("static" in path.parts and "description" in path.parts):
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            for name, pattern in RUNTIME_PATTERNS.items():
                if pattern.search(content):
                    runtime.setdefault(name, []).append(str(path.relative_to(root)))

    priority_errors = []
    for module_name in PRIORITY_MODULES:
        path = root / module_name / "static" / "description" / "index.html"
        if not path.is_file():
            priority_errors.append(f"Missing priority page: {path.relative_to(root)}")
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for target in REQUIRED_CONTACTS:
            if target not in content:
                priority_errors.append(f"{module_name}: missing {target}")
        if "https://www.conexaoazul.com/logo-light.png" not in content:
            priority_errors.append(f"{module_name}: missing official light logo")
        if "Módulo original: Cybrosys Techno Solutions" not in content:
            priority_errors.append(f"{module_name}: missing original author attribution")
        if any(p.search(content) for p in LEGACY_PATTERNS.values()):
            priority_errors.append(f"{module_name}: legacy marketing contact/logo")

    return {
        "marketing_pages_scanned": len(marketing),
        "marketing_counts": {
            name: sum(int(found[name]) for found in marketing.values())
            for name in LEGACY_PATTERNS
        },
        "runtime_matches": {name: sorted(set(paths)) for name, paths in runtime.items()},
        "priority_modules": len(PRIORITY_MODULES),
        "priority_errors": priority_errors,
        "sample_modules": {
            name: [module for module, found in marketing.items() if found[name]][:10]
            for name in LEGACY_PATTERNS
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="fail if priority pages regress")
    parser.add_argument("--json", action="store_true", help="print machine-readable evidence")
    parser.add_argument("--root", type=Path, default=ROOT, help="CybroAddons checkout")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Marketing pages: {result['marketing_pages_scanned']}")
        for name, count in result["marketing_counts"].items():
            print(f"  {name}: {count}")
        for name, paths in result["runtime_matches"].items():
            print(f"  runtime {name}: {len(paths)} file(s)")
            for path in paths[:5]:
                print(f"    {path}")
        print(f"Priority regressions: {len(result['priority_errors'])}")
        for problem in result["priority_errors"]:
            print(f"  {problem}")
    return bool(args.strict and result["priority_errors"])


if __name__ == "__main__":
    raise SystemExit(main())
