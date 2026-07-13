from main import L16_TICKET, WEEK12_SCENARIOS, seed_marco_angry_history


def test_cli_scenarios_week12_only():
    assert WEEK12_SCENARIOS == (
        "l15", "l16a", "l16b", "l17a", "l17b", "l18a", "l18b", "l19a", "l19b", "all"
    )


def test_l16_ticket_contains_marco():
    assert "Marco Rossi" in L16_TICKET
    assert "15.000" in L16_TICKET


def test_seed_marco_reset(tmp_path):
    log_file = tmp_path / "demo.jsonl"
    seed_marco_angry_history(4, log_file, reset=True)
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    seed_marco_angry_history(4, log_file, reset=True)
    lines2 = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines2) == 4
