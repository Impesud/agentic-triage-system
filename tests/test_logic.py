import json
from unittest.mock import MagicMock, patch

import pytest

from logic import (
    MAX_TRIAGE_JSON_RETRIES,
    ReactRunMetrics,
    TriageRunMetrics,
    _append_fallback_tools,
    _build_context_text,
    _detects_angry_sentiment,
    _emergency_triage_result,
    _extract_max_budget_eur,
    _requires_vip_escalation,
    react_triage,
    triage_message,
)
from schemas.ticket import TriageResult
from prompts.triage_v1 import build_chat_messages


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


@patch("logic.get_client")
def test_triage_message_without_tools(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    json_out = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.return_value = _completion(content=json_out)

    result = triage_message("help", manuale="Manuale IT")

    assert result.categoria == "IT"
    mock_client.chat.completions.create.assert_called_once()


@patch("logic.get_client")
def test_triage_message_return_metrics(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    json_out = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.return_value = _completion(content=json_out)

    outcome = triage_message("help", manuale="Manuale IT", return_metrics=True)
    assert isinstance(outcome, tuple)
    result, metrics = outcome
    assert result.categoria == "IT"
    assert isinstance(metrics, TriageRunMetrics)
    assert metrics.tokens_est > 0


@patch("logic.get_client")
def test_triage_message_with_tool(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    tc = _tool_call("search_policy", {"query": "sconto"})
    final = (
        '{"analisi_problema":"1. P. 2. POLICY. 3. SALES. 4. MEDIUM.",'
        '"categoria":"SALES","priorita":"MEDIUM","riassunto_breve":"sconto",'
        '"messaggio_originale":"sconto?"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(tool_calls=[tc]),
        _completion(content=final),
    ]

    result = triage_message("sconto?", manuale="")

    assert result.categoria == "SALES"
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_triage_message_empty_response_raises(mock_get_client):
    mock_get_client.return_value = MagicMock(
        chat=MagicMock(
            completions=MagicMock(
                create=MagicMock(return_value=_completion(content=None))
            )
        )
    )
    with pytest.raises(ValueError, match="Risposta vuota"):
        triage_message("x", manuale="")


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


@patch("logic.get_client")
def test_vip_escalation_fallback_when_llm_skips_tool(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    first_json = (
        '{"analisi_problema":"1. P. 2. C. 3. SALES. 4. HIGH.",'
        '"categoria":"SALES","priorita":"HIGH","riassunto_breve":"VIP",'
        '"messaggio_originale":"15k"}'
    )
    final_json = (
        '{"analisi_problema":"1. P. 2. VIP notify. 3. SALES. 4. HIGH.",'
        '"categoria":"SALES","priorita":"HIGH","riassunto_breve":"VIP",'
        '"messaggio_originale":"15k"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(content=first_json),
        _completion(content=final_json),
    ]

    vip_input = (
        "Buon giorno, budget approvato di 15.000€ per integrazione AI, "
        "vorremmo parlare urgentemente con un responsabile commerciale."
    )
    mock_notify = MagicMock(return_value="ok")
    mock_policy = MagicMock(return_value="Policy: budget VIP escalation")
    with patch.dict(
        "logic.TOOL_MAP",
        {"notify_manager": mock_notify, "search_policy": mock_policy},
        clear=False,
    ):
        result = triage_message(vip_input, manuale="")

    assert result.categoria == "SALES"
    mock_policy.assert_called_once()
    mock_notify.assert_called_once()
    assert mock_notify.call_args.kwargs["priority"] == 4
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_no_vip_fallback_under_threshold(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    json_out = (
        '{"analisi_problema":"1. P. 2. C. 3. SALES. 4. MEDIUM.",'
        '"categoria":"SALES","priorita":"MEDIUM","riassunto_breve":"std",'
        '"messaggio_originale":"8k"}'
    )
    mock_client.chat.completions.create.return_value = _completion(content=json_out)

    standard_input = "Abbiamo un budget di 8.000 euro per formazione Agile."
    mock_notify = MagicMock(return_value="ok")
    with patch.dict("logic.TOOL_MAP", {"notify_manager": mock_notify}, clear=False):
        triage_message(standard_input, manuale="")

    mock_notify.assert_not_called()


@patch("logic.get_client")
def test_angry_sentiment_fallback_policy_then_notify(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    first_json = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. CRITICAL.",'
        '"categoria":"IT","priorita":"CRITICAL","riassunto_breve":"arrabbiato",'
        '"messaggio_originale":"down"}'
    )
    final_json = (
        '{"analisi_problema":"1. P. 2. POLICY+notify. 3. IT. 4. CRITICAL.",'
        '"categoria":"IT","priorita":"CRITICAL","riassunto_breve":"arrabbiato",'
        '"messaggio_originale":"down"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(content=first_json),
        _completion(content=final_json),
    ]

    angry_input = (
        "SONO DELUSO! Portale IN DOWN, perso 20.000 euro. INACCETTABILE! "
        "Chiamo l'avvocato e vi denuncio!"
    )
    mock_notify = MagicMock(return_value="ok")
    mock_policy = MagicMock(return_value="Policy: sentiment ARRABBIATO → notify_manager")
    with patch.dict(
        "logic.TOOL_MAP",
        {"notify_manager": mock_notify, "search_policy": mock_policy},
        clear=False,
    ):
        triage_message(angry_input, manuale="")

    mock_policy.assert_called_once()
    mock_notify.assert_called_once()
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_fallback_appends_tool_messages_to_conversation(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.chat.completions.create.side_effect = [
        _completion(content='{"analisi_problema":"x","categoria":"SALES",'
        '"priorita":"HIGH","riassunto_breve":"v","messaggio_originale":"15k"}'),
        _completion(
            content='{"analisi_problema":"y","categoria":"SALES",'
            '"priorita":"HIGH","riassunto_breve":"v","messaggio_originale":"15k"}'
        ),
    ]

    vip_input = "Budget approvato di 15.000€ per progetto enterprise."
    mock_notify = MagicMock(return_value="ok")
    mock_policy = MagicMock(return_value="Policy: VIP")
    with patch.dict(
        "logic.TOOL_MAP",
        {"notify_manager": mock_notify, "search_policy": mock_policy},
        clear=False,
    ):
        triage_message(vip_input, manuale="")

    second_call_messages = mock_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    tool_messages = [m for m in second_call_messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert any(m.get("name") == "notify_manager" for m in tool_messages)
    assert any(m.get("tool_call_id") == "fallback-nm-1" for m in tool_messages)


def test_fallback_notify_denied_without_policy_evidence():
    conversation: list[dict] = []
    tools_called: set[str] = set()
    pending = [
        ("notify_manager", {"message": "Escalation critica", "priority": 4}, "fallback-nm-1"),
    ]
    _append_fallback_tools(conversation, tools_called, pending)
    tool_messages = [m for m in conversation if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert "[SECURITY DENIED]" in tool_messages[0]["content"]
    assert "notify_manager" in tools_called


def test_emergency_triage_result_is_valid_pydantic():
    result = _emergency_triage_result("input di test")
    assert isinstance(result, TriageResult)
    assert result.categoria == "GENERAL"
    assert result.priorita == "CRITICAL"
    assert result.azione_eseguita == "Emergency Fallback attivato"
    assert "FALLBACK" in result.riassunto_breve


@patch("logic.get_client")
def test_self_correction_repairs_invalid_json(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    invalid = '{"categoria":"IT"}'
    valid = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"ok retry",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.side_effect = [
        _completion(content=invalid),
        _completion(content=valid),
    ]

    result, stats = triage_message("help", manuale="", return_stats=True)

    assert result.categoria == "IT"
    assert stats.used_self_correction is True
    assert stats.used_emergency_fallback is False
    assert stats.attempts == 2
    assert mock_client.chat.completions.create.call_count == 2


@patch("logic.get_client")
def test_emergency_fallback_after_max_retries(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    invalid = '{"categoria":"IT"}'
    mock_client.chat.completions.create.side_effect = [
        _completion(content=invalid),
        _completion(content=invalid),
        _completion(content=invalid),
    ]

    result, stats = triage_message("help", manuale="", return_stats=True)

    assert result.categoria == "GENERAL"
    assert "Fallback" in (result.azione_eseguita or "")
    assert stats.used_emergency_fallback is True
    assert stats.attempts == MAX_TRIAGE_JSON_RETRIES
    assert mock_client.chat.completions.create.call_count == MAX_TRIAGE_JSON_RETRIES


@patch("logic.get_client")
def test_max_json_retries_bounds_api_calls(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    invalid = '{"categoria":"IT"}'
    mock_client.chat.completions.create.side_effect = [
        _completion(content=invalid),
        _completion(content=invalid),
        _completion(content=invalid),
    ]

    triage_message("x", manuale="", return_stats=True)

    assert mock_client.chat.completions.create.call_count == MAX_TRIAGE_JSON_RETRIES


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
def test_react_triage_return_metrics(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    final = (
        '{"analisi_problema":"1. P. 2. C. 3. IT. 4. LOW.",'
        '"categoria":"IT","priorita":"LOW","riassunto_breve":"test ok",'
        '"messaggio_originale":"help"}'
    )
    mock_client.chat.completions.create.return_value = _completion(content=final)

    outcome = react_triage("help", manuale="Manuale IT", return_metrics=True)
    assert isinstance(outcome, tuple)
    result, metrics = outcome
    assert result.categoria == "IT"
    assert isinstance(metrics, ReactRunMetrics)
    assert metrics.tokens_est > 0


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


def test_react_pruning_reduces_conversation_tokens():
    from orchestration.message_pruning import estimate_conversation_tokens, prune_conversation

    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "ticket"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
        {"role": "tool", "name": "search_policy", "content": "x" * 800},
        {"role": "tool", "name": "search_policy", "content": "y" * 100},
    ]
    before = estimate_conversation_tokens(messages)
    pruned, saved = prune_conversation(messages, keep_last_tool_results=1)
    after = estimate_conversation_tokens(pruned)
    assert saved > 0
    assert after < before
