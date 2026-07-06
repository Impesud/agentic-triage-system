"""Test security_alerts SQLite — Lezione 18."""

from orchestration.security_store import init_security_tables, list_recent_alerts, log_security_alert


def test_log_and_list_security_alerts(tmp_path):
    db = tmp_path / "alerts.db"
    init_security_tables(str(db))
    alert_id = log_security_alert(
        alert_type="INPUT_INJECTION",
        severity="CRITICAL",
        blocked_stage="pre_pipeline",
        input_excerpt="test excerpt",
        matched_pattern="ignora",
        payload={"vectors": ["policy_override"]},
        db_path=str(db),
    )
    assert alert_id == 1
    alerts = list_recent_alerts(limit=5, db_path=str(db))
    assert len(alerts) == 1
    assert alerts[0].alert_type == "INPUT_INJECTION"
