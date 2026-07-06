"""Test integrazione report HTML da main.py."""

from unittest.mock import patch

from analytics.week12_report import Week12ReportBuilder
from main import (
    _parse_args,
    _register_api_skip,
    _run_scenario_with_report,
    _write_report,
    run_l15_topology_demo,
)


def test_register_api_skip_l16a():
    report = Week12ReportBuilder(root_scenario="l16a")
    _register_api_skip(report, "l16a")
    assert report.scenario_status("l16a") == "Saltato"
    assert len(report.triage_rows) == 1
    assert report.triage_rows[0].skipped


def test_register_api_skip_l16b():
    report = Week12ReportBuilder(root_scenario="l16b")
    _register_api_skip(report, "l16b")
    assert report.scenario_status("l16b") == "Saltato"
    assert report.triage_rows[0].scenario_id == "l16b"


@patch("main.skip_llm_block", return_value=True)
def test_run_scenario_skipped_still_populates_report(mock_skip):
    report = Week12ReportBuilder(root_scenario="l17a")
    ran = _run_scenario_with_report("l17a", report)
    assert ran is False
    assert report.scenario_status("l17a") == "Saltato"


def test_l15_run_populates_report():
    report = Week12ReportBuilder(root_scenario="l15")
    run_l15_topology_demo(report=report)
    assert report.l15 is not None
    assert report.scenario_status("l15") == "Eseguito"


@patch("main.open_html_in_browser", return_value=True)
def test_write_report_opens_browser_and_writes_json(mock_open, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "analytics.week12_report.WEEK12_REPORT_PATH",
        tmp_path / "week12_demo_report.html",
    )
    monkeypatch.setattr(
        "analytics.week12_report.WEEK12_REPORT_JSON_PATH",
        tmp_path / "week12_demo_report.json",
    )
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(ticket="t", topologies=["sequential"], agents=[], handoff={})
    path = _write_report(report, open_browser=True)
    assert path.exists()
    assert (tmp_path / "week12_demo_report.json").exists()
    mock_open.assert_called_once_with(path)


@patch("main.open_html_in_browser")
def test_write_report_no_open_skips_browser(mock_open, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "analytics.week12_report.WEEK12_REPORT_PATH",
        tmp_path / "week12_demo_report.html",
    )
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(ticket="t", topologies=["sequential"], agents=[], handoff={})
    _write_report(report, open_browser=False)
    mock_open.assert_not_called()


def test_parse_args_no_report_flag():
    with patch("sys.argv", ["main.py", "--no-report"]):
        args = _parse_args()
    assert args.no_report is True
    assert args.no_open is False


def test_parse_args_no_open_flag():
    with patch("sys.argv", ["main.py", "--no-open"]):
        args = _parse_args()
    assert args.no_open is True
    assert args.no_report is False
