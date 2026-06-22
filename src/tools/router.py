from schemas.ticket import Category, Ticket

TEAM_BY_CATEGORY: dict[Category, str] = {
    "IT": "team_tecnico",
    "BILLING": "amministrazione",
    "SALES": "commerciale",
    "SECURITY": "sicurezza",
    "GENERAL": "GeneralQueue",
}


def team_for_category(categoria: Category) -> str:
    """Restituisce il team di routing per una categoria triage."""
    return TEAM_BY_CATEGORY[categoria]


def assign_to_team(ticket: Ticket) -> Ticket:
    """Assegna il ticket al team in base alla categoria."""
    if ticket.categoria is None:
        raise ValueError("Impossibile eseguire il routing senza categoria")

    team = TEAM_BY_CATEGORY[ticket.categoria]
    return ticket.model_copy(update={"team": team})
