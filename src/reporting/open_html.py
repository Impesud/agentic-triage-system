"""Apre file HTML nel browser predefinito (Linux, macOS, WSL → Windows)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from paths import REPO_ROOT, WEEK12_REPORT_PATH


def _which(name: str) -> str | None:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(directory) / name
        if candidate.is_file():
            return str(candidate)
    return None


def wsl_unc_path(path: Path) -> str:
    """Percorso UNC Windows per file sotto WSL (fallback manuale)."""
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    resolved = path.resolve()
    parts = resolved.parts
    if parts and parts[0] == "/":
        tail = "/".join(parts[1:])
        return f"\\\\wsl.localhost\\{distro}\\{tail.replace('/', chr(92))}"
    return str(resolved)


def resolve_report_path(path: Path | str | None = None) -> Path:
    """Risolve il report da aprire: argomento, week12 default, o ultimo in logs/reports/."""
    if path is not None:
        report = Path(path)
        if not report.is_absolute():
            report = REPO_ROOT / report
        return report

    if WEEK12_REPORT_PATH.is_file():
        return WEEK12_REPORT_PATH

    reports_dir = REPO_ROOT / "logs" / "reports"
    if reports_dir.is_dir():
        candidates = sorted(reports_dir.glob("*/report.html"), key=lambda p: p.stat().st_mtime)
        if candidates:
            return candidates[-1]

    return WEEK12_REPORT_PATH


def open_html_in_browser(path: Path | str) -> bool:
    """
    Tenta l'apertura nel browser. Ritorna True se un comando di apertura è stato lanciato.
    Su WSL prova cmd.exe/start ed explorer prima di xdg-open.
    """
    report = Path(path).resolve()
    if not report.is_file():
        return False

    win_path: str | None = None
    try:
        win_path = subprocess.check_output(
            ["wslpath", "-w", str(report)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    attempts: list[list[str]] = []
    if win_path:
        attempts.append(["cmd.exe", "/c", "start", "", win_path])
        attempts.append(["explorer.exe", win_path])

    if _which("wslview"):
        attempts.append(["wslview", str(report)])

    attempts.append(["xdg-open", str(report)])

    for cmd in attempts:
        try:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
    return False


def format_open_fallback(path: Path) -> str:
    """Istruzioni manuali se l'apertura automatica non è disponibile."""
    report = path.resolve()
    try:
        rel = report.relative_to(REPO_ROOT)
        open_hint = f"python3 scripts/open_report.py {rel}"
    except ValueError:
        open_hint = f"python3 scripts/open_report.py {report}"
    return (
        "\nApertura automatica non disponibile. Prova:\n"
        f"  1. {open_hint}\n"
        f"  2. Percorso Windows: {wsl_unc_path(report)}\n"
        f"  3. Server locale: cd {report.parent} && python3 -m http.server 8765\n"
        f"     poi http://localhost:8765/{report.name}"
    )
