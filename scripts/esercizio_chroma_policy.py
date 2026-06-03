"""
Esercizio Lezione 10B — ChromaDB + policy Impesud.

Esecuzione dalla root del repo:
  source .venv/bin/activate
  pip install -e .
  PYTHONPATH=src python scripts/esercizio_chroma_policy.py
"""

from __future__ import annotations

from paths import POLICY_PATH
from rag.policy_semantic import (
    DEFAULT_THRESHOLD,
    format_semantic_result,
    semantic_policy_search,
)

DEMO_QUERY = (
    "Voglio annullare il contratto e riavere i soldi: quali sono i termini?"
)


def main() -> None:
    if not POLICY_PATH.exists():
        raise FileNotFoundError(f"Policy non trovata: {POLICY_PATH}")

    print(f"Query: {DEMO_QUERY}\n")
    result = semantic_policy_search(DEMO_QUERY, POLICY_PATH)

    if result is None:
        print(f"[INFO] Nessun chunk sopra soglia {DEFAULT_THRESHOLD}")
        return

    print(format_semantic_result(result))
    print(f"\n[OK] score={result.score:.3f} (soglia {DEFAULT_THRESHOLD})")
    print("Riesegui senza modificare policy.txt: Chroma non re-indicizza (persistenza).")


if __name__ == "__main__":
    main()
