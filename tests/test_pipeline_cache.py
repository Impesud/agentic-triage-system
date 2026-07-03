"""Test PipelineContextCache — Lezione 17."""

from orchestration.handoff_enrichment import enrich_handoff_from_cache
from orchestration.models import CommunicationTopology, SharedHandoffContext
from orchestration.pipeline_cache import PipelineContextCache


def test_policy_cache_second_call_is_hit():
    cache = PipelineContextCache()
    calls: list[str] = []

    def fn(q: str) -> str:
        calls.append(q)
        return f"policy:{q}"

    assert cache.get_or_call_policy("Budget VIP", fn) == "policy:Budget VIP"
    assert cache.get_or_call_policy("budget vip", fn) == "policy:Budget VIP"
    assert len(calls) == 1
    assert cache.policy_hits == 1


def test_ltm_cache_per_cliente_hours():
    cache = PipelineContextCache()
    calls: list[tuple[str, int]] = []

    def fn(cliente: str, hours: int) -> str:
        calls.append((cliente, hours))
        return f"ltm:{cliente}:{hours}"

    cache.get_or_call_ltm("Marco", 24, fn)
    cache.get_or_call_ltm("Marco", 24, fn)
    assert len(calls) == 1
    assert cache.ltm_hits == 1


def test_enriched_handoff_skips_redundant_fields():
    handoff = SharedHandoffContext(
        ticket_message="ticket",
        topology=CommunicationTopology.SEQUENTIAL,
    )
    cache = PipelineContextCache()
    cache.policy_by_query["budget"] = "[RAG] sconto 5%"
    cache.ltm_by_cliente["marco|24"] = "2 ticket precedenti"

    enriched = enrich_handoff_from_cache(handoff, cache)
    assert enriched.policy_excerpt is not None
    assert enriched.ltm_digest is not None


def test_handoff_enriched_after_cache_populated():
    from orchestration.models import CommunicationTopology, SharedHandoffContext

    handoff = SharedHandoffContext(
        ticket_message="ticket",
        topology=CommunicationTopology.SEQUENTIAL,
    )
    cache = PipelineContextCache()
    cache.policy_by_query["budget"] = "[RAG] policy chunk"
    cache.ltm_by_cliente["marco|24"] = "storico 2 ticket"

    enriched = enrich_handoff_from_cache(handoff, cache)
    assert "policy chunk" in (enriched.policy_excerpt or "")
    assert enriched.ltm_digest is not None
