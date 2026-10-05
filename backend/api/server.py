"""
Enterprise FastAPI Server for Autonomous Invoice Reconciliation Agent.
Exposes REST endpoints, Prometheus telemetry, audit trail, and serves the operations console.
"""
import os
import json
import sqlite3
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, PlainTextResponse
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from backend.db.database import get_connection, init_db, seed_initial_data
from backend.services.agent_service import AgentService
from backend.services.hitl_service import HITLService
from backend.services.email_service import EmailGateService
from backend.telemetry.prometheus import perf_tracker

app = FastAPI(
    title="Autonomous Invoice Reconciliation Enterprise System",
    description="Production-grade 3-layer reconciliation agent with rule guardrails, multi-step tool reasoning, Prometheus metrics, and HITL governance.",
    version="2.0.0"
)

# Enable CORS for external integrations & frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class InvoiceIngestRequest(BaseModel):
    invoice_id: Optional[str] = None
    invoice_number: str
    supplier_name: str
    supplier_gstin: str
    invoice_date: str
    subtotal: float
    tax_amount: float
    total_amount: float
    due_date: Optional[str] = None
    source: Optional[str] = "email"

class HITLResolveRequest(BaseModel):
    action: str # APPROVE or REJECT
    reviewer: Optional[str] = "Suresh Bhat (Senior Accountant)"
    notes: Optional[str] = ""

class EmailDispatchRequest(BaseModel):
    authorized_by: Optional[str] = "Suresh Bhat"

# Startup event
@app.on_event("startup")
def startup_event():
    init_db()
    seed_initial_data()
    # Trigger benchmark initial batch if empty
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM invoices")
        if cur.fetchone()["cnt"] == 0:
            print("[System Startup] Pre-populating benchmark invoices into persistent database...")
            if os.path.exists("data/invoices.json"):
                with open("data/invoices.json", "r", encoding="utf-8") as f:
                    inv_list = json.load(f)
                agent = AgentService(conn)
                for inv in inv_list:
                    agent.process_invoice(inv)
                print(f"[System Startup] Successfully reconciled {len(inv_list)} benchmark invoices.")
        # Rehydrate in-memory performance and OpenTelemetry metrics from database
        perf_tracker.hydrate_from_db(conn)
    finally:
        conn.close()

# 1. Health & Readiness Probe
@app.get("/api/v1/health")
def health_check():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1")
    conn.close()
    return {
        "status": "HEALTHY",
        "service": "ReconcileAI Autonomous Engine",
        "version": "2.0.0",
        "business": "Sri Krishna Electricals & Hardware, Tiger Circle, Manipal",
        "database": "CONNECTED_WAL_MODE",
        "governance": "HITL_STRICT_APPROVAL_GATE_ENABLED"
    }

# 2. Prometheus Scrape Endpoint
@app.get("/metrics")
def get_metrics():
    if perf_tracker.total_processed == 0:
        try:
            conn = get_connection()
            perf_tracker.hydrate_from_db(conn)
            conn.close()
        except Exception:
            pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# 3. Real-Time Telemetry & SLA Stats
@app.get("/api/v1/telemetry/performance")
def get_performance_telemetry():
    return perf_tracker.get_summary()

# 4. Ingestion Webhook Endpoint (Layer 1 -> Layer 2 -> Layer 3)
@app.post("/api/v1/invoices/ingest")
def ingest_invoice(invoice: InvoiceIngestRequest):
    conn = get_connection()
    try:
        agent = AgentService(conn)
        result = agent.process_invoice(invoice.dict())
        return {
            "success": True,
            "data": result
        }
    finally:
        conn.close()

# 5. List Invoices with Filters
@app.get("/api/v1/invoices")
def list_invoices(
    status: Optional[str] = Query(None, description="Filter by status (AUTO_RECONCILED, HITL_PENDING, etc.)"),
    confidence: Optional[str] = Query(None, description="Filter by confidence (HIGH, MEDIUM, LOW, ZERO)"),
    search: Optional[str] = Query(None, description="Search supplier or invoice number"),
    limit: int = 50,
    offset: int = 0
):
    conn = get_connection()
    try:
        cur = conn.cursor()
        query = "SELECT * FROM invoices WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if confidence:
            query += " AND confidence = ?"
            params.append(confidence)
        if search:
            query += " AND (supplier_name LIKE ? OR invoice_number LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

        for r in rows:
            r["guardrail_violations"] = json.loads(r["guardrail_violations_json"] or "[]")
            r["matched_txns"] = json.loads(r["matched_txns_json"] or "[]")
            r["reconciliation_details"] = json.loads(r["reconciliation_details_json"] or "{}")
            r["reasoning_trace"] = json.loads(r["reasoning_trace_json"] or "[]")

        return {
            "total": len(rows),
            "limit": limit,
            "offset": offset,
            "invoices": rows
        }
    finally:
        conn.close()

