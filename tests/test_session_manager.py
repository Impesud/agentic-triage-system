from memory.session_manager import SessionManager


def test_append_and_get_messages():
    sm = SessionManager()
    sm.append(1, "user", "ciao")
    sm.append(1, "assistant", "risposta")
    msgs = sm.get_messages(1)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "risposta"


def test_isolation_between_tickets():
    sm = SessionManager()
    sm.append(1, "user", "a")
    sm.append(2, "user", "b")
    assert len(sm.get_messages(1)) == 1
    assert sm.get_messages(2)[0]["content"] == "b"


def test_clear():
    sm = SessionManager()
    sm.append(3, "user", "x")
    sm.clear(3)
    assert sm.get_messages(3) == []
