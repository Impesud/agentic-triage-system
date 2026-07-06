"""Test report HTML Settimana 12."""

from analytics.week12_report import (
    BenchmarkRow,
    L17aRunRow,
    Week12ReportBuilder,
    render_week12_html,
)


def test_render_week12_html_l15_section():
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(
        ticket="Sono Marco Rossi",
        topologies=["sequential", "hierarchical"],
        agents=[{"name": "TriageAnalyst", "role": "Analyst", "tools": ["search_long_term_history"]}],
        handoff={"cliente_nome": "Marco", "sentiment": "NEUTRO"},
    )
    html_out = render_week12_html(report)
    assert "Lezione 15" in html_out
    assert "Marco" in html_out
    assert "sequential" in html_out


def test_render_week12_html_l17a_and_benchmark():
    report = Week12ReportBuilder(root_scenario="all")
    report.set_l17a_runs(
        [
            L17aRunRow(
                label="baseline",
                wall_ms=1200.0,
                tokens_est=500,
                enable_pruning=False,
                enable_cache=False,
                enable_compact_output=False,
                categoria="SALES",
                priorita="HIGH",
            )
        ]
    )
    report.set_l17b_rows(
        [BenchmarkRow(name="react_triage", wall_ms=800.0, tokens_est=300, categoria="SALES")]
    )
    html_out = render_week12_html(report)
    assert "Lezione 17a" in html_out
    assert "Lezione 17b" in html_out
    assert "baseline" in html_out
    assert "react_triage" in html_out


def test_week12_report_builder_writes_file(tmp_path):
    report = Week12ReportBuilder(root_scenario="l15")
    report.set_l15(
        ticket="test",
        topologies=["sequential"],
        agents=[],
        handoff={},
    )
    out = report.write_html(tmp_path / "demo.html")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "test" in content
