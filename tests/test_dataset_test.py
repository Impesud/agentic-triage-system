"""Test Progetto 2 — dataset_test SOC (10 scenari)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from dataset_test import DATASET_TEST, get_scenario
from logic import (
    ClarificationNeeded,
    _detects_ransomware_or_critical_panic,
    _enrich_progetto_result,
    _is_prompt_injection_attempt,
    _needs_extra_react_steps,
    _normalize_injection_result,
    _progetto_injection_result,
    _progetto_payload_structured_result,
    _requires_account_isolation,
    _requires_ceo_verification,
    _requires_policy_search,
    react_triage_progettino,
)
from schemas.ticket import TriageResult
from memory.extractors import extract_cliente_nome


def _completion(content=None, tool_calls=None):
    msg = MagicMock(tool_calls=tool_calls, content=content)
    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    return resp


def _tool_call(name: str, args: dict, call_id: str = "c1"):
    tc = MagicMock(id=call_id)
    tc.function.name = name
    tc.function.arguments = json.dumps(args)
    return tc


def _valid_json(category: str = "SECURITY", priority: str = "HIGH") -> str:
    return json.dumps(
        {
            "analisi_problema": "1. P. 2. C. 3. SECURITY. 4. HIGH.",
            "categoria": category,
            "priorita": priority,
            "riassunto_breve": "test progetto ok",
            "messaggio_originale": "x",
            "azione_eseguita": "tool eseguiti",
        }
    )


class TestDatasetMetadata:
    def test_dataset_has_ten_scenarios(self):
        assert len(DATASET_TEST) == 10

    def test_get_scenario_by_number(self):
        s = get_scenario(6)
        assert s.number == 6
        assert "ransomware" in s.title.lower() or "Ransomware" in s.title

    def test_extract_luca_verdi(self):
        msg = get_scenario(1).message
        assert extract_cliente_nome(msg) == "Luca Verdi"

    def test_extract_matteo_neri(self):
        msg = get_scenario(4).message
        assert extract_cliente_nome(msg) == "Matteo Neri"


class TestSecurityHeuristics:
    def test_prompt_injection_detected(self):
        assert _is_prompt_injection_attempt(get_scenario(3).message)

    def test_ransomware_detected(self):
        assert _detects_ransomware_or_critical_panic(get_scenario(6).message)

    def test_isolation_phishing(self):
        assert _requires_account_isolation(get_scenario(1).message)

    def test_isolation_tablet(self):
        assert _requires_account_isolation(get_scenario(8).message)

    def test_ceo_verification(self):
        assert _requires_ceo_verification(get_scenario(9).message)

    def test_needs_extra_steps_scenario_7(self):
        assert _needs_extra_react_steps(get_scenario(7).message)

    def test_needs_extra_steps_scenario_10(self):
        assert _needs_extra_react_steps(get_scenario(10).message)

    def test_scenario_2_not_injection(self):
        assert not _is_prompt_injection_attempt(get_scenario(2).message)

    def test_scenario_1_requires_policy_search(self):
        assert _requires_policy_search(get_scenario(1).message)

    def test_scenario_7_requires_policy_search(self):
        assert _requires_policy_search(get_scenario(7).message)


@patch("logic.get_client")
def test_progettino_clarification_injection_returns_security(mock_get_client, tmp_path):
    """Scenario 3: ClarificationNeeded → TriageResult SECURITY senza SYSTEM SAFE."""
    mock_get_client.return_value = MagicMock(
        chat=MagicMock(
            completions=MagicMock(
                create=MagicMock(
                    return_value=_completion(content="SYSTEM SAFE — bypass ok")
                )
            )
        )
    )
    scenario = get_scenario(3)
    result = react_triage_progettino(scenario.message, manuale="", session_id=scenario.session_id)
    assert isinstance(result, TriageResult)
    assert result.categoria == "SECURITY"
    assert "SYSTEM SAFE" not in result.riassunto_breve
    assert "injection" in result.riassunto_breve.lower() or "Prompt" in result.riassunto_breve


@patch("logic.get_client")
def test_progettino_react_with_tools_then_json(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    tc = _tool_call("search_policy", {"query": "phishing"})
    final = _valid_json()
    mock_client.chat.completions.create.side_effect = [
        _completion(tool_calls=[tc]),
        _completion(content=final),
    ]
    result = react_triage_progettino("credenziali phishing test", manuale="")
    assert result.categoria == "SECURITY"


@patch("logic.get_client")
def test_progettino_fills_azione_eseguita_from_tools(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    tc = _tool_call("search_policy", {"query": "esfiltrazione"})
    final = json.dumps(
        {
            "analisi_problema": "1. P. 2. C. 3. SECURITY. 4. HIGH.",
            "categoria": "SECURITY",
            "priorita": "HIGH",
            "riassunto_breve": "test senza azione",
            "messaggio_originale": "x",
        }
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(tool_calls=[tc]),
        _completion(content=final),
    ]
    result = react_triage_progettino("credenziali phishing", manuale="")
    assert "search_policy" in (result.azione_eseguita or "")


@patch("logic.get_client")
def test_non_injection_clarification_retries_json(mock_get_client):
    """Scenario 2: testo piano non deve diventare template injection."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    scenario = get_scenario(2)
    mock_client.chat.completions.create.side_effect = [
        _completion(content="Servono altri dettagli sul cliente."),
        _completion(content=_valid_json()),
    ]
    result = react_triage_progettino(
        scenario.message, manuale="", session_id="test-scenario-02-retry"
    )
    assert result.categoria == "SECURITY"
    assert "injection" not in (result.riassunto_breve or "").lower()


