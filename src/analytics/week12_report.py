"""Report HTML demo Settimana 12–13 (Lezioni 15–18)."""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paths import WEEK12_REPORT_JSON_PATH, WEEK12_REPORT_PATH

# Scenari demo Lezioni 15–18 (Settimana 12–13)
LESSON_SCENARIOS: tuple[tuple[str, str, str], ...] = (
    ("l15", "15", "Topologie e Blackboard"),
    ("l16a", "16", "CrewAI sequenziale"),
    ("l16b", "16", "AutoGen GroupChat"),
    ("l17a", "17", "Pruning ReAct (3 run)"),
    ("l17b", "17", "Benchmark multi-pipeline"),
    ("l18a", "18", "Input Guardrail + SQLite"),
    ("l18b", "18", "Hand-off sanitizer + tool gate"),
)


@dataclass
class SkippedScenario:
    scenario_id: str
    reason: str


@dataclass
class L15Section:
    ticket: str
    topologies: list[str]
    agents: list[dict[str, Any]]
    handoff: dict[str, Any]


@dataclass
class TriageScenarioRow:
    scenario_id: str
    lesson: str
    title: str
    wall_ms: float | None = None
    result: dict[str, Any] | None = None
    skipped: bool = False
    skip_reason: str | None = None
    ticket_input: str | None = None
    orchestrator: str | None = None


@dataclass
class L17aRunRow:
    label: str
    wall_ms: float
    tokens_est: int
    enable_pruning: bool
    enable_cache: bool
    enable_compact_output: bool
    categoria: str | None = None
    priorita: str | None = None
    analisi_problema: str | None = None
    azione_eseguita: str | None = None
    riassunto_breve: str | None = None
    messaggio_originale: str | None = None


@dataclass
class BenchmarkRow:
    name: str
    wall_ms: float
    tokens_est: int | None
    categoria: str | None
    priorita: str | None = None
    riassunto_breve: str | None = None
    azione_eseguita: str | None = None
    cache_policy_hits: int | None = None
    cache_ltm_hits: int | None = None


@dataclass
class L18aGuardrailRow:
    label: str
    allowed: bool
    vectors: str = ""
    severity: str = ""
    ticket_input: str = ""
    alert_id: int | None = None


@dataclass
class L18aAlertSummary:
    id: int
    severity: str
    alert_type: str
    blocked_stage: str
    input_excerpt: str


@dataclass
class L18bGateRow:
    step: str
    allowed: bool
    detail: str = ""