# 6. Deep Dive Invoice Details & Tool Traces
@app.get("/api/v1/invoices/{invoice_id}")
def get_invoice_detail(invoice_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")

        inv = dict(row)
        inv["guardrail_violations"] = json.loads(inv["guardrail_violations_json"] or "[]")
        inv["matched_txns"] = json.loads(inv["matched_txns_json"] or "[]")
        inv["reconciliation_details"] = json.loads(inv["reconciliation_details_json"] or "{}")
        inv["reasoning_trace"] = json.loads(inv["reasoning_trace_json"] or "[]")

        # Fetch Tool Calls for this invoice
        cur.execute("SELECT * FROM tool_calls WHERE invoice_id = ? ORDER BY created_at ASC", (invoice_id,))
        inv["tool_calls"] = [dict(t) for t in cur.fetchall()]

        # Fetch Matched Bank Transactions
        if inv["matched_txns"]:
            placeholders = ",".join("?" for _ in inv["matched_txns"])
            cur.execute(f"SELECT * FROM bank_transactions WHERE txn_id IN ({placeholders})", inv["matched_txns"])
            inv["matched_bank_rows"] = [dict(b) for b in cur.fetchall()]
        else:
            inv["matched_bank_rows"] = []

        return inv
    finally:
        conn.close()

# 7. Bank Transactions Ledger
@app.get("/api/v1/bank/transactions")
def list_bank_transactions(status: Optional[str] = None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if status:
            cur.execute("SELECT * FROM bank_transactions WHERE reconciliation_status = ? ORDER BY txn_date ASC", (status,))
        else:
            cur.execute("SELECT * FROM bank_transactions ORDER BY txn_date ASC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

# 8. Human-in-the-Loop (HITL) Queue
@app.get("/api/v1/hitl/tasks")
def list_hitl_tasks(status: Optional[str] = "PENDING"):
    conn = get_connection()
    try:
        hitl = HITLService(conn)
        return hitl.list_tasks(status=status)
    finally:
        conn.close()

# 9. Human-in-the-Loop (HITL) Resolution Callback
@app.post("/api/v1/hitl/tasks/{task_id}/resolve")
def resolve_hitl_task(task_id: str, body: HITLResolveRequest):
    conn = get_connection()
    try:
        hitl = HITLService(conn)
        result = hitl.resolve_task(task_id, body.action, reviewer=body.reviewer, notes=body.notes)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        conn.close()

# 10. Gated Email Outbox
@app.get("/api/v1/email-drafts")
def list_email_drafts():
    conn = get_connection()
    try:
        svc = EmailGateService(conn)
        return svc.list_drafts()
    finally:
        conn.close()

# 11. Authorize Gated Email Dispatch
@app.post("/api/v1/email-drafts/{draft_id}/dispatch")
def dispatch_email_draft(draft_id: str, body: EmailDispatchRequest):
    conn = get_connection()
    try:
        svc = EmailGateService(conn)
        res = svc.dispatch_draft(draft_id, authorized_by=body.authorized_by)
        return {"success": True, "data": res}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    finally:
        conn.close()

# 12. Audit Trail
@app.get("/api/v1/audit/logs")
def list_audit_logs(limit: int = 50):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,))
        logs = [dict(r) for r in cur.fetchall()]
        for l in logs:
            l["payload"] = json.loads(l["payload_json"])
        return logs
    finally:
        conn.close()

# 13. System Batch Re-Run Trigger
@app.post("/api/v1/system/reconcile-benchmark-batch")
def run_benchmark_batch():
    if not os.path.exists("data/invoices.json"):
        raise HTTPException(status_code=404, detail="data/invoices.json not found")
    
    with open("data/invoices.json", "r", encoding="utf-8") as f:
        invoices = json.load(f)

    conn = get_connection()
    try:
        # Reset bank transactions and invoices in proper foreign key order
        cur = conn.cursor()
        cur.execute("DELETE FROM hitl_tasks")
        cur.execute("DELETE FROM gated_email_outbox")
        cur.execute("DELETE FROM tool_calls")
        cur.execute("DELETE FROM audit_events")
        cur.execute("DELETE FROM invoices")
        cur.execute("UPDATE bank_transactions SET reconciliation_status = 'PENDING', matched_invoice_id = NULL, matched_at = NULL")
        conn.commit()

        agent = AgentService(conn)
        results = []
        for inv in invoices:
            res = agent.process_invoice(inv)
            results.append(res)

        return {
            "success": True,
            "processed_count": len(results),
            "telemetry": perf_tracker.get_summary()
        }
    finally:
        conn.close()

# Mount Console Static Files
console_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "console"))
if not os.path.exists(console_dir):
    console_dir = os.path.abspath(os.path.join(os.getcwd(), "console"))

if os.path.exists(console_dir):
    app.mount("/console", StaticFiles(directory=console_dir, html=True), name="console")

@app.get("/")
def root():
    return RedirectResponse(url="/console/")
