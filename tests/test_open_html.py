"""Test apertura report HTML nel browser."""

from pathlib import Path
from unittest.mock import patch

from reporting.open_html import format_open_fallback, open_html_in_browser, resolve_report_path, wsl_unc_path


def test_wsl_unc_path():
    path = Path("/home/user/proj/logs/week12_demo_report.html")
    unc = wsl_unc_path(path)
    assert unc.startswith("\\\\wsl.localhost\\")
    assert "week12_demo_report.html" in unc


def test_resolve_report_path_explicit(tmp_path):
    report = tmp_path / "custom.html"
    report.write_text("<html></html>", encoding="utf-8")
    assert resolve_report_path(report) == report.resolve()


@patch("reporting.open_html.subprocess.run")
@patch("reporting.open_html.subprocess.check_output", return_value="C:\\tmp\\report.html\n")
def test_open_html_uses_cmd_on_wsl(mock_check_output, mock_run, tmp_path):
    report = tmp_path / "report.html"
    report.write_text("<html></html>", encoding="utf-8")
    assert open_html_in_browser(report) is True
    mock_run.assert_called()
    first_cmd = mock_run.call_args_list[0][0][0]
    assert first_cmd[0] == "cmd.exe"


def test_open_html_missing_file(tmp_path):
    assert open_html_in_browser(tmp_path / "missing.html") is False


def test_format_open_fallback_contains_unc(tmp_path):
    report = tmp_path / "week12_demo_report.html"
    report.write_text("<html></html>", encoding="utf-8")
    text = format_open_fallback(report)
    assert "open_report.py" in text
    assert "http.server" in text


def test_resolve_report_path_defaults_to_week12(monkeypatch, tmp_path):
    report = tmp_path / "week12_demo_report.html"
    report.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr("reporting.open_html.WEEK12_REPORT_PATH", report)
    assert resolve_report_path() == report.resolve()


def test_resolve_report_path_missing_returns_week12_path(monkeypatch, tmp_path):
    missing = tmp_path / "missing.html"
    monkeypatch.setattr("reporting.open_html.WEEK12_REPORT_PATH", missing)
    monkeypatch.setattr("reporting.open_html.REPO_ROOT", tmp_path)
    assert resolve_report_path() == missing
