"""
Nucleo del loop agentico (logic.py) — Lezione 9: memoria; Lezione 10: tool search_policy con RAG.
"""

import json
import re
from typing import Any

from client import MODEL, get_client
from memory.extractors import detect_sentiment_label, extract_cliente_nome
from parsing.parser import parse_llm_output
from prompts.triage_v1 import build_chat_messages
from schemas.ticket import TriageResult
from tools.history_tools import should_escalate_repeat_customer
from tools.registry import TOOL_MAP, TOOLS_DEFINITION

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


def _run_agent_loop(
    messages: list[dict[str, Any]],
    user_input: str,
    context_text: str,
) -> str:
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
        return _request_final_json(client, conversation)

    fallback_ran = _apply_all_fallbacks(
        context_text,
        conversation,
        tools_called,
        first_assistant=response_message,
    )
    if fallback_ran:
        return _request_final_json(client, conversation)

    content = response_message.content
    if not content:
        raise ValueError("Risposta vuota dal modello")
    if not _looks_like_json(content):
        raise ClarificationNeeded(content.strip())
    return content.strip()


def triage_message(
    user_input: str,
    manuale: str,
    history: list[dict[str, str]] | None = None,
) -> TriageResult:
    context_text = _build_context_text(user_input, history)
    messages = build_chat_messages(user_input, manuale, history=history)
    raw_output = _run_agent_loop(messages, user_input, context_text)
    return parse_llm_output(raw_output)