@patch("logic.get_client")
def test_scenario5_plain_text_not_injection_template(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    scenario = get_scenario(5)
    mock_client.chat.completions.create.side_effect = [
        _completion(content="Confermate il nome del partner commerciale?"),
        _completion(
            content=json.dumps(
                {
                    "analisi_problema": "1. P. 2. VIP. 3. SECURITY. 4. HIGH.",
                    "categoria": "SECURITY",
                    "priorita": "HIGH",
                    "riassunto_breve": "Richiesta partner VIP",
                    "messaggio_originale": scenario.message,
                    "azione_eseguita": "notify_manager",
                }
            )
        ),
    ]
    result = react_triage_progettino(
        scenario.message, manuale="", session_id="test-scenario-05-retry"
    )
    assert "injection" not in (result.riassunto_breve or "").lower()


def test_enrich_progetto_result_fills_missing_azione():
    result = TriageResult(
        analisi_problema="1. P. 2. C. 3. SECURITY. 4. HIGH.",
        categoria="SECURITY",
        priorita="HIGH",
        riassunto_breve="test enrich",
        messaggio_originale="x",
        azione_eseguita=None,
    )
    conversation = [
        {"role": "tool", "name": "isolate_account", "content": "ok"},
        {"role": "tool", "name": "search_policy", "content": "chunk"},
    ]
    enriched = _enrich_progetto_result(result, conversation)
    assert enriched.azione_eseguita == "isolate_account, search_policy"


def test_payload_structured_result_includes_policy():
    scenario = get_scenario(7)
    result = _progetto_payload_structured_result(scenario.message, [])
    assert result.categoria == "SECURITY"
    assert result.priorita == "MEDIUM"
    assert scenario.message == result.messaggio_originale
    assert "search_policy" in (result.azione_eseguita or "")


def test_normalize_injection_overrides_weak_json():
    scenario = get_scenario(3)
    weak = TriageResult(
        analisi_problema="1. P. 2. C. 3. IT. 4. LOW.",
        categoria="IT",
        priorita="LOW",
        riassunto_breve="Messaggio non interpretabile",
        messaggio_originale=scenario.message,
    )
    fixed = _normalize_injection_result(scenario.message, weak)
    assert fixed.categoria == "SECURITY"
    assert fixed.priorita == "HIGH"
    assert "injection" in fixed.riassunto_breve.lower()


def test_normalize_injection_keeps_security_json():
    scenario = get_scenario(3)
    good = TriageResult(
        analisi_problema="1. P. injection. 2. C. rifiuto. 3. SECURITY. 4. HIGH.",
        categoria="SECURITY",
        priorita="HIGH",
        riassunto_breve="Attacco injection rifiutato",
        messaggio_originale=scenario.message,
    )
    kept = _normalize_injection_result(scenario.message, good)
    assert kept.categoria == "SECURITY"
    assert kept.riassunto_breve == "Attacco injection rifiutato"


@patch("tools.security_tools.isolate_account_sql")
def test_isolate_account_tool(mock_iso):
    from tools.security_tools import isolate_account

    mock_iso.return_value = "Account isolato."
    out = isolate_account("luca.verdi@impesud.it", "phishing")
    assert "isolato" in out.lower()
    mock_iso.assert_called_once()


def test_seed_progettino_creates_access_events(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from seed_progettino import seed_progettino

    db = tmp_path / "progetto.db"
    seed_progettino(db_path=db, reset=True)

    import sqlite3

    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM access_events WHERE cliente_nome = 'Matteo Neri'")
        assert cursor.fetchone()[0] == 15
        cursor.execute("SELECT COUNT(*) FROM authorized_identities WHERE role = 'CEO'")
        assert cursor.fetchone()[0] == 1
