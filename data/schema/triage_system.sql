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
