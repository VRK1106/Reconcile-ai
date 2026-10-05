"""
Human-in-the-Loop (HITL) Service: Manages accountant review tasks, Telegram webhooks, and ledger commits.
"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.telemetry.prometheus import ACTIVE_HITL_TASKS

class HITLService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_tasks(self, status: Optional[str] = "PENDING") -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if status:
            cur.execute("""
                SELECT h.*, i.supplier_name, i.total_amount, i.invoice_number, i.matched_txns_json
                FROM hitl_tasks h
                JOIN invoices i ON h.invoice_id = i.invoice_id
                WHERE h.status = ?
                ORDER BY h.created_at DESC
            """, (status,))
        else:
            cur.execute("""
                SELECT h.*, i.supplier_name, i.total_amount, i.invoice_number, i.matched_txns_json
                FROM hitl_tasks h
                JOIN invoices i ON h.invoice_id = i.invoice_id
                ORDER BY h.created_at DESC
            """)
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r["options"] = json.loads(r["options_json"])
            r["matched_txns"] = json.loads(r["matched_txns_json"])
        return rows

    def resolve_task(self, task_id: str, action: str, reviewer: str = "Suresh Bhat", notes: str = "") -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM hitl_tasks WHERE task_id = ?", (task_id,))
        task = cur.fetchone()
        if not task:
            raise ValueError(f"HITL Task '{task_id}' not found")

        inv_id = task["invoice_id"]
        cur.execute("SELECT * FROM invoices WHERE invoice_id = ?", (inv_id,))
        inv = cur.fetchone()

        new_status = "APPROVED" if "APPROVE" in action.upper() else "REJECTED"
        inv_new_status = "HITL_APPROVED" if new_status == "APPROVED" else "HITL_REJECTED"

        # Update HITL task
        cur.execute("""
            UPDATE hitl_tasks
            SET status = ?, resolved_by = ?, reviewer_notes = ?, resolved_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        """, (new_status, reviewer, notes, task_id))

        # Update Invoice
        cur.execute("""
            UPDATE invoices
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE invoice_id = ?
        """, (inv_new_status, inv_id))

        # If approved, update matched bank transaction(s)
        if new_status == "APPROVED" and inv["matched_txns_json"]:
            matched_txns = json.loads(inv["matched_txns_json"])
            for t_id in matched_txns:
                cur.execute("""
                    UPDATE bank_transactions
                    SET reconciliation_status = 'RECONCILED', matched_invoice_id = ?, matched_at = CURRENT_TIMESTAMP
                    WHERE txn_id = ?
                """, (inv_id, t_id))

        # Record Audit event
        cur.execute("""
            INSERT INTO audit_events (trace_id, event_type, actor, entity_type, entity_id, payload_json)
            VALUES (?, 'HITL_TASK_RESOLVED', ?, 'HITL_TASK', ?, ?)
        """, (inv["trace_id"], f"USER:{reviewer}", task_id, json.dumps({"action": action, "notes": notes, "invoice_id": inv_id})))

        self.conn.commit()
        ACTIVE_HITL_TASKS.dec()

        return {
            "task_id": task_id,
            "invoice_id": inv_id,
            "status": new_status,
            "resolved_by": reviewer,
            "resolved_at": datetime.now().isoformat()
        }
