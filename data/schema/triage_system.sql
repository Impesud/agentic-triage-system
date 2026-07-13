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
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_usd_milli INTEGER,
    latency_ms INTEGER,
    llm_calls INTEGER,
    pipeline TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cliente ON tickets(cliente_nome);
CREATE INDEX IF NOT EXISTS idx_tickets_categoria_cost ON tickets(categoria, cost_usd_milli);

-- Lezione 18: allerte guardrail sicurezza
CREATE TABLE IF NOT EXISTS security_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    blocked_stage TEXT NOT NULL,
    matched_pattern TEXT,
    input_excerpt TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_alerts_type ON security_alerts(alert_type);

-- Lezione 19: sessioni HITL in attesa di approvazione
CREATE TABLE IF NOT EXISTS ticket_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    breakpoint_stage TEXT NOT NULL,
    pending_tool TEXT NOT NULL,
    pending_args_json TEXT NOT NULL,
    stm_json TEXT NOT NULL,
    pipeline_context_json TEXT,
    user_input_excerpt TEXT NOT NULL,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_states_status ON ticket_states(status);
