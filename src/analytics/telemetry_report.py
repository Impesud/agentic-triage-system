"""Report aggregati telemetria L20 da SQLite tickets."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from paths import TRIAGE_DB_PATH


def query_cost_by_categoria(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Costo medio e latenza per categoria (query didattica L20)."""
    path = db_path or TRIAGE_DB_PATH
    if not path.exists():
        return []
    with sqlite3.connect(str(path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT categoria,
                   ROUND(AVG(cost_usd_milli) / 1000.0, 4) AS avg_cost_usd,
                   ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
                   COUNT(*) AS n
            FROM tickets
            WHERE cost_usd_milli IS NOT NULL
            GROUP BY categoria
            ORDER BY categoria
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def format_telemetry_report(rows: list[dict[str, Any]]) -> str:
    lines = [
        "=== TELEMETRIA SQLite (tickets L20) ===",
        "Costo medio per categoria (USD da cost_usd_milli / 1000):",
        "",
    ]
    if not rows:
        lines.append("  (nessun ticket con cost_usd_milli valorizzato)")
    else:
        lines.append(f"{'Categoria':<12} {'Avg USD':>10} {'Avg ms':>10} {'N':>6}")
        lines.append("-" * 42)
        for row in rows:
            lines.append(
                f"{row['categoria']:<12} "
                f"{row['avg_cost_usd']:>10.4f} "
                f"{row['avg_latency_ms']:>10.1f} "
                f"{row['n']:>6}"
            )
    lines.append("========================================")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report telemetria L20 da SQLite")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Percorso triage_system.db (default: data/triage_system.db)",
    )
    args = parser.parse_args()
    rows = query_cost_by_categoria(args.db)
    print(format_telemetry_report(rows))


if __name__ == "__main__":
    main()
