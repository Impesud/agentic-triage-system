"""
Tool di sicurezza SOC — Progetto 2.

Espone isolate_account e verify_sender_identity per gli scenari
phishing, anomalie login, smarrimento dispositivo e whaling CEO.
"""

from __future__ import annotations

from tools.logger import (
    account_to_email,
    isolate_account_sql,
    log_event,
    verify_sender_identity_sql,
)


def isolate_account(account_id: str, reason: str) -> str:
    """
    Isola un account Active Directory compromesso o a rischio.

    Usato negli scenari 1 (phishing + credenziali), 4 (login anomali da Singapore)
    e 8 (tablet smarrito con sessioni VPN attive).

    Args:
        account_id: Identificativo AD (es. luca.verdi@impesud.it).
        reason: Sintesi dell'incidente che motiva l'isolamento.

    Returns:
        Messaggio di conferma per l'osservazione ReAct.
    """
    result = isolate_account_sql(account_id, reason)
    log_event(
        "account_isolated",
        {"account_id": account_id, "reason": reason[:300]},
    )
    print(f"🔒 [ISOLAMENTO] Account {account_id} isolato.", flush=True)
    return result


def verify_sender_identity(claimed_name: str, claimed_role: str) -> str:
    """
    Verifica la dichiarazione di identità del mittente contro il registro autorizzato.

    Usato nello scenario 9 (whaling / spoofing CEO): il testo «Sono il CEO» non
    è prova sufficiente senza lookup su authorized_identities.

    Args:
        claimed_name: Nome o titolo dichiarato (es. «CEO dell'azienda»).
        claimed_role: Ruolo dichiarato (es. «CEO»).

    Returns:
        Esito VERIFIED o SPOOFING_SUSPECTED con dettagli dal database.
    """
    result = verify_sender_identity_sql(claimed_name, claimed_role)
    log_event(
        "identity_verification",
        {
            "claimed_name": claimed_name,
            "claimed_role": claimed_role,
            "result_preview": result[:200],
        },
    )
    return result


def derive_account_id_from_name(full_name: str) -> str:
    """
    Deriva un account_id aziendale standard da «Nome Cognome».

    Esempio: «Luca Verdi» → luca.verdi@impesud.it
    """
    return account_to_email(full_name)
