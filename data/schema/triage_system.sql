-- Schema SQLite Long-Term Memory (Lezione 13)
-- Riferimento versionato in Git. Il file runtime data/triage_system.db
-- viene creato da init_db() ed è gitignored.

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nome TEXT NOT NULL,
    categoria TEXT NOT NULL,
    priorita TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    riassunto_breve TEXT NOT NULL,
    lingua TEXT NOT NULL,
    azione_eseguita TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cliente ON tickets(cliente_nome);

-- Progetto 2: eventi di accesso anomali (scenario 4)
CREATE TABLE IF NOT EXISTS access_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    cliente_nome TEXT NOT NULL,
    event_type TEXT NOT NULL,
    location TEXT,
    attempts INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_access_cliente ON access_events(cliente_nome);

-- Progetto 2: registro identità autorizzate (scenario 9)
CREATE TABLE IF NOT EXISTS authorized_identities (
    account_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    can_request_ad_changes INTEGER DEFAULT 0,
    verified_channel TEXT
);

CREATE TABLE IF NOT EXISTS isolated_accounts (
    account_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    isolated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
