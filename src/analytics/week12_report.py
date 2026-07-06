"""Report HTML demo Settimana 12 (Lezioni 15–17)."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paths import WEEK12_REPORT_PATH


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


@dataclass
class BenchmarkRow:
    name: str
    wall_ms: float
    tokens_est: int | None
    categoria: str | None


@dataclass
class Week12ReportBuilder:
    """Accumula risultati demo L15–L17 e genera HTML."""

    root_scenario: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    l15: L15Section | None = None
    triage_rows: list[TriageScenarioRow] = field(default_factory=list)
    l17a_runs: list[L17aRunRow] = field(default_factory=list)
    l17b_rows: list[BenchmarkRow] = field(default_factory=list)
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
            )
        )

    def set_l17a_runs(self, runs: list[L17aRunRow]) -> None:
        self.l17a_runs = runs

    def set_l17b_rows(self, rows: list[BenchmarkRow]) -> None:
        self.l17b_rows = rows

    def write_html(self, path: Path | None = None) -> Path:
        out = path or WEEK12_REPORT_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_week12_html(self), encoding="utf-8")
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


def render_week12_html(report: Week12ReportBuilder) -> str:
    """Renderizza report HTML self-contained."""
    generated = report.started_at.strftime("%Y-%m-%d %H:%M UTC")
    sections: list[str] = []

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
          <h3>SharedHandoffContext (simulato)</h3>
          <pre class="json">{handoff_json}</pre>
        </section>"""
        )

    if report.triage_rows:
        rows_html = []
        for row in report.triage_rows:
            if row.skipped:
                rows_html.append(
                    f"<tr><td>{_esc(row.scenario_id)}</td><td>{_esc(row.title)}</td>"
                    f'<td colspan="4" class="skip">{_esc(row.skip_reason)}</td></tr>'
                )
                continue
            res = row.result or {}
            rows_html.append(
                f"<tr><td>{_esc(row.scenario_id)}</td><td>{_esc(row.title)}</td>"
                f"<td>{_esc(res.get('categoria'))}</td>"
                f"<td>{_priority_badge(res.get('priorita'))}</td>"
                f"<td>{row.wall_ms:.0f} ms</td>"
                f"<td>{_esc(res.get('riassunto_breve'))}</td></tr>"
            )
        sections.append(
            f"""
        <section>
          <h2>Lezione 16 — Orchestrazione multi-agent</h2>
          <table>
            <thead>
              <tr>
                <th>Scenario</th><th>Titolo</th><th>Categoria</th>
                <th>Priorità</th><th>Tempo</th><th>Riassunto</th>
              </tr>
            </thead>
            <tbody>{"".join(rows_html)}</tbody>
          </table>
        </section>"""
        )

        for row in report.triage_rows:
            if row.result and not row.skipped:
                detail = _esc(json.dumps(row.result, ensure_ascii=False, indent=2))
                sections.append(
                    f"""
          <details>
            <summary>Dettaglio JSON — {_esc(row.scenario_id)}</summary>
            <pre class="json">{detail}</pre>
          </details>"""
                )

    if report.l17a_runs:
        rows = "".join(
            f"<tr><td>{_esc(r.label)}</td><td>{r.wall_ms:.0f}</td><td>{r.tokens_est}</td>"
            f"<td>{'sì' if r.enable_pruning else 'no'}</td>"
            f"<td>{'sì' if r.enable_cache else 'no'}</td>"
            f"<td>{'sì' if r.enable_compact_output else 'no'}</td>"
            f"<td>{_esc(r.categoria)}</td><td>{_priority_badge(r.priorita)}</td></tr>"
            for r in report.l17a_runs
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 17a — Confronto ottimizzazioni ReAct</h2>
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
        </section>"""
        )

    if report.l17b_rows:
        rows = "".join(
            f"<tr><td>{_esc(r.name)}</td><td>{r.wall_ms:.0f}</td>"
            f"<td>{_esc(r.tokens_est if r.tokens_est is not None else '—')}</td>"
            f"<td>{_esc(r.categoria or '—')}</td></tr>"
            for r in report.l17b_rows
        )
        sections.append(
            f"""
        <section>
          <h2>Lezione 17b — Benchmark multi-pipeline</h2>
          <table>
            <thead>
              <tr><th>Pipeline</th><th>ms</th><th>Token stim.</th><th>Categoria</th></tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </section>"""
        )

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
      <h1>Report Demo — Settimana 12 (L15–L17)</h1>
      <p class="meta">
        Scenario CLI: <code>{_esc(report.root_scenario)}</code> ·
        Generato: {generated}
      </p>
    </header>
    {body}
    <footer>
      Agentic Triage System — branch lesson-17-multi-agent-performance
    </footer>
  </div>
</body>
</html>"""
