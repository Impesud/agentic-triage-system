"""Test orchestrazione multi-agent Lezione 16."""

import json
from unittest.mock import MagicMock, patch

import pytest

from logic import multi_agent_triage, triage_message
from orchestration.crew_pipeline import build_resolver_task_description, crew_triage
from orchestration.models import CommunicationTopology
from orchestration.result_parser import finalize_multi_agent_output
from orchestration.topologies import simulate_analyst_handoff
from schemas.ticket import TriageResult

_VALID_JSON = (
    '{"analisi_problema":"1. P. 2. C. 3. SALES. 4. HIGH.",'
    '"categoria":"SALES","priorita":"HIGH","riassunto_breve":"Budget AI manager",'
    '"messaggio_originale":"ticket demo"}'
)


def test_handoff_injected_in_resolver_prompt():
    handoff = simulate_analyst_handoff(
        "Sono Marco Rossi. Budget 15000 euro.",
        topology=CommunicationTopology.SEQUENTIAL,
    )
    description = build_resolver_task_description("ticket demo", handoff.model_dump_json())
    assert "Marco" in description
    assert "SharedHandoffContext" in description or "cliente_nome" in description


def test_finalize_multi_agent_output_valid():
    result = finalize_multi_agent_output(_VALID_JSON, "ticket demo")
    assert isinstance(result, TriageResult)
    assert result.categoria == "SALES"


def test_finalize_multi_agent_output_fallback():
    result = finalize_multi_agent_output("non-json", "ticket demo")
    assert result.categoria == "GENERAL"
    assert result.azione_eseguita


@patch("orchestration.crew_pipeline.Crew")
@patch("orchestration.crew_pipeline.ensure_framework_env")
def test_crew_pipeline_mocked(mock_env, mock_crew_cls):
    mock_env.return_value = "sk-test"
    kickoff_result = MagicMock()
    kickoff_result.raw = _VALID_JSON
    mock_crew_cls.return_value.kickoff.return_value = kickoff_result

    result = crew_triage("ticket demo", "Manuale IT")
    assert result.categoria == "SALES"
    mock_crew_cls.return_value.kickoff.assert_called_once()


@patch("orchestration.autogen_team.asyncio.run")
@patch("orchestration.autogen_team.ensure_framework_env")
def test_autogen_team_mocked(mock_env, mock_asyncio_run):
    mock_env.return_value = "sk-test"
    mock_asyncio_run.return_value = _VALID_JSON

    from orchestration.autogen_team import autogen_triage

    result = autogen_triage("ticket demo", "Manuale IT")
    assert result.categoria == "SALES"


def test_multi_agent_triage_missing_deps(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "orchestration.crew_pipeline":
            raise ImportError("No module named 'crewai'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="multiagent"):
        multi_agent_triage("x", "m", orchestrator="crewai")


@patch("logic.get_client")
def test_triage_message_unchanged_for_benchmark(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    json_out = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(tool_calls=None, content=json_out))]
    )
    result = triage_message("help", manuale="Manuale IT")
    assert result.categoria == "IT"
