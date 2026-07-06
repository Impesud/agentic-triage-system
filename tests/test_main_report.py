"""Test integrazione report HTML da main.py."""

from unittest.mock import patch

from analytics.week12_report import Week12ReportBuilder
from main import _register_api_skip, _run_scenario_with_report, run_l15_topology_demo


def test_register_api_skip_l16a():
    report = Week12ReportBuilder(root_scenario="l16a")
    _register_api_skip(report, "l16a")
    assert report.scenario_status("l16a") == "Saltato"
    assert len(report.triage_rows) == 1
    assert report.triage_rows[0].skipped


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
