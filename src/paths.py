"""Percorsi assoluti rispetto alla root del repository."""

from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SRC_DIR.parent

MANUALE_IT_PATH = REPO_ROOT / "data" / "manuale_it.txt"
TICKETS_PATH = REPO_ROOT / "data" / "tickets.jsonl"
LOG_FILE_PATH = REPO_ROOT / "logs" / "activity.jsonl"
ENV_PATH = REPO_ROOT / ".env"
