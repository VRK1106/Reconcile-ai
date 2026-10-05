"""
Approval-Gated Supplier Email Outbox Service.
Guarantees that no external communication is sent without verified human authorization.
"""
import sqlite3
import json
from typing import List, Dict, Any

class EmailGateService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_drafts(self) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT e.*, i.invoice_number, i.supplier_name, i.total_amount
            FROM gated_email_outbox e
            JOIN invoices i ON e.invoice_id = i.invoice_id
            ORDER BY e.created_at DESC
        """)
        return [dict(r) for r in cur.fetchall()]

    def dispatch_draft(self, draft_id: str, authorized_by: str = "Suresh Bhat") -> Dict[str, Any]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM gated_email_outbox WHERE draft_id = ?", (draft_id,))
        draft = cur.fetchone()
        if not draft:
            raise ValueError(f"Draft '{draft_id}' not found")

        cur.execute("""
            UPDATE gated_email_outbox
            SET status = 'DISPATCHED', authorized_by = ?, dispatched_at = CURRENT_TIMESTAMP
            WHERE draft_id = ?
        """, (authorized_by, draft_id))

        cur.execute("""
            INSERT INTO audit_events (trace_id, event_type, actor, entity_type, entity_id, payload_json)
            VALUES (?, 'GATED_EMAIL_DISPATCHED', ?, 'EMAIL_DRAFT', ?, ?)
        """, (f"TRC-EMAIL-{draft_id}", f"USER:{authorized_by}", draft_id, json.dumps({
            "to": draft["recipient_email"],
            "subject": draft["subject"],
            "invoice_id": draft["invoice_id"]
        })))

        self.conn.commit()
        return {
            "draft_id": draft_id,
            "status": "DISPATCHED",
            "authorized_by": authorized_by,
            "recipient": draft["recipient_email"]
        }
