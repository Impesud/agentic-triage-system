from tools.router import assign_to_team


def test_assign_to_team_it(triaged_ticket):
    routed = assign_to_team(triaged_ticket(categoria="IT"))
    assert routed.team == "team_tecnico"


def test_assign_to_team_billing(triaged_ticket):
    routed = assign_to_team(triaged_ticket(categoria="BILLING", priorita="MEDIUM"))
    assert routed.team == "amministrazione"


def test_assign_to_team_sales(triaged_ticket):
    routed = assign_to_team(triaged_ticket(categoria="SALES", priorita="LOW"))
    assert routed.team == "commerciale"


def test_assign_to_team_security(triaged_ticket):
    routed = assign_to_team(triaged_ticket(categoria="SECURITY", priorita="LOW"))
    assert routed.team == "sicurezza"
