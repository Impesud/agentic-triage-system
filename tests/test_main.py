from main import (
    DEMO_SCENARIOS,
    LTM_MARCO_TICKET,
    SMOKE_IT_TICKET,
    STM_TURN1,
    STM_TURN2,
)


def test_demo_scenarios_lesson9():
    assert len(DEMO_SCENARIOS) == 3
    ids = [s.id for s in DEMO_SCENARIOS]
    assert ids == ["M3", "M1", "M2"]
    m1 = next(s for s in DEMO_SCENARIOS if s.id == "M1")
    assert len(m1.messages) == 2
    assert m1.messages == (STM_TURN1, STM_TURN2)
    m2 = next(s for s in DEMO_SCENARIOS if s.id == "M2")
    assert m2.messages == (LTM_MARCO_TICKET,)
    m3 = next(s for s in DEMO_SCENARIOS if s.id == "M3")
    assert m3.messages == (SMOKE_IT_TICKET,)


def test_stm_turns_distinct():
    assert STM_TURN1 != STM_TURN2
    assert "server-X" in STM_TURN2


def test_ltm_text_differs_from_few_shot_prod02():
    """Testo demo M2 distinto dal few-shot (prod-02) in triage_v1."""
    assert "db-primary" in LTM_MARCO_TICKET
    assert "prod-02" not in LTM_MARCO_TICKET


def test_seed_marco_reset(tmp_path):
    from main import seed_marco_angry_history

    log_file = tmp_path / "demo.jsonl"
    seed_marco_angry_history(4, log_file, reset=True)
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    seed_marco_angry_history(4, log_file, reset=True)
    lines2 = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines2) == 4
