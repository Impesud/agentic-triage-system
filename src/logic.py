"""
Nucleo del loop agentico (logic.py) — Lezione 9: memoria; Lezione 10: RAG;
Lezione 11: self-correction su soft error e emergency fallback;
Lezione 13: loop ReAct multi-step; Lezione 14: max_steps, STM, self-correction in-loop;
Lezione 16: orchestrazione multi-agent (CrewAI / AutoGen).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from client import MODEL, get_client
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from parsing.parser import parse_llm_output
from prompts.triage_v1 import build_chat_messages
from schemas.ticket import TriageResult
from tools.history_tools import should_escalate_repeat_customer
from tools.logger import log_event
from tools.logger import log_event
from tools.registry import TOOL_MAP, TOOLS_DEFINITION

MAX_TRIAGE_JSON_RETRIES = 3
DEFAULT_REACT_MAX_STEPS = 4

# Cache Short-Term Memory per sessioni ReAct multi-turno (Lezione 14)
_SHORT_TERM_STORE: dict[str, list[Any]] = {}

_REACT_PROMPT_SUFFIX = """
Operi rigorosamente all'interno di un ciclo ReAct strutturato: Thought -> Action -> Observation.
Per ogni iterazione:
1. Produci un pensiero (Thought) spiegando quale dato ti manca o quale tool serve.
2. Decidi se invocare uno strumento (Action) o concludere con il JSON finale.

Quando hai raccolto tutti gli elementi utili dalle Observation precedenti, interrompi l'uso dei tool
e genera IMMEDIATAMENTE il payload JSON finale conforme allo schema richiesto. Nessun markdown.
"""

_VIP_BUDGET_THRESHOLD = 10_000
_BUDGET_PATTERN = re.compile(
    r"(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:€|euro)",
    re.IGNORECASE,
)

_ANGRY_LEGAL_TERMS = (
    "avvocato",
    "denuncio",
    "querela",
    "tribunale",
    "azione legale",
    "legali",
)


@dataclass(frozen=True)
class TriageStats:
    """Metriche del ciclo di validazione JSON (Lezione 11 / benchmark L12)."""

    attempts: int = 0
    used_self_correction: bool = False
    used_emergency_fallback: bool = False


class ClarificationNeeded(Exception):
    """L'LLM ha richiesto un chiarimento prima del triage finale."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _parse_budget_amount(raw: str) -> int:
    return int(raw.replace(".", "").replace(",", ""))


def _extract_max_budget_eur(text: str) -> int | None:
    amounts = [_parse_budget_amount(m.group(1)) for m in _BUDGET_PATTERN.finditer(text)]
    return max(amounts) if amounts else None


def _requires_vip_escalation(text: str) -> bool:
    max_budget = _extract_max_budget_eur(text)
    return max_budget is not None and max_budget > _VIP_BUDGET_THRESHOLD


def _detects_angry_sentiment(text: str) -> bool:
    """Sentiment ARRABBIATO: euristica policy (legale/finanziario) o label extractor."""
    if detect_sentiment_label(text) == "ARRABBIATO":
        return True
    lower = text.lower()
    legal = any(term in lower for term in _ANGRY_LEGAL_TERMS)
    financial = any(term in lower for term in ("perso", "perdita", "perdite", "fatturato", "danni"))
    financial = financial and bool(re.search(r"\d", text))
    return legal and financial


def _policy_fallback_needed(user_input: str, tools_called: set[str]) -> bool:
    if "notify_manager" in tools_called:
        return False
    return _requires_vip_escalation(user_input) or _detects_angry_sentiment(user_input)


def _build_context_text(user_input: str, history: list[dict[str, str]] | None) -> str:
    parts: list[str] = []
    if history:
        parts.extend(m["content"] for m in history if m.get("role") == "user")
    parts.append(user_input)
    return "\n".join(parts)


def _long_term_fallback_needed(context_text: str, tools_called: set[str]) -> bool:
    if "notify_manager" in tools_called:
        return False
    cliente = extract_cliente_nome(context_text)
    if not cliente:
        return False
    return should_escalate_repeat_customer(cliente, hours=24)


def _looks_like_json(content: str) -> bool:
    return content.strip().startswith("{")


def _call_llm_with_tools(client: Any, messages: list[dict[str, Any]]) -> Any:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=messages,
        tools=TOOLS_DEFINITION,
        tool_choice="auto",
    )
    return response.choices[0].message


def _execute_tool_calls(conversation: list[Any], tool_calls: Any) -> set[str]:
    tools_called: set[str] = set()
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        tools_called.add(function_name)
        function_args = json.loads(tool_call.function.arguments)
        if function_name == "search_long_term_history" and "hours" not in function_args:
            function_args.setdefault("hours", 24)
        tool_output = TOOL_MAP[function_name](**function_args)
        conversation.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": tool_output,
            }
        )
    return tools_called


