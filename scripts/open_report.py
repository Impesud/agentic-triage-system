#!/usr/bin/env python3
"""
Apre un report HTML nel browser predefinito (WSL → browser Windows).

Uso:
  PYTHONPATH=src python3 scripts/open_report.py
  PYTHONPATH=src python3 scripts/open_report.py logs/week12_demo_report.html
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from reporting.open_html import (  # noqa: E402
    format_open_fallback,
    open_html_in_browser,
    resolve_report_path,
)


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    report = resolve_report_path(arg)

    if not report.is_file():
        print(f"File non trovato: {report}")
        print("Esegui prima una demo: PYTHONPATH=src python3 src/main.py")
        return 1

    print(f"Report: {report}")
    if open_html_in_browser(report):
        print("Apertura nel browser richiesta.")
        return 0

    print(format_open_fallback(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