@dataclass
class Week12ReportBuilder:
    """Accumula risultati demo L15–L18 e genera HTML."""

    root_scenario: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    l15: L15Section | None = None
    triage_rows: list[TriageScenarioRow] = field(default_factory=list)
    l17a_runs: list[L17aRunRow] = field(default_factory=list)
    l17b_rows: list[BenchmarkRow] = field(default_factory=list)
    l18a_rows: list[L18aGuardrailRow] = field(default_factory=list)
    l18b_rows: list[L18bGateRow] = field(default_factory=list)
    l18a_alerts: list[L18aAlertSummary] = field(default_factory=list)
    l17_ticket: str | None = None
    skipped: list[SkippedScenario] = field(default_factory=list)

    def record_skip(self, scenario_id: str, reason: str) -> None:
        self.skipped.append(SkippedScenario(scenario_id=scenario_id, reason=reason))

    def set_l15(
        self,
        *,
        ticket: str,
        topologies: list[str],
        agents: list[dict[str, Any]],
        handoff: dict[str, Any],
    ) -> None:
        self.l15 = L15Section(
            ticket=ticket,
            topologies=topologies,
            agents=agents,
            handoff=handoff,
        )

    def add_triage_scenario(
        self,
        *,
        scenario_id: str,
        lesson: str,
        title: str,
        wall_ms: float | None = None,
        result: dict[str, Any] | None = None,
        skipped: bool = False,
        skip_reason: str | None = None,
        ticket_input: str | None = None,
        orchestrator: str | None = None,
    ) -> None:
        self.triage_rows.append(
            TriageScenarioRow(
                scenario_id=scenario_id,
                lesson=lesson,
                title=title,
                wall_ms=wall_ms,
                result=result,
                skipped=skipped,
                skip_reason=skip_reason,
                ticket_input=ticket_input,
                orchestrator=orchestrator,
            )
        )

    def set_l17_ticket(self, ticket: str) -> None:
        self.l17_ticket = ticket

    def set_l18a_alerts(self, alerts: list[L18aAlertSummary]) -> None:
        self.l18a_alerts = alerts

    def set_l17a_runs(self, runs: list[L17aRunRow]) -> None:
        self.l17a_runs = runs

    def set_l17b_rows(self, rows: list[BenchmarkRow]) -> None:
        self.l17b_rows = rows

    def set_l18a_rows(self, rows: list[L18aGuardrailRow]) -> None:
        self.l18a_rows = rows

    def set_l18b_rows(self, rows: list[L18bGateRow]) -> None:
        self.l18b_rows = rows

    def scenario_status(self, scenario_id: str) -> str:
        """Stato scenario per riepilogo HTML: Eseguito | Saltato | Non eseguito."""
        if any(s.scenario_id == scenario_id for s in self.skipped):
            return "Saltato"
        if scenario_id == "l15" and self.l15 is not None:
            return "Eseguito"
        if scenario_id in ("l16a", "l16b"):
            for row in self.triage_rows:
                if row.scenario_id == scenario_id:
                    return "Saltato" if row.skipped else "Eseguito"
        if scenario_id == "l17a" and self.l17a_runs:
            return "Eseguito"
        if scenario_id == "l17b" and self.l17b_rows:
            return "Eseguito"
        if scenario_id == "l18a" and self.l18a_rows:
            return "Eseguito"
        if scenario_id == "l18b" and self.l18b_rows:
            return "Eseguito"
        return "Non eseguito"

    def skip_reason_for(self, scenario_id: str) -> str | None:
        for item in self.skipped:
            if item.scenario_id == scenario_id:
                return item.reason
        for row in self.triage_rows:
            if row.scenario_id == scenario_id and row.skipped:
                return row.skip_reason
        return None

    def write_html(self, path: Path | None = None) -> Path:
        out = path or WEEK12_REPORT_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_week12_html(self), encoding="utf-8")
        return out

    def to_dict(self) -> dict[str, Any]:
        """Serializza il report per JSON (revisione post-lab, diff tra run)."""
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["scenario_summary"] = {
            scenario_id: {
                "status": self.scenario_status(scenario_id),
                "reason": self.skip_reason_for(scenario_id),
            }
            for scenario_id, _, _ in LESSON_SCENARIOS
        }
        data["trace_note"] = (
            "Trace completo step-by-step: logs/activity.jsonl "
            "(non incluso in questo report)."
        )
        return data

    def write_json(self, path: Path | None = None) -> Path:
        out = path or WEEK12_REPORT_JSON_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return out


def _esc(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value))


def _priority_badge(priorita: str | None) -> str:
    if not priorita:
        return '<span class="badge">—</span>'
    cls = {
        "LOW": "badge low",
        "MEDIUM": "badge medium",
        "HIGH": "badge high",
        "CRITICAL": "badge critical",
    }.get(priorita, "badge")
    return f'<span class="{cls}">{_esc(priorita)}</span>'


def _placeholder_section(title: str, message: str) -> str:
    return f"""
        <section>
          <h2>{title}</h2>
          <p class="meta">{_esc(message)}</p>
        </section>"""


def _render_details_block(title: str, body_html: str) -> str:
    return f"""
          <details>
            <summary>{_esc(title)}</summary>
            {body_html}
          </details>"""