def _append_fallback_tools(
    conversation: list[Any],
    tools_called: set[str],
    pending: list[tuple[str, dict[str, Any], str]],
    *,
    first_assistant: Any | None = None,
) -> bool:
    if not pending:
        return False

    if first_assistant is not None:
        conversation.append(first_assistant)

    conversation.append(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
                for name, args, tool_id in pending
            ],
        }
    )

    for name, args, tool_id in pending:
        tools_called.add(name)
        tool_output = TOOL_MAP[name](**args)
        conversation.append(
            {
                "role": "tool",
                "tool_call_id": tool_id,
                "name": name,
                "content": tool_output,
            }
        )
    return True


def _apply_policy_fallback(
    context_text: str,
    conversation: list[Any],
    tools_called: set[str],
    *,
    first_assistant: Any | None = None,
) -> bool:
    if not _policy_fallback_needed(context_text, tools_called):
        return False

    needs_vip = _requires_vip_escalation(context_text)
    needs_angry = _detects_angry_sentiment(context_text)
    pending: list[tuple[str, dict[str, Any], str]] = []

    if needs_angry and "search_policy" not in tools_called:
        pending.append(
            (
                "search_policy",
                {"query": "sentiment ARRABBIATO escalation critica"},
                "fallback-sp-1",
            )
        )

    if "notify_manager" not in tools_called:
        if needs_vip:
            budget = _extract_max_budget_eur(context_text)
            message = (
                f"Escalation VIP automatica: budget {budget}€ (>10.000€). "
                f"Sintesi: {context_text[:250]}"
            )
            reason = "Escalation VIP applicata da policy (fallback deterministico)."
        else:
            message = (
                f"Escalation sentiment ARRABBIATO (policy §3.1). "
                f"Sintesi: {context_text[:250]}"
            )
            reason = "Escalation sentiment ARRABBIATO applicata da policy (fallback deterministico)."
        pending.append(
            ("notify_manager", {"message": message, "priority": 4}, "fallback-nm-1")
        )

    if not pending:
        return False

    _append_fallback_tools(conversation, tools_called, pending, first_assistant=first_assistant)
    print(f"[AGENTE] {reason}", flush=True)
    return True


def _apply_long_term_fallback(
    context_text: str,
    conversation: list[Any],
    tools_called: set[str],
    *,
    first_assistant: Any | None = None,
) -> bool:
    cliente = extract_cliente_nome(context_text)
    if not cliente:
        return False

    pending: list[tuple[str, dict[str, Any], str]] = []

    if "search_long_term_history" not in tools_called:
        pending.append(
            (
                "search_long_term_history",
                {"cliente_nome": cliente, "hours": 24},
                "fallback-ltm-1",
            )
        )

    if _long_term_fallback_needed(context_text, tools_called) and "notify_manager" not in tools_called:
        pending.append(
            (
                "notify_manager",
                {
                    "message": (
                        f"Escalation storico cliente {cliente}: >=4 ticket IT ARRABBIATO "
                        f"in 24h. Sintesi: {context_text[:250]}"
                    ),
                    "priority": 4,
                },
                "fallback-ltm-nm-1",
            )
        )

    if not pending:
        return False

    ran = _append_fallback_tools(
        conversation, tools_called, pending, first_assistant=first_assistant
    )
    if ran:
        print(
            f"[AGENTE] Fallback long-term memory per cliente '{cliente}'.",
            flush=True,
        )
    return ran


def _apply_all_fallbacks(
    context_text: str,
    conversation: list[Any],
    tools_called: set[str],
    *,
    first_assistant: Any | None = None,
) -> bool:
    ran_policy = _apply_policy_fallback(
        context_text, conversation, tools_called, first_assistant=first_assistant
    )
    first_assistant = None
    ran_ltm = _apply_long_term_fallback(
        context_text, conversation, tools_called, first_assistant=first_assistant
    )
    return ran_policy or ran_ltm


def _request_final_json(client: Any, conversation: list[Any]) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=conversation,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Risposta vuota dal modello")
    return content.strip()


def _emergency_triage_result(user_input: str) -> TriageResult:
    """Fallback deterministico dopo esaurimento tentativi di self-correction."""
    return TriageResult(
        analisi_problema=(
            "1. Problema: non classificabile automaticamente. "
            "2. Contesto: emergency fallback strutturale. "
            "3. Categoria: GENERAL. 4. Priorità: CRITICAL."
        ),
        categoria="GENERAL",
        priorita="CRITICAL",
        riassunto_breve="FALLBACK emergenza validazione agente",
        messaggio_originale=user_input,
        azione_eseguita="Emergency Fallback attivato",
    )


