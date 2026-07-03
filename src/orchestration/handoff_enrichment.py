"""Arricchimento SharedHandoffContext da cache runtime (Lezione 17)."""

from __future__ import annotations

from orchestration.models import SharedHandoffContext
from orchestration.pipeline_cache import PipelineContextCache


def enrich_handoff_from_cache(
    handoff: SharedHandoffContext,
    cache: PipelineContextCache,
) -> SharedHandoffContext:
    """
    Propaga excerpt policy e digest LTM già recuperati nella pipeline
    così il Resolver può evitare tool ridondanti.
    """
    policy_excerpt = cache.first_policy_excerpt()
    ltm_digest = cache.first_ltm_digest()
    if policy_excerpt is None and ltm_digest is None:
        return handoff

    updates: dict[str, str] = {}
    if policy_excerpt is not None:
        updates["policy_excerpt"] = policy_excerpt
    if ltm_digest is not None:
        updates["ltm_digest"] = ltm_digest
    return handoff.model_copy(update=updates)
