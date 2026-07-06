"""Test CLI scripts/open_report.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_open_report_module():
    if str(REPO_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / "src"))
    script = REPO_ROOT / "scripts" / "open_report.py"
    spec = importlib.util.spec_from_file_location("open_report_cli", script)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@patch("reporting.open_html.open_html_in_browser", return_value=True)
def test_open_report_script_success(mock_open, tmp_path, capsys):
    report = tmp_path / "week12_demo_report.html"
    report.write_text("<html></html>", encoding="utf-8")
    mod = _load_open_report_module()
    with patch.object(sys, "argv", ["open_report.py", str(report)]):
        assert mod.main() == 0
    mock_open.assert_called_once()
    assert "Apertura nel browser richiesta" in capsys.readouterr().out


def test_open_report_script_missing_file(capsys):
    mod = _load_open_report_module()
    missing = REPO_ROOT / "logs" / "nonexistent_report.html"
    with patch.object(sys, "argv", ["open_report.py", str(missing)]):
        assert mod.main() == 1
    assert "File non trovato" in capsys.readouterr().out