def _self_correction_user_message(error: ValueError) -> str:
    return (
        f"Il tuo JSON precedente ha generato un errore di validazione: {error}. "
        "Correggilo e restituisci unicamente il JSON conforme allo schema richiesto."
    )


def _finalize_with_self_correction(
    client: Any,
    conversation: list[Any],
    user_input: str,
    initial_raw: str | None,
    *,
    max_retries: int = MAX_TRIAGE_JSON_RETRIES,
) -> tuple[TriageResult, TriageStats]:
    """
    Valida l'output JSON con retry in-context (soft error).
    Dopo max_retries tentativi attiva emergency fallback (hard stop cognitivo).
    """
    stats = TriageStats()
    raw_content: str | None = initial_raw

    for attempt in range(1, max_retries + 1):
        if raw_content is None:
            raw_content = _request_final_json(client, conversation)

        stats = TriageStats(
            attempts=attempt,
            used_self_correction=stats.used_self_correction,
            used_emergency_fallback=False,
        )

        try:
            return parse_llm_output(raw_content), stats
        except ValueError as exc:
            print(
                f"   ⚠️ Tentativo {attempt}/{max_retries} fallito. "
                f"Errore di validazione: {exc}",
                flush=True,
            )
            log_event(
                "triage_json_retry",
                {
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "error": str(exc)[:500],
                    "input_preview": user_input[:200],
                },
            )

            if attempt == max_retries:
                print(
                    "   🚨 Max retries raggiunti. Attivazione Fallback di sicurezza strutturale.",
                    flush=True,
                )
                fallback = _emergency_triage_result(user_input)
                log_event(
                    "emergency_fallback",
                    {
                        "attempts": attempt,
                        "input_preview": user_input[:200],
                        "categoria": fallback.categoria,
                        "priorita": fallback.priorita,
                    },
                )
                return fallback, TriageStats(
                    attempts=attempt,
                    used_self_correction=stats.used_self_correction,
                    used_emergency_fallback=True,
                )

            conversation.append({"role": "assistant", "content": raw_content})
            conversation.append(
                {"role": "user", "content": _self_correction_user_message(exc)}
            )
            raw_content = None
            stats = TriageStats(
                attempts=attempt,
                used_self_correction=True,
                used_emergency_fallback=False,
            )

    raise RuntimeError("self-correction loop terminato senza risultato")


def _run_agent_loop(
    messages: list[dict[str, Any]],
    user_input: str,
    context_text: str,
) -> tuple[Any, list[Any], str | None]:
    """
    Esegue tool e fallback policy/LTM.
    Ritorna (client, conversation, initial_raw):
    - initial_raw valorizzato se la prima risposta è già JSON (senza tool)
    - None se serve _request_final_json nella fase di finalize
    """
    client = get_client()
    response_message = _call_llm_with_tools(client, messages)
    tool_calls = response_message.tool_calls
    tools_called: set[str] = set()
    conversation: list[Any] = list(messages)

    if tool_calls:
        print("\n[AGENTE] Attivazione tool in corso...")
        conversation.append(response_message)
        tools_called = _execute_tool_calls(conversation, tool_calls)
        _apply_all_fallbacks(context_text, conversation, tools_called)
        return client, conversation, None

    fallback_ran = _apply_all_fallbacks(
        context_text,
        conversation,
        tools_called,
        first_assistant=response_message,
    )
    if fallback_ran:
        return client, conversation, None

    content = response_message.content
    if not content:
        raise ValueError("Risposta vuota dal modello")
    if not _looks_like_json(content):
        raise ClarificationNeeded(content.strip())
    return client, conversation, content.strip()


def triage_message(
    user_input: str,
    manuale: str,
    history: list[dict[str, str]] | None = None,
    *,
    return_stats: bool = False,
    max_json_retries: int = MAX_TRIAGE_JSON_RETRIES,
) -> TriageResult | tuple[TriageResult, TriageStats]:
    context_text = _build_context_text(user_input, history)
    messages = build_chat_messages(user_input, manuale, history=history)
    client, conversation, initial_raw = _run_agent_loop(messages, user_input, context_text)
    result, stats = _finalize_with_self_correction(
        client,
        conversation,
        user_input,
        initial_raw,
        max_retries=max_json_retries,
    )
    if return_stats:
        return result, stats
    return result


