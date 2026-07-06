"""Test report HTML copre tutte le lezioni 15–17."""

from analytics.week12_report import (
    LESSON_SCENARIOS,
    BenchmarkRow,
    L17aRunRow,
    Week12ReportBuilder,
    render_week12_html,
)


def test_summary_lists_all_lesson_scenarios():
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(ticket="t", topologies=["sequential"], agents=[], handoff={})
    html_out = render_week12_html(report)
    assert "Riepilogo scenari" in html_out
    for scenario_id, lesson, _ in LESSON_SCENARIOS:
        assert scenario_id in html_out
        assert f"L{lesson}" in html_out


def test_all_lesson_sections_present_when_only_l15_run():
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(ticket="Marco", topologies=["sequential"], agents=[], handoff={})
    html_out = render_week12_html(report)
    assert "Lezione 15" in html_out
    assert "Lezione 16" in html_out
    assert "Lezione 17a" in html_out
    assert "Lezione 17b" in html_out
    assert "Non eseguito in questa run" in html_out
    assert report.scenario_status("l16a") == "Non eseguito"
    assert report.scenario_status("l17b") == "Non eseguito"


def test_l16_section_shows_both_subscenarios():
    report = Week12ReportBuilder(root_scenario="l16a")
    report.add_triage_scenario(
        scenario_id="l16a",
        lesson="16",
        title="CrewAI",
        wall_ms=100.0,
        result={"categoria": "SALES", "priorita": "HIGH", "riassunto_breve": "ok"},
    )
    html_out = render_week12_html(report)
    assert "l16a" in html_out
    assert "l16b" in html_out
    assert "Non eseguito in questa run" in html_out


def test_skipped_l17a_shows_in_report():
    report = Week12ReportBuilder(root_scenario="all")
    report.record_skip("l17a", "OPENAI_API_KEY assente")
    html_out = render_week12_html(report)
    assert report.scenario_status("l17a") == "Saltato"
    assert "OPENAI_API_KEY assente" in html_out


def test_full_all_scenario_report_structure():
    report = Week12ReportBuilder(root_scenario="all")
    report.set_l15(ticket="t", topologies=["sequential"], agents=[], handoff={"cliente_nome": "Marco"})
    report.add_triage_scenario(
        scenario_id="l16a",
        lesson="16",
        title="Crew",
        wall_ms=50,
        result={"categoria": "SALES", "priorita": "HIGH", "riassunto_breve": "x"},
    )
    report.add_triage_scenario(
        scenario_id="l16b",
        lesson="16",
        title="AutoGen",
        wall_ms=60,
        result={"categoria": "SALES", "priorita": "HIGH", "riassunto_breve": "y"},
    )
    report.set_l17a_runs(
        [
            L17aRunRow(
                label="baseline",
                wall_ms=100,
                tokens_est=50,
                enable_pruning=False,
                enable_cache=False,
                enable_compact_output=False,
            )
        ]
    )
    report.set_l17b_rows([BenchmarkRow(name="react", wall_ms=80, tokens_est=40, categoria="SALES")])
    html_out = render_week12_html(report)
    for scenario_id, _, _ in LESSON_SCENARIOS:
        assert report.scenario_status(scenario_id) == "Eseguito"
    assert "Eseguito" in html_out


def test_week12_report_builder_writes_file(tmp_path):
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(ticket="test", topologies=["sequential"], agents=[], handoff={})
    out = report.write_html(tmp_path / "demo.html")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "Riepilogo scenari" in content
    assert "test" in content
