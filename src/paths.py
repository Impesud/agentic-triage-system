"""Percorsi assoluti rispetto alla root del repository."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

MANUALE_IT_PATH = REPO_ROOT / "data" / "manuale_it.txt"
POLICY_PATH = REPO_ROOT / "data" / "policy.txt"
CHROMA_PATH = REPO_ROOT / "data" / "chroma"
TRIAGE_DB_PATH = REPO_ROOT / "data" / "triage_system.db"
LOG_FILE_PATH = REPO_ROOT / "logs" / "activity.jsonl"
REPORTS_DIR = REPO_ROOT / "logs" / "reports"
ENV_PATH = REPO_ROOT / ".env"
