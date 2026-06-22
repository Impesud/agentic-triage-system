#!/usr/bin/env python3
"""
Apre l'ultimo report HTML (o un percorso specifico) nel browser predefinito.

Uso:
  PYTHONPATH=src python3 scripts/open_report.py
  PYTHONPATH=src python3 scripts/open_report.py logs/reports/2026-06-22_163901/report.html
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "logs" / "reports"


def _latest_report() -> Path | None:
    if not REPORTS_DIR.is_dir():
        return None
    candidates = sorted(REPORTS_DIR.glob("*/report.html"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _wsl_unc_path(path: Path) -> str:
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    resolved = path.resolve()
    parts = resolved.parts
    if parts and parts[0] == "/":
        tail = "/".join(parts[1:])
        return f"\\\\wsl.localhost\\{distro}\\{tail.replace('/', '\\')}"
    return str(resolved)


def _try_open(path: Path) -> bool:
    path = path.resolve()
    if not path.is_file():
        return False

    win_path = None
    try:
        win_path = subprocess.check_output(
            ["wslpath", "-w", str(path)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    attempts: list[list[str]] = []
    if win_path:
        attempts.append(["cmd.exe", "/c", "start", "", win_path])
        attempts.append(["explorer.exe", win_path])

    if shutil_which("wslview"):
        attempts.append(["wslview", str(path)])

    attempts.append(["xdg-open", str(path)])

    for cmd in attempts:
        try:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
    return False


def shutil_which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file():
            return str(candidate)
    return None


def main() -> int:
    if len(sys.argv) > 1:
        report = Path(sys.argv[1])
        if not report.is_absolute():
            report = REPO_ROOT / report
    else:
        report = _latest_report()
        if report is None:
            print("Nessun report in logs/reports/. Esegui prima: PYTHONPATH=src python3 src/main.py")
            return 1

    if not report.is_file():
        print(f"File non trovato: {report}")
        return 1

    print(f"Report: {report}")
    if _try_open(report):
        print("Apertura nel browser richiesta.")
        return 0

    print("\nApertura automatica non disponibile su questo ambiente.")
    print("Prova una di queste opzioni:\n")
    print(f"  1. Incolla in Esplora file / browser Windows:\n     {_wsl_unc_path(report)}\n")
    print(f"  2. In Cursor/VS Code: tasto destro su report.html → Reveal in File Explorer → doppio click\n")
    print(f"  3. Server locale:\n     cd {report.parent} && python3 -m http.server 8765")
    print("     poi apri http://localhost:8765/report.html nel browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
