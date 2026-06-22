import json
from unittest.mock import MagicMock, patch

from logic import (
    _build_context_text,
    _detects_angry_sentiment,
    _emergency_triage_result,
    _extract_max_budget_eur,
    _requires_vip_escalation,
    react_triage,
)
from prompts.triage_v1 import build_chat_messages
from schemas.ticket import TriageResult


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


def test_build_chat_messages_includes_history():
    history = [
        {"role": "user", "content": "Il server non si avvia."},
        {"role": "assistant", "content": "Qual è l'ID del server?"},
    ]
    messages = build_chat_messages("È il server-X.", manuale="", history=history)
    assert messages[0]["role"] == "system"
    assert messages[1:3] == history
    assert messages[-1]["role"] == "user"
    assert "server-X" in messages[-1]["content"]


def test_build_context_text_joins_thread():
    history = [{"role": "user", "content": "Sono Marco."}]
    ctx = _build_context_text("Server down.", history)
    assert "Marco" in ctx
    assert "Server down" in ctx


def test_extract_max_budget_eur():
    assert _extract_max_budget_eur("budget di 15.000€ per il progetto") == 15000
    assert _extract_max_budget_eur("budget di 8.000 euro") == 8000
    assert _extract_max_budget_eur("nessun importo") is None


def test_detects_angry_sentiment():
    angry = (
        "SONO FURIOSO! Ho perso 20.000 euro. INACCETTABILE! Vi denuncio e chiamo l'avvocato!"
    )
    calm = "Buongiorno, vorrei informazioni sul corso base."
    assert _detects_angry_sentiment(angry) is True
    assert _detects_angry_sentiment(calm) is False


def test_requires_vip_escalation_threshold():
    assert _requires_vip_escalation("abbiamo 15.000€ approvati") is True
    assert _requires_vip_escalation("budget di 8.000 euro") is False
    assert _requires_vip_escalation("budget esatto 10.000€") is False


def test_emergency_triage_result_is_valid_pydantic():
    result = _emergency_triage_result("input di test")
    assert isinstance(result, TriageResult)
    assert result.categoria == "GENERAL"
    assert result.priorita == "CRITICAL"
    assert result.azione_eseguita == "Emergency Fallback attivato"
    assert "FALLBACK" in result.riassunto_breve


@patch("logic.get_client")
def test_react_triage_with_tool_then_json(mock_get_client, tmp_path, monkeypatch):
    import paths as paths_module
    from tools.logger import log_triage_to_sqlite

    monkeypatch.setattr(paths_module, "TRIAGE_DB_PATH", tmp_path / "react.db")
    log_triage_to_sqlite(
        {
            "cliente_nome": "Marco Rossi",
            "categoria": "SALES",
            "priorita": "HIGH",
            "sentiment": "NEUTRALE",
            "riassunto_breve": "Progetto AI precedente",
            "lingua": "Italiano",
            "azione_eseguita": "Nessuna",
        }
    )

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    tc = _tool_call("search_long_term_history", {"cliente_nome": "Marco Rossi"})
    final = (
        '{"analisi_problema":"1. P. 2. Storico DB. 3. SALES. 4. HIGH.",'
        '"categoria":"SALES","priorita":"HIGH","riassunto_breve":"Budget AI manager",'
        '"messaggio_originale":"Marco Rossi budget 15k"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(tool_calls=[tc]),
        _completion(content=final),
    ]

    result = react_triage(
        "Sono Marco Rossi, budget 15.000€, voglio un manager.",
        manuale="Manuale IT",
    )

    assert result.categoria == "SALES"
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_react_max_steps_fallback(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    tc = _tool_call("search_policy", {"query": "sconto"})
    mock_client.chat.completions.create.return_value = _completion(tool_calls=[tc])

    result = react_triage("test loop infinito", manuale="", max_steps=4)

    assert "Fallback" in (result.azione_eseguita or "")
    assert mock_client.chat.completions.create.call_count == 4


@patch("logic.get_client")
def test_react_self_correction_in_loop(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    invalid = '{"categoria":"IT"}'
    valid = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(content=invalid),
        _completion(content=valid),
    ]

    result = react_triage("help", manuale="", max_steps=4)

    assert result.categoria == "IT"
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_short_term_store_preserves_session(mock_get_client):
    from logic import _SHORT_TERM_STORE

    _SHORT_TERM_STORE.clear()
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    json_out = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"turno uno",'
        '"messaggio_originale":"ticket uno"}'
    )
    json_out_2 = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"turno due",'
        '"messaggio_originale":"ticket due"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(content=json_out),
        _completion(content=json_out_2),
    ]

    react_triage("ticket uno", manuale="", session_id="session_test")
    messages_before = len(_SHORT_TERM_STORE["session_test"])
    react_triage("ticket due", manuale="", session_id="session_test")

    assert len(_SHORT_TERM_STORE["session_test"]) > messages_before
    assert mock_client.chat.completions.create.call_count == 2
    _SHORT_TERM_STORE.clear()
