"""
Layer 3 Tool Service: Provides the 5 Reconciliation Tools with telemetry and audit capture.
1. bank_row_search
2. supplier_history_lookup
3. invoice_list_lookup
4. corrections_memory_lookup
5. draft_email_tool (gated by human authorization)
"""
import time
import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.telemetry.prometheus import TOOL_EXECUTIONS_TOTAL, TOOL_LATENCY_HISTOGRAM, perf_tracker

GENERIC_STOP_WORDS = {"elec", "ltd", "india", "co", "trading", "and", "cables", "wires", "solutions", "industries", "company"}

class ToolService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.memory_rules = [
            {
                "case_type": "alias_name_resolution",
                "pattern": "SHARMA TRDRS BLR",
                "resolved_to": "Sharma Trading Company",
                "notes": "Approved by Suresh Bhat on 2026-08-15"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "POLYWIRES",
                "resolved_to": "Polycab Wires & Cables Ltd",
                "notes": "Approved on 2026-08-20"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "HAVELLS KA",
                "resolved_to": "Havells India Limited",
                "notes": "Approved on 2026-08-28"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "SUPREME PLAST",
                "resolved_to": "Supreme Industries Ltd",
                "notes": "Approved on 2026-08-30"
            },
            {
                "case_type": "cash_discount_tolerance",
                "pattern": "LESS 2PCT CASH DISC",
                "rule": "Allow up to 2.5% settlement discount if narration specifies cash discount or prompt payment",
                "notes": "Godrej standard prompt payment dealer discount terms"
            }
        ]

    def _record_tool_call(self, trace_id: str, invoice_id: str, tool_name: str, inputs: Dict[str, Any], outputs: Any, duration_ms: float):
        TOOL_EXECUTIONS_TOTAL.labels(tool_name=tool_name).inc()
        TOOL_LATENCY_HISTOGRAM.labels(tool_name=tool_name).observe(duration_ms / 1000.0)
        perf_tracker.record_tool(tool_name, duration_ms)

        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO tool_calls (trace_id, invoice_id, tool_name, inputs_json, outputs_json, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (trace_id, invoice_id, tool_name, json.dumps(inputs), json.dumps(outputs, default=str), duration_ms))

    def supplier_history_lookup(self, trace_id: str, invoice_id: str, query: str) -> Optional[Dict[str, Any]]:
        start = time.perf_counter()
        q = query.strip().lower()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM suppliers")
        rows = cur.fetchall()

        matched = None
        for r in rows:
            name = r["name"].lower()
            gstin = r["gstin"].lower()
            aliases = [a.lower() for a in json.loads(r["aliases_json"])]

            if q == gstin or q == name or any(a in q or q in a for a in aliases) or (name in q or q in name):
                matched = {
                    "supplier_id": r["supplier_id"],
                    "name": r["name"],
                    "gstin": r["gstin"],
                    "aliases": json.loads(r["aliases_json"]),
                    "email": r["email"],
                    "category": r["category"],
                    "payment_terms_days": r["payment_terms_days"]
                }
                break

        dur = round((time.perf_counter() - start) * 1000, 3)
        self._record_tool_call(trace_id, invoice_id, "supplier_history_lookup", {"query": query}, matched, dur)
        return matched

    def bank_row_search(
        self,
        trace_id: str,
        invoice_id: str,
        target_amount: Optional[float] = None,
        date_center: Optional[str] = None,
        days_window: int = 45,
        narration_query: Optional[str] = None,
        amount_tolerance: float = 0.001
    ) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM bank_transactions WHERE reconciliation_status != 'RECONCILED'")
        all_txns = cur.fetchall()

        center_dt = None
        if date_center:
            try:
                center_dt = datetime.strptime(date_center, "%Y-%m-%d")
            except ValueError:
                pass

        matches = []
        for txn in all_txns:
            # 1. Date window
            if center_dt:
                try:
                    txn_dt = datetime.strptime(txn["txn_date"], "%Y-%m-%d")
                    if abs((txn_dt - center_dt).days) > days_window:
                        continue
                except ValueError:
                    pass

            # 2. Amount match
            amt_ok = True
            if target_amount is not None:
                diff = abs(txn["amount"] - target_amount)
                amt_ok = (diff <= (target_amount * amount_tolerance)) or (diff <= 1.0)

            # 3. Narration query
            narr_ok = True
            if narration_query:
                q_clean = narration_query.lower().strip()
                t_narr = txn["narration"].lower()
                if q_clean in t_narr:
                    narr_ok = True
                else:
                    tokens = [w for w in q_clean.replace("/", " ").replace("-", " ").split() if len(w) > 2 and w not in GENERIC_STOP_WORDS]
                    narr_ok = any(t in t_narr for t in tokens) if tokens else (q_clean in t_narr)

            if target_amount is not None and narration_query is not None:
                if amt_ok and narr_ok:
                    matches.append(dict(txn))
            elif target_amount is not None:
                if amt_ok:
                    matches.append(dict(txn))
            elif narration_query is not None:
                if narr_ok:
                    matches.append(dict(txn))
            else:
                matches.append(dict(txn))

        dur = round((time.perf_counter() - start) * 1000, 3)
        self._record_tool_call(
            trace_id, invoice_id, "bank_row_search",
            {"target_amount": target_amount, "date_center": date_center, "narration_query": narration_query},
            [m["txn_id"] for m in matches], dur
        )
        return matches

    def invoice_list_lookup(self, trace_id: str, invoice_id: str, supplier_gstin: str) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM invoices 
            WHERE supplier_gstin = ? AND invoice_id != ? AND status NOT IN ('AUTO_RECONCILED', 'HITL_APPROVED')
        """, (supplier_gstin, invoice_id))
        rows = [dict(r) for r in cur.fetchall()]

        dur = round((time.perf_counter() - start) * 1000, 3)
        self._record_tool_call(trace_id, invoice_id, "invoice_list_lookup", {"supplier_gstin": supplier_gstin}, len(rows), dur)
        return rows

    def corrections_memory_lookup(self, trace_id: str, invoice_id: str, text: str) -> List[Dict[str, Any]]:
        start = time.perf_counter()
        t_low = text.lower()
        matched = [m for m in self.memory_rules if m["pattern"].lower() in t_low or t_low in m["pattern"].lower()]

        dur = round((time.perf_counter() - start) * 1000, 3)
        self._record_tool_call(trace_id, invoice_id, "corrections_memory_lookup", {"text": text}, matched, dur)
        return matched

    def draft_email_tool(
        self,
        trace_id: str,
        invoice_id: str,
        recipient_email: str,
        supplier_name: str,
        invoice_number: str,
        amount: float,
        reason: str
    ) -> Dict[str, Any]:
        start = time.perf_counter()
        draft_id = f"DRAFT-{int(time.time() * 1000) % 1000000:06d}"
        subject = f"Inquiry: Payment Status for Invoice {invoice_number} (₹{amount:,.2f}) - Sri Krishna Electricals Manipal"
        body = (
            f"Dear {supplier_name} Accounts Team,\n\n"
            f"We are reviewing our purchase ledger for Invoice No. {invoice_number} dated for ₹{amount:,.2f}.\n"
            f"Automated reconciliation status note:\n"
            f"'{reason}'.\n\n"
            f"Could you please confirm the payment UTR / bank reference or provide an updated statement of account?\n\n"
            f"Warm regards,\n"
            f"Suresh Bhat (Accounts Department)\n"
            f"Sri Krishna Electricals & Hardware, Tiger Circle, Manipal - 576104\n"
            f"Phone: +91 98450 12345"
        )

        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO gated_email_outbox (draft_id, invoice_id, recipient_email, subject, body, status, safety_gate)
            VALUES (?, ?, ?, ?, ?, 'HELD_FOR_APPROVAL', 'MANDATORY_HUMAN_AUTHORIZATION')
        """, (draft_id, invoice_id, recipient_email, subject, body))

        draft = {
            "draft_id": draft_id,
            "to": recipient_email,
            "subject": subject,
            "body": body,
            "status": "HELD_FOR_APPROVAL",
            "safety_gate": "MANDATORY_HUMAN_AUTHORIZATION"
        }

        dur = round((time.perf_counter() - start) * 1000, 3)
        self._record_tool_call(trace_id, invoice_id, "draft_email_tool", {"invoice_number": invoice_number, "to": recipient_email}, draft_id, dur)
        return draft
