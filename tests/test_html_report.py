import json

import pytest

from dataset_test import get_scenario
from reporting.html_report import build_scenario_report, write_report
from schemas.ticket import TriageResult


def _sample_result(**overrides) -> TriageResult:
    base = {
        "analisi_problema": "1. Problema: test. 2. Contesto: test. 3. SECURITY. 4. HIGH.",
        "categoria": "SECURITY",
        "priorita": "HIGH",
        "riassunto_breve": "Test report HTML",
        "messaggio_originale": "Messaggio di test",
        "azione_eseguita": "search_policy, isolate_account",
    }
    base.update(overrides)
    return TriageResult(**base)


def test_build_scenario_report_outcome_ok():
    scenario = get_scenario(1)
    result = _sample_result(
        azione_eseguita="search_long_term_history, search_policy, isolate_account",
    )
    report = build_scenario_report(scenario, result, "sicurezza")
    assert report.outcome_ok is True
    assert report.team == "sicurezza"


def test_build_scenario_report_scenario3_allows_general():
    scenario = get_scenario(3)
    result = _sample_result(categoria="GENERAL", azione_eseguita=None)
    report = build_scenario_report(scenario, result, "GeneralQueue")
    assert report.outcome_ok is True


def test_write_report_creates_html_and_json(tmp_path, monkeypatch):
    monkeypatch.setattr("reporting.html_report.REPORTS_DIR", tmp_path)
    scenario = get_scenario(2)
    result = _sample_result(azione_eseguita="search_policy")
    report = build_scenario_report(scenario, result, "sicurezza")
    run_dir = tmp_path / "test-run"

    html_path = write_report([report], run_dir=run_dir)

    assert html_path == run_dir / "report.html"
    assert html_path.exists()
    assert (run_dir / "report.json").exists()

    html = html_path.read_text(encoding="utf-8")
    assert scenario.title in html
    assert "SECURITY" in html
    assert "HIGH" in html


def test_write_report_escapes_html_in_message(tmp_path, monkeypatch):
    from dataclasses import replace

    monkeypatch.setattr("reporting.html_report.REPORTS_DIR", tmp_path)
    scenario = get_scenario(1)
    malicious = '<script>alert("x")</script> phishing'
    result = _sample_result(
        messaggio_originale=malicious,
        azione_eseguita="search_long_term_history, search_policy, isolate_account",
    )
    scenario2 = replace(scenario, message=malicious)
    report = build_scenario_report(scenario2, result, "sicurezza")

    html_path = write_report([report], run_dir=tmp_path / "escape-run")
    html = html_path.read_text(encoding="utf-8")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_report_json_structure(tmp_path, monkeypatch):
    monkeypatch.setattr("reporting.html_report.REPORTS_DIR", tmp_path)
    scenario = get_scenario(4)
    result = _sample_result(
        priorita="CRITICAL",
        azione_eseguita="search_long_term_history, isolate_account, notify_manager",
    )
    report = build_scenario_report(scenario, result, "sicurezza")
    run_dir = tmp_path / "json-run"
    write_report([report], run_dir=run_dir)

    payload = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert payload["scenario_count"] == 1
    assert payload["scenarios"][0]["number"] == 4
    assert payload["scenarios"][0]["categoria"] == "SECURITY"