def _render_kv_table(fields: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>"
        for k, v in fields.items()
        if v is not None and v != ""
    )
    return f'<table class="kv"><tbody>{rows}</tbody></table>'


def _render_json_pre(data: Any) -> str:
    return f'<pre class="json">{_esc(json.dumps(data, ensure_ascii=False, indent=2))}</pre>'


def _triage_detail_body(row: TriageScenarioRow) -> str:
    res = row.result or {}
    fields = {
        "Ticket input": row.ticket_input,
        "Orchestratore": row.orchestrator,
        "Tempo": f"{row.wall_ms:.0f} ms" if row.wall_ms is not None else None,
        "Categoria": res.get("categoria"),
        "Priorità": res.get("priorita"),
        "Riassunto": res.get("riassunto_breve"),
        "Analisi problema": res.get("analisi_problema"),
        "Azione eseguita": res.get("azione_eseguita"),
        "Messaggio originale": res.get("messaggio_originale"),
    }
    return _render_kv_table(fields) + "<h4>TriageResult (JSON)</h4>" + _render_json_pre(res)


def _l17a_run_detail_body(run: L17aRunRow) -> str:
    fields = {
        "Run": run.label,
        "Tempo": f"{run.wall_ms:.0f} ms",
        "Token stimati": run.tokens_est,
        "Pruning": "sì" if run.enable_pruning else "no",
        "Cache": "sì" if run.enable_cache else "no",
        "Compact output": "sì" if run.enable_compact_output else "no",
        "Categoria": run.categoria,
        "Priorità": run.priorita,
        "Riassunto": run.riassunto_breve,
        "Analisi problema": run.analisi_problema,
        "Azione eseguita": run.azione_eseguita,
    }
    return _render_kv_table(fields)


def _l17b_row_detail_body(row: BenchmarkRow) -> str:
    fields = {
        "Pipeline": row.name,
        "Tempo": f"{row.wall_ms:.0f} ms",
        "Token stimati": row.tokens_est,
        "Categoria": row.categoria,
        "Priorità": row.priorita,
        "Riassunto": row.riassunto_breve,
        "Azione eseguita": row.azione_eseguita,
        "Cache policy hits": row.cache_policy_hits,
        "Cache LTM hits": row.cache_ltm_hits,
    }
    return _render_kv_table(fields)


def _l18a_row_detail_body(row: L18aGuardrailRow) -> str:
    fields = {
        "Etichetta": row.label,
        "Esito": "ALLOWED" if row.allowed else "BLOCKED",
        "Ticket input": row.ticket_input,
        "Vettori": row.vectors or None,
        "Severità": row.severity or None,
        "Alert SQLite id": row.alert_id,
    }
    return _render_kv_table(fields)


def _l18b_row_detail_body(row: L18bGateRow) -> str:
    fields = {
        "Step": row.step,
        "Esito": "OK" if row.allowed else "DENIED",
        "Dettaglio": row.detail,
    }
    return _render_kv_table(fields)


def _render_l16_section(report: Week12ReportBuilder) -> str:
    rows_html = []
    detail_blocks: list[str] = []
    for scenario_id, _, label in LESSON_SCENARIOS:
        if not scenario_id.startswith("l16"):
            continue
        row = next((r for r in report.triage_rows if r.scenario_id == scenario_id), None)
        if row and row.skipped:
            rows_html.append(
                f"<tr><td>{_esc(scenario_id)}</td><td>{_esc(label)}</td>"
                f'<td colspan="4" class="skip">{_esc(row.skip_reason)}</td></tr>'
            )
        elif row and row.result:
            res = row.result
            rows_html.append(
                f"<tr><td>{_esc(scenario_id)}</td><td>{_esc(label)}</td>"
                f"<td>{_esc(res.get('categoria'))}</td>"
                f"<td>{_priority_badge(res.get('priorita'))}</td>"
                f"<td>{row.wall_ms:.0f} ms</td>"
                f"<td>{_esc(res.get('riassunto_breve'))}</td></tr>"
            )
            detail_blocks.append(
                _render_details_block(
                    f"Dettaglio strutturato — {scenario_id}",
                    _triage_detail_body(row),
                )
            )
        else:
            rows_html.append(
                f"<tr><td>{_esc(scenario_id)}</td><td>{_esc(label)}</td>"
                f'<td colspan="4" class="meta">Non eseguito in questa run</td></tr>'
            )
    return f"""
        <section>
          <h2>Lezione 16 — Orchestrazione multi-agent</h2>
          <table>
            <thead>
              <tr>
                <th>Scenario</th><th>Descrizione</th><th>Categoria</th>
                <th>Priorità</th><th>Tempo</th><th>Riassunto</th>
              </tr>
            </thead>
            <tbody>{"".join(rows_html)}</tbody>
          </table>
        </section>{"".join(detail_blocks)}"""


