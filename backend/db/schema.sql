-- Enterprise Database Schema for Autonomous Invoice Reconciliation Agent
-- Supports ACID transactions, relational integrity, audit logging, and telemetry

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    gstin TEXT NOT NULL UNIQUE,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    email TEXT,
    phone TEXT,
    city TEXT,
    category TEXT,
    payment_terms_days INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bank_transactions (
    txn_id TEXT PRIMARY KEY,
    txn_date TEXT NOT NULL,
    txn_type TEXT NOT NULL DEFAULT 'DEBIT',
    amount REAL NOT NULL,
    narration TEXT NOT NULL,
    ref_no TEXT NOT NULL,
    reconciliation_status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, RECONCILED, UNMATCHED
    matched_invoice_id TEXT,
    matched_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    supplier_gstin TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    subtotal REAL NOT NULL,
    tax_amount REAL NOT NULL,
    total_amount REAL NOT NULL,
    due_date TEXT,
    source TEXT NOT NULL DEFAULT 'email', -- email, telegram, upload, webhook
    layer1_extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Layer 2 Guardrail state
    guardrail_passed INTEGER NOT NULL DEFAULT 1,
    guardrail_violations_json TEXT DEFAULT '[]',
    
    -- Layer 3 Agent & Decision state
    status TEXT NOT NULL DEFAULT 'INTAKE', -- INTAKE, GUARDRAIL_BLOCKED, AUTO_RECONCILED, HITL_PENDING, HITL_APPROVED, HITL_REJECTED, ESCALATED_UNPAID, ESCALATED_LOW_CONFIDENCE
    decision TEXT,
    confidence TEXT, -- HIGH, MEDIUM, LOW, ZERO
    confidence_score REAL DEFAULT 0.0,
    matched_txns_json TEXT DEFAULT '[]',
    reconciliation_details_json TEXT DEFAULT '{}',
    reasoning_trace_json TEXT DEFAULT '[]',
    trace_id TEXT,
    total_processing_ms REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_calls (
    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    outputs_json TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hitl_tasks (
    task_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    task_type TEXT NOT NULL, -- COMBINED_PAYMENT, PARTIAL_PAYMENT, DISCOUNT_VARIANCE, UNRECOGNIZED_SUPPLIER
    title TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    options_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED, ESCALATED
    assigned_to TEXT DEFAULT 'Suresh Bhat (Senior Accountant)',
    reviewer_notes TEXT,
    resolved_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS gated_email_outbox (
    draft_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'HELD_FOR_APPROVAL', -- HELD_FOR_APPROVAL, DISPATCHED, DISMISSED
    safety_gate TEXT NOT NULL DEFAULT 'MANDATORY_HUMAN_AUTHORIZATION',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dispatched_at TIMESTAMP,
    authorized_by TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL, -- SYSTEM, AGENT, GUARDRAILS, USER:SureshBhat
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS telemetry_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_invoices INTEGER NOT NULL,
    auto_resolved_count INTEGER NOT NULL,
    hitl_pending_count INTEGER NOT NULL,
    blocked_count INTEGER NOT NULL,
    avg_latency_ms REAL NOT NULL,
    p95_latency_ms REAL NOT NULL,
    cpu_percent REAL NOT NULL,
    memory_mb REAL NOT NULL
);

-- Indexes for lightning-fast queries
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_gstin ON invoices(supplier_gstin);
CREATE INDEX IF NOT EXISTS idx_bank_amount ON bank_transactions(amount);
CREATE INDEX IF NOT EXISTS idx_tool_trace ON tool_calls(trace_id);
CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_tasks(status);
