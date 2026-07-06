"""Message Pruning per catene multi-agente e loop ReAct (Lezione 17)."""

from __future__ import annotations

from typing import Any

from tools.logger import log_event

_PROTECTED_ROLES = frozenset({"system", "user"})


def _message_field(message: Any, key: str, default: Any = None) -> Any:
    """Legge un campo da messaggio dict o oggetto SDK OpenAI (es. ChatCompletionMessage)."""
    if isinstance(message, dict):
        return message.get(key, default)
    return getattr(message, key, default)


def estimate_tokens(text: str) -> int:
    """Stima token: tiktoken se installato, altrimenti len//4."""
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(0, len(text) // 4)


def estimate_conversation_tokens(messages: list[Any]) -> int:
    """Somma stime token su role/content dei messaggi OpenAI-style (dict o SDK)."""
    total = 0
    for message in messages:
        content = _message_field(message, "content")
        if isinstance(content, str):
            total += estimate_tokens(content)
        tool_calls = _message_field(message, "tool_calls")
        if tool_calls:
            total += estimate_tokens(str(tool_calls))
    return total


def compact_tool_observation(name: str, content: str, *, max_chars: int = 200) -> str:
    """Compatta un'observation tool mantenendo nome, preview e hint [PRUNED]."""
    preview = content[:max_chars].replace("\n", " ")
    if len(content) > max_chars:
        omitted = len(content) - max_chars
        return (
            f"[PRUNED] {name}: {preview}... "
            f"({omitted} chars omitted, {len(content)} total)"
        )
    return content


def compact_tool_output(content: str, *, max_chars: int = 400) -> str:
    """Tronca l'output grezzo di un tool prima che entri nella history (Livello B)."""
    if len(content) <= max_chars:
        return content
    preview = content[:max_chars].replace("\n", " ")
    omitted = len(content) - max_chars
    return f"{preview}... [COMPACT] ({omitted} chars omitted)"


def prune_conversation(
    messages: list[Any],
    *,
    keep_last_tool_results: int = 1,
    always_keep_roles: frozenset[str] = _PROTECTED_ROLES,
    max_chars_per_pruned: int = 200,
) -> tuple[list[Any], int]:
    """
    Potatura observation tool obsolete nella cronologia.

    Ritorna (messages_pruned, bytes_saved) rispetto alla serializzazione content.
    """
    if keep_last_tool_results < 0:
        raise ValueError("keep_last_tool_results deve essere >= 0")

    tool_seen: dict[str, int] = {}
    pruned: list[Any] = []
    bytes_saved = 0

    for message in reversed(messages):
        role = _message_field(message, "role")
        if role in always_keep_roles:
            pruned.append(message)
            continue

        if role == "tool":
            if not isinstance(message, dict):
                pruned.append(message)
                continue
            name = str(_message_field(message, "name", "unknown_tool"))
            content = _message_field(message, "content")
            if not isinstance(content, str):
                pruned.append(message)
                continue

            count = tool_seen.get(name, 0)
            tool_seen[name] = count + 1

            if count < keep_last_tool_results:
                pruned.append(message)
            else:
                compact = compact_tool_observation(
                    name, content, max_chars=max_chars_per_pruned
                )
                bytes_saved += max(0, len(content) - len(compact))
                pruned.append({**message, "content": compact})
            continue

        pruned.append(message)

    pruned.reverse()
    return pruned, bytes_saved


def apply_pruning_with_log(
    messages: list[Any],
    *,
    step: int | None = None,
    keep_last_tool_results: int = 1,
) -> list[Any]:
    """Applica prune_conversation e registra message_pruning_applied se utile."""
    before_tokens = estimate_conversation_tokens(messages)
    pruned, bytes_saved = prune_conversation(
        messages,
        keep_last_tool_results=keep_last_tool_results,
    )
    after_tokens = estimate_conversation_tokens(pruned)
    if bytes_saved > 0:
        log_event(
            "message_pruning_applied",
            {
                "bytes_saved": bytes_saved,
                "tokens_before_est": before_tokens,
                "tokens_after_est": after_tokens,
                "step": step,
                "messages_before": len(messages),
                "messages_after": len(pruned),
            },
        )
    return pruned