def render_week12_html(report: Week12ReportBuilder) -> str:
    """Renderizza report HTML self-contained."""
    generated = report.started_at.strftime("%Y-%m-%d %H:%M UTC")
    sections: list[str] = []

    summary_rows = []
    for scenario_id, lesson, label in LESSON_SCENARIOS:
        status = report.scenario_status(scenario_id)
        reason = report.skip_reason_for(scenario_id) if status == "Saltato" else ""
        status_cell = _esc(status)
        if status == "Saltato" and reason:
            status_cell = f'<span class="skip">{status_cell}</span>'
        summary_rows.append(
            f"<tr><td><code>{_esc(scenario_id)}</code></td>"
            f"<td>L{lesson}</td><td>{_esc(label)}</td>"
            f"<td>{status_cell}</td><td>{_esc(reason or '—')}</td></tr>"
        )
    sections.append(
        f"""
        <section>
          <h2>Riepilogo scenari (Lezioni 15–18)</h2>
          <table>
            <thead>
              <tr><th>Scenario</th><th>Lezione</th><th>Descrizione</th><th>Stato</th><th>Note</th></tr>
            </thead>
            <tbody>{"".join(summary_rows)}</tbody>
          </table>
        </section>"""
    )

    if report.skipped:
        rows = "".join(
            f"<tr><td>{_esc(s.scenario_id)}</td><td>{_esc(s.reason)}</td></tr>"
            for s in report.skipped
        )
        sections.append(
            f"""
        <section>
          <h2>Scenari saltati</h2>
          <table><thead><tr><th>Scenario</th><th>Motivo</th></tr></thead>
          <tbody>{rows}</tbody></table>
        </section>"""
        )

    if report.l15:
        l15 = report.l15
        topo_list = "".join(f"<li>{_esc(t)}</li>" for t in l15.topologies)
        agent_rows = "".join(
            f"<tr><td>{_esc(a.get('name'))}</td><td>{_esc(a.get('role'))}</td>"
            f"<td>{_esc(', '.join(a.get('tools', [])))}</td></tr>"
            for a in l15.agents
        )
        handoff_json = _esc(json.dumps(l15.handoff, ensure_ascii=False, indent=2))
        l15_details = _render_details_block(
            "Dettaglio strutturato — hand-off e squadra",
            _render_kv_table({"Ticket demo": l15.ticket})
            + "<h4>SharedHandoffContext</h4>"
            + f'<pre class="json">{handoff_json}</pre>',
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 15 — Topologie e Blackboard</h2>
          <p class="meta">Scenario <code>l15</code> · senza chiamate LLM</p>
          <p><strong>Ticket demo:</strong> {_esc(l15.ticket)}</p>
          <h3>Topologie</h3>
          <ul>{topo_list}</ul>
          <h3>Squadra Impesud</h3>
          <table>
            <thead><tr><th>Agente</th><th>Ruolo</th><th>Tool</th></tr></thead>
            <tbody>{agent_rows}</tbody>
          </table>
          {l15_details}
        </section>"""
        )

    else:
        msg = (
            report.skip_reason_for("l15") or "Non eseguito in questa run"
            if report.scenario_status("l15") == "Saltato"
            else "Non eseguito in questa run"
        )
        sections.append(_placeholder_section("Lezione 15 — Topologie e Blackboard", msg))

    sections.append(_render_l16_section(report))

    if report.l17a_runs:
        rows = "".join(
            f"<tr><td>{_esc(r.label)}</td><td>{r.wall_ms:.0f}</td><td>{r.tokens_est}</td>"
            f"<td>{'sì' if r.enable_pruning else 'no'}</td>"
            f"<td>{'sì' if r.enable_cache else 'no'}</td>"
            f"<td>{'sì' if r.enable_compact_output else 'no'}</td>"
            f"<td>{_esc(r.categoria)}</td><td>{_priority_badge(r.priorita)}</td></tr>"
            for r in report.l17a_runs
        )
        detail_blocks = "".join(
            _render_details_block(f"Run — {r.label}", _l17a_run_detail_body(r))
            for r in report.l17a_runs
        )
        ticket_line = (
            f'<p class="meta"><strong>Ticket:</strong> {_esc(report.l17_ticket)}</p>'
            if report.l17_ticket
            else ""
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 17a — Confronto ottimizzazioni ReAct</h2>
          {ticket_line}
          <table>
            <thead>
              <tr>
                <th>Run</th><th>ms</th><th>Token stim.</th>
                <th>Pruning</th><th>Cache</th><th>Compact</th>
                <th>Categoria</th><th>Priorità</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          {detail_blocks}
        </section>"""
        )

    else:
        if report.scenario_status("l17a") == "Saltato":
            msg = report.skip_reason_for("l17a") or "Saltato"
        else:
            msg = "Non eseguito in questa run"
        sections.append(_placeholder_section("Lezione 17a — Confronto ottimizzazioni ReAct", msg))

    if report.l17b_rows:
        rows = "".join(
            f"<tr><td>{_esc(r.name)}</td><td>{r.wall_ms:.0f}</td>"
            f"<td>{_esc(r.tokens_est if r.tokens_est is not None else '—')}</td>"
            f"<td>{_esc(r.categoria or '—')}</td></tr>"
            for r in report.l17b_rows
        )
        detail_blocks = "".join(
            _render_details_block(f"Pipeline — {r.name}", _l17b_row_detail_body(r))
            for r in report.l17b_rows
        )
        ticket_line = (
            f'<p class="meta"><strong>Ticket:</strong> {_esc(report.l17_ticket)}</p>'
            if report.l17_ticket
            else ""
        )
        trace_note = (
            '<p class="meta">Trace eventi correlati: <code>logs/activity.jsonl</code> '
            '(evento <code>pipeline_latency_report</code>).</p>'
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 17b — Benchmark multi-pipeline</h2>
          {ticket_line}
          <table>
            <thead>
              <tr><th>Pipeline</th><th>ms</th><th>Token stim.</th><th>Categoria</th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          {detail_blocks}
          {trace_note}
        </section>"""
        )

    else:
        if report.scenario_status("l17b") == "Saltato":
            msg = report.skip_reason_for("l17b") or "Saltato"
        else:
            msg = "Non eseguito in questa run"
        sections.append(_placeholder_section("Lezione 17b — Benchmark multi-pipeline", msg))

    if report.l18a_rows:
        rows = "".join(
            f"<tr><td>{_esc(r.label)}</td>"
            f"<td>{'ALLOWED' if r.allowed else 'BLOCKED'}</td>"
            f"<td>{_esc(r.vectors or '—')}</td>"
            f"<td>{_esc(r.severity or '—')}</td></tr>"
            for r in report.l18a_rows
        )
        detail_blocks = "".join(
            _render_details_block(f"Ticket — {r.label}", _l18a_row_detail_body(r))
            for r in report.l18a_rows
        )
        alert_block = ""
        if report.l18a_alerts:
            alert_rows = "".join(
                f"<tr><td>#{a.id}</td><td>{_esc(a.severity)}</td>"
                f"<td>{_esc(a.alert_type)}</td><td>{_esc(a.blocked_stage)}</td>"
                f"<td>{_esc(a.input_excerpt[:80])}</td></tr>"
                for a in report.l18a_alerts
            )
            alert_block = f"""
          <h3>Ultime allerte SQLite</h3>
          <table>
            <thead>
              <tr><th>ID</th><th>Severità</th><th>Tipo</th><th>Stage</th><th>Estratto</th></tr>
            </thead>
            <tbody>{alert_rows}</tbody>
          </table>"""
        sections.append(
            f"""
        <section>
          <h2>Lezione 18a — Input Guardrail</h2>
          <table>
            <thead>
              <tr><th>Ticket</th><th>Esito</th><th>Vettori</th><th>Severità</th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          {detail_blocks}
          {alert_block}
        </section>"""
        )
    else:
        msg = "Non eseguito in questa run"
        sections.append(_placeholder_section("Lezione 18a — Input Guardrail", msg))

    if report.l18b_rows:
        rows = "".join(
            f"<tr><td>{_esc(r.step)}</td>"
            f"<td>{'OK' if r.allowed else 'DENIED'}</td>"
            f"<td>{_esc(r.detail or '—')}</td></tr>"
            for r in report.l18b_rows
        )
        detail_blocks = "".join(
            _render_details_block(f"Step — {r.step}", _l18b_row_detail_body(r))
            for r in report.l18b_rows
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 18b — Hand-off e tool gate</h2>
          <table>
            <thead>
              <tr><th>Step</th><th>Esito</th><th>Dettaglio</th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          {detail_blocks}
        </section>"""
        )
    else:
        msg = "Non eseguito in questa run"
        sections.append(_placeholder_section("Lezione 18b — Hand-off e tool gate", msg))

    body = "\n".join(sections) if sections else "<p>Nessun risultato registrato.</p>"

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Impesud — Report Demo Settimana 12</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --border: #2a3544;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      padding: 2rem 1rem;
      line-height: 1.5;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.15rem; margin-top: 0; color: var(--accent); }}
    h3 {{ font-size: 1rem; color: var(--muted); }}
    .meta {{ color: var(--muted); font-size: 0.9rem; }}
    section {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ padding: 0.5rem 0.65rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-weight: 600; }}
    table.kv th {{ width: 11rem; color: var(--muted); font-weight: 500; vertical-align: top; }}
    table.kv td {{ word-break: break-word; }}
    h4 {{ font-size: 0.9rem; color: var(--muted); margin: 1rem 0 0.5rem; }}
    pre.json {{
      background: #0b1018;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
      overflow-x: auto;
      font-size: 0.8rem;
    }}
    .badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 600;
      background: #334155;
    }}
    .badge.low {{ background: #14532d; }}
    .badge.medium {{ background: #713f12; }}
    .badge.high {{ background: #7c2d12; }}
    .badge.critical {{ background: #7f1d1d; }}
    .skip {{ color: #fbbf24; font-style: italic; }}
    details {{ margin: 0.5rem 0 1rem; }}
    summary {{ cursor: pointer; color: var(--muted); }}
    footer {{ margin-top: 2rem; color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Report Demo — Settimana 12–13 (L15–L18)</h1>
      <p class="meta">
        Scenario CLI: <code>{_esc(report.root_scenario)}</code> ·
        Generato: {generated}
      </p>
    </header>
    {body}
    <footer>
      Agentic Triage System — report sintesi (HTML) + dati strutturati (JSON).
      Trace completo: <code>logs/activity.jsonl</code> ·
      JSON gemello: <code>logs/week12_demo_report.json</code>
    </footer>
  </div>
</body>
</html>"""