def _build_react_messages(
    user_input: str,
    manuale: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    messages = build_chat_messages(user_input, manuale, history=history)
    system = messages[0]["content"] + "\n\n" + _REACT_PROMPT_SUFFIX.strip()
    messages[0] = {"role": "system", "content": system}
    return messages


def react_triage(
    user_input: str,
    manuale: str,
    *,
    history: list[dict[str, str]] | None = None,
    session_id: str | None = None,
    max_steps: int = DEFAULT_REACT_MAX_STEPS,
    max_json_retries: int = MAX_TRIAGE_JSON_RETRIES,
) -> TriageResult:
    """
    Motore di Triage Agentico ReAct Multi-Step (Lezioni 13–14).
    Esegue cicli iterativi Thought -> Action -> Observation fino a convergenza JSON.
    Con session_id riusa la conversazione in _SHORT_TERM_STORE (Short-Term Memory).
    """
    client = get_client()

    if session_id and session_id in _SHORT_TERM_STORE:
        conversation = _SHORT_TERM_STORE[session_id]
        conversation.append({"role": "user", "content": user_input})
    elif session_id:
        conversation = _build_react_messages(user_input, manuale, history=history)
        _SHORT_TERM_STORE[session_id] = conversation
    else:
        conversation = _build_react_messages(user_input, manuale, history=history)

    print(
        f"\n🎬 [ReAct Engine] Avvio pianificazione per ticket: '{user_input[:40]}...'",
        flush=True,
    )

    for step in range(1, max_steps + 1):
        print(f"🔄 [STEP {step}/{max_steps}] Riflessione cognitiva dell'agente...", flush=True)

        response_message = _call_llm_with_tools(client, conversation)
        tool_calls = response_message.tool_calls
        conversation.append(response_message)

        if tool_calls:
            print("\n[AGENTE] Attivazione tool in corso (ReAct Action)...", flush=True)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                if function_name == "search_long_term_history" and "hours" not in function_args:
                    function_args.setdefault("hours", 24)
                print(
                    f"   🛠️ [ACTION] Invocazione tool '{function_name}' con: {function_args}",
                    flush=True,
                )
                tool_output = TOOL_MAP[function_name](**function_args)
                preview = tool_output[:50] + ("..." if len(tool_output) > 50 else "")
                print(f"   📥 [OBSERVATION] Risultato: {preview}", flush=True)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": tool_output,
                    }
                )
            continue

        content = response_message.content
        if not content:
            raise ValueError("Risposta vuota dal modello nel ciclo ReAct")

        if not _looks_like_json(content):
            raise ClarificationNeeded(content.strip())

        print(
            f"🏁 [ReAct Engine] Convergenza raggiunta al ciclo {step}. Validazione strutturale...",
            flush=True,
        )
        try:
            result = parse_llm_output(content.strip())
            if session_id:
                _SHORT_TERM_STORE[session_id] = conversation
            return result
        except ValueError as parsing_err:
            print(
                f"   ⚠️ [Self-Correction] Formato non valido. "
                f"Tentativo di riallineamento in-context: {parsing_err}",
                flush=True,
            )
            conversation.append(
                {
                    "role": "user",
                    "content": (
                        f"Il tuo JSON finale ha violato lo schema. Errore riscontrato da Pydantic: "
                        f"{parsing_err}. Rigenera la struttura correggendo il campo."
                    ),
                }
            )
            if session_id:
                _SHORT_TERM_STORE[session_id] = conversation
            continue

    print(
        "🚨 [CRITICO] Il ciclo di Planning ReAct ha esaurito max_steps. "
        "Attivazione Fallback di emergenza.",
        flush=True,
    )
    log_event(
        "react_max_steps_fallback",
        {
            "max_steps": max_steps,
            "session_id": session_id,
            "input_preview": user_input[:200],
        },
    )
    fallback = TriageResult(
        analisi_problema=_emergency_triage_result(user_input).analisi_problema,
        categoria="GENERAL",
        priorita="CRITICAL",
        riassunto_breve=(
            "FALLBACK: L'agente ha superato i max_steps di pianificazione ReAct "
            "o ha corrotto la struttura."
        ),
        messaggio_originale=user_input,
        azione_eseguita="Fallback per interruzione ciclo ReAct",
    )
    if session_id:
        _SHORT_TERM_STORE[session_id] = conversation
    return fallback


_MULTIAGENT_INSTALL_HINT = 'pip install -e ".[multiagent]"'


def multi_agent_triage(
    user_input: str,
    manuale: str,
    *,
    orchestrator: Literal["crewai", "autogen"] = "crewai",
) -> TriageResult:
    """
    Facade orchestrazione multi-agent (Lezione 16).
    CrewAI = pipeline sequenziale; AutoGen = GroupChat collaborativo.
    """
    try:
        if orchestrator == "crewai":
            from orchestration.crew_pipeline import crew_triage

            return crew_triage(user_input, manuale)
        if orchestrator == "autogen":
            from orchestration.autogen_team import autogen_triage

            return autogen_triage(user_input, manuale)
    except ImportError as exc:
        raise ImportError(
            f"Dipendenze multi-agent mancanti. Esegui: {_MULTIAGENT_INSTALL_HINT}"
        ) from exc

    raise ValueError(f"Orchestratore sconosciuto: {orchestrator!r}")
