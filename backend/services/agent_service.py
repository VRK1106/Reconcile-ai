"""
Layer 3 Autonomous Reconciliation Agent Service.
Coordinates:
- Intake & Trace ID Generation
- Layer 2 Deterministic Guardrails
- Layer 3 Multi-Step Tool Reasoning (Alias matching, Subset sum, Partials, Discounts)
- Autonomous Ledger Commit (High Confidence) vs HITL Task Queue (Medium Confidence) vs Escalations (Low/Zero)
- Performance Telemetry & Audit Logging
"""
import time
import uuid
import json
import sqlite3
from typing import Dict, Any, List, Optional
from backend.services.guardrail_service import GuardrailService
from backend.services.tool_service import ToolService
from backend.telemetry.prometheus import (
    INVOICE_PROCESSED_TOTAL, RECONCILIATION_LATENCY, ACTIVE_HITL_TASKS, perf_tracker
)

class AgentService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.guardrails = GuardrailService(conn)
        self.tools = ToolService(conn)

    def process_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.perf_counter()
        trace_id = f"TRC-{uuid.uuid4().hex[:12].upper()}"
        inv_id = invoice_data.get("invoice_id") or f"INV-{uuid.uuid4().hex[:6].upper()}"
        inv_num = invoice_data.get("invoice_number", "UNKNOWN")
        supplier_name = invoice_data.get("supplier_name", "UNKNOWN")
        gstin = (invoice_data.get("supplier_gstin") or "").strip().upper()
        total_amount = float(invoice_data.get("total_amount", 0.0))
        subtotal = float(invoice_data.get("subtotal", 0.0))
        tax_amount = float(invoice_data.get("tax_amount", 0.0))
        inv_date = invoice_data.get("invoice_date", "")
        due_date = invoice_data.get("due_date", "")
        source = invoice_data.get("source", "email")

        reasoning_trace = [
            f"[Layer 1 Intake] Ingested invoice {inv_num} (ID: {inv_id}) from '{supplier_name}' (GSTIN: {gstin}) for ₹{total_amount:,.2f} via {source}."
        ]

        # ---------------------------------------------------------
        # LAYER 2: Deterministic Rule Guardrails
        # ---------------------------------------------------------
        guardrail_res = self.guardrails.execute_guardrails(invoice_data)
        if not guardrail_res["passed"]:
            v_text = "; ".join(guardrail_res["violations"])
            reasoning_trace.append(f"[Layer 2 Guardrail Failure] Blocked deterministically: {v_text}")
            
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO invoices (
                    invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                    subtotal, tax_amount, total_amount, due_date, source,
                    guardrail_passed, guardrail_violations_json, status, decision, confidence,
                    confidence_score, reasoning_trace_json, trace_id, total_processing_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 'GUARDRAIL_BLOCKED', 'BLOCKED_BY_GUARDRAIL', 'ZERO', 0.0, ?, ?, ?)
            """, (
                inv_id, inv_num, supplier_name, gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                json.dumps(guardrail_res["violations"]), json.dumps(reasoning_trace), trace_id, duration_ms
            ))
            
            # Record audit event
            cur.execute("""
                INSERT INTO audit_events (trace_id, event_type, actor, entity_type, entity_id, payload_json)
                VALUES (?, 'GUARDRAIL_BLOCKED', 'GUARDRAIL_ENGINE', 'INVOICE', ?, ?)
            """, (trace_id, inv_id, json.dumps({"violations": guardrail_res["violations"], "amount": total_amount})))
            
            self.conn.commit()

            INVOICE_PROCESSED_TOTAL.labels(source=source, status="GUARDRAIL_BLOCKED", confidence="ZERO").inc()
            RECONCILIATION_LATENCY.labels(decision="BLOCKED_BY_GUARDRAIL").observe(duration_ms / 1000.0)
            perf_tracker.record_invoice(duration_ms, "BLOCKED_BY_GUARDRAIL", "ZERO", False)

            return {
                "trace_id": trace_id,
                "invoice_id": inv_id,
                "invoice_number": inv_num,
                "supplier_name": supplier_name,
                "status": "GUARDRAIL_BLOCKED",
                "decision": "BLOCKED_BY_GUARDRAIL",
                "confidence": "ZERO",
                "confidence_score": 0.0,
                "reasoning_trace": reasoning_trace,
                "duration_ms": duration_ms
            }

        reasoning_trace.append(f"[Layer 2 Guardrails Passed] GSTIN format verified, tax math validated, duplicate check passed in {guardrail_res['duration_ms']}ms.")

        # ---------------------------------------------------------
        # LAYER 3: Multi-Step AI Agent Tool Reasoning
        # ---------------------------------------------------------
        # Tool 1: Supplier lookup
        supplier_info = self.tools.supplier_history_lookup(trace_id, inv_id, supplier_name)
        if not supplier_info:
            supplier_info = self.tools.supplier_history_lookup(trace_id, inv_id, gstin)

        if not supplier_info:
            reasoning_trace.append(f"[Tool: supplier_history_lookup] Supplier '{supplier_name}' (GSTIN: {gstin}) not found in master records.")
            reasoning_trace.append("[Layer 3 Escalation] Confidence LOW. Escalating to human accountant for vendor onboarding.")
            
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO invoices (
                    invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                    subtotal, tax_amount, total_amount, due_date, source,
                    guardrail_passed, guardrail_violations_json, status, decision, confidence,
                    confidence_score, reasoning_trace_json, trace_id, total_processing_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'ESCALATED_LOW_CONFIDENCE', 'UNRECOGNIZED_SUPPLIER', 'LOW', 0.35, ?, ?, ?)
            """, (
                inv_id, inv_num, supplier_name, gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                json.dumps(reasoning_trace), trace_id, duration_ms
            ))
            self.conn.commit()

            INVOICE_PROCESSED_TOTAL.labels(source=source, status="ESCALATED_LOW_CONFIDENCE", confidence="LOW").inc()
            RECONCILIATION_LATENCY.labels(decision="UNRECOGNIZED_SUPPLIER").observe(duration_ms / 1000.0)
            perf_tracker.record_invoice(duration_ms, "UNRECOGNIZED_SUPPLIER", "LOW", True)

            return {
                "trace_id": trace_id,
                "invoice_id": inv_id,
                "invoice_number": inv_num,
                "supplier_name": supplier_name,
                "status": "ESCALATED_LOW_CONFIDENCE",
                "decision": "UNRECOGNIZED_SUPPLIER",
                "confidence": "LOW",
                "confidence_score": 0.35,
                "reasoning_trace": reasoning_trace,
                "duration_ms": duration_ms
            }

        reasoning_trace.append(f"[Tool: supplier_history_lookup] Found master supplier '{supplier_info['name']}'. Aliases: {supplier_info['aliases']}.")

        # Tool 2: Exact Amount Bank Row Search
        exact_bank_matches = self.tools.bank_row_search(
            trace_id, inv_id,
            target_amount=total_amount,
            date_center=inv_date,
            days_window=35,
            amount_tolerance=0.001
        )

        if exact_bank_matches:
            reasoning_trace.append(f"[Tool: bank_row_search] Found {len(exact_bank_matches)} candidate transaction(s) with exact amount ₹{total_amount:,.2f}.")
            for candidate in exact_bank_matches:
                cand_narr = candidate["narration"].upper()
                name_match = (supplier_info["name"].upper() in cand_narr)
                alias_match = any(alias.upper() in cand_narr for alias in supplier_info.get("aliases", []))
                inv_match = (inv_num.upper() in cand_narr.replace("/", "").replace("-", ""))

                mem_matches = self.tools.corrections_memory_lookup(trace_id, inv_id, cand_narr)
                if mem_matches:
                    alias_match = True
                    reasoning_trace.append(f"[Tool: corrections_memory] Recalled historical human approval: '{mem_matches[0]['pattern']}' -> '{mem_matches[0]['resolved_to']}'.")

                if name_match or alias_match or inv_match:
                    reasoning_trace.append(f"[Match Verified] Bank Txn {candidate['txn_id']} ({candidate['ref_no']}) matches. Narration: '{candidate['narration']}'.")
                    reasoning_trace.append("[Autonomous Ledger Post] Confidence HIGH (0.98). Reconciling invoice and marking bank row as RECONCILED.")

                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    cur = self.conn.cursor()
                    
                    # Update Invoice
                    cur.execute("""
                        INSERT OR REPLACE INTO invoices (
                            invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                            subtotal, tax_amount, total_amount, due_date, source,
                            guardrail_passed, guardrail_violations_json, status, decision, confidence,
                            confidence_score, matched_txns_json, reconciliation_details_json,
                            reasoning_trace_json, trace_id, total_processing_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'AUTO_RECONCILED', 'AUTO_RESOLVE_PAID', 'HIGH', 0.98, ?, ?, ?, ?, ?)
                    """, (
                        inv_id, inv_num, supplier_info["name"], gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                        json.dumps([candidate["txn_id"]]),
                        json.dumps({"bank_txn_id": candidate["txn_id"], "amount": candidate["amount"], "ref_no": candidate["ref_no"]}),
                        json.dumps(reasoning_trace), trace_id, duration_ms
                    ))

                    # Update Bank Transaction to RECONCILED
                    cur.execute("""
                        UPDATE bank_transactions 
                        SET reconciliation_status = 'RECONCILED', matched_invoice_id = ?, matched_at = CURRENT_TIMESTAMP
                        WHERE txn_id = ?
                    """, (inv_id, candidate["txn_id"]))

                    # Record Audit Event
                    cur.execute("""
                        INSERT INTO audit_events (trace_id, event_type, actor, entity_type, entity_id, payload_json)
                        VALUES (?, 'INVOICE_AUTO_RECONCILED', 'AUTONOMOUS_AGENT', 'INVOICE', ?, ?)
                    """, (trace_id, inv_id, json.dumps({"bank_txn_id": candidate["txn_id"], "amount": candidate["amount"]})))

                    self.conn.commit()

                    INVOICE_PROCESSED_TOTAL.labels(source=source, status="AUTO_RECONCILED", confidence="HIGH").inc()
                    RECONCILIATION_LATENCY.labels(decision="AUTO_RESOLVE_PAID").observe(duration_ms / 1000.0)
                    perf_tracker.record_invoice(duration_ms, "AUTO_RESOLVE_PAID", "HIGH", True)

                    return {
                        "trace_id": trace_id,
                        "invoice_id": inv_id,
                        "invoice_number": inv_num,
                        "supplier_name": supplier_info["name"],
                        "status": "AUTO_RECONCILED",
                        "decision": "AUTO_RESOLVE_PAID",
                        "confidence": "HIGH",
                        "confidence_score": 0.98,
                        "matched_txns": [candidate["txn_id"]],
                        "reasoning_trace": reasoning_trace,
                        "duration_ms": duration_ms
                    }

        # Step 5: Test Combined / Split Payments (Subset Sum)
        reasoning_trace.append(f"[Tool: bank_row_search] No single bank row matched exact amount ₹{total_amount:,.2f}.")
        reasoning_trace.append("[Tool: invoice_list_lookup] Searching open invoices for supplier to evaluate combined payment hypothesis.")

        peer_invoices = self.tools.invoice_list_lookup(trace_id, inv_id, gstin)
        candidate_bank_rows_for_supplier = []
        for alias in [supplier_info["name"]] + supplier_info.get("aliases", []):
            candidate_bank_rows_for_supplier.extend(
                self.tools.bank_row_search(
                    trace_id, inv_id,
                    target_amount=None,
                    date_center=inv_date,
                    days_window=30,
                    narration_query=alias
                )
            )

        unique_cand_rows = {r["txn_id"]: r for r in candidate_bank_rows_for_supplier}.values()

        # Subset sum check
        for peer in peer_invoices:
            peer_amt = float(peer.get("total_amount", 0.0))
            combined_sum = round(total_amount + peer_amt, 2)
            for b_row in unique_cand_rows:
                if abs(b_row["amount"] - combined_sum) <= 1.0:
                    reasoning_trace.append(
                        f"[Combined Match Found] Bank Txn {b_row['txn_id']} (₹{b_row['amount']:,.2f}) matches sum of {inv_num} (₹{total_amount:,.2f}) + {peer['invoice_number']} (₹{peer_amt:,.2f})."
                    )
                    reasoning_trace.append("[HITL Queue] Confidence MEDIUM (0.80). Generating 1-tap review task for Suresh Bhat.")

                    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    task_id = f"HITL-{uuid.uuid4().hex[:6].upper()}"
                    prompt_text = (
                        f"Bank debit of ₹{b_row['amount']:,.2f} on {b_row['txn_date']} ({b_row['ref_no']}) "
                        f"covers Invoice {inv_num} (₹{total_amount:,.2f}) and Invoice {peer['invoice_number']} (₹{peer_amt:,.2f})."
                    )

                    cur = self.conn.cursor()
                    cur.execute("""
                        INSERT OR REPLACE INTO invoices (
                            invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                            subtotal, tax_amount, total_amount, due_date, source,
                            guardrail_passed, guardrail_violations_json, status, decision, confidence,
                            confidence_score, matched_txns_json, reconciliation_details_json,
                            reasoning_trace_json, trace_id, total_processing_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'HITL_PENDING', 'COMBINED_PAYMENT_SUGGESTED', 'MEDIUM', 0.80, ?, ?, ?, ?, ?)
                    """, (
                        inv_id, inv_num, supplier_info["name"], gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                        json.dumps([b_row["txn_id"]]),
                        json.dumps({"bank_txn_id": b_row["txn_id"], "combined_amount": b_row["amount"], "peer_invoice_id": peer["invoice_id"]}),
                        json.dumps(reasoning_trace), trace_id, duration_ms
                    ))

                    cur.execute("""
                        INSERT INTO hitl_tasks (task_id, invoice_id, task_type, title, prompt_text, options_json, status)
                        VALUES (?, ?, 'COMBINED_PAYMENT', 'Approve Combined Payment Reconciliation', ?, ?, 'PENDING')
                    """, (
                        task_id, inv_id, prompt_text,
                        json.dumps(["Approve Combined Reconciliation", "Reject & Investigate"])
                    ))

                    self.conn.commit()

                    ACTIVE_HITL_TASKS.inc()
                    INVOICE_PROCESSED_TOTAL.labels(source=source, status="HITL_PENDING", confidence="MEDIUM").inc()
                    RECONCILIATION_LATENCY.labels(decision="COMBINED_PAYMENT_SUGGESTED").observe(duration_ms / 1000.0)
                    perf_tracker.record_invoice(duration_ms, "COMBINED_PAYMENT_SUGGESTED", "MEDIUM", True)

                    return {
                        "trace_id": trace_id,
                        "invoice_id": inv_id,
                        "invoice_number": inv_num,
                        "supplier_name": supplier_info["name"],
                        "status": "HITL_PENDING",
                        "decision": "COMBINED_PAYMENT_SUGGESTED",
                        "confidence": "MEDIUM",
                        "confidence_score": 0.80,
                        "hitl_task_id": task_id,
                        "reasoning_trace": reasoning_trace,
                        "duration_ms": duration_ms
                    }

        # Step 6: Test Partial Payments & Cash Discounts
        for b_row in unique_cand_rows:
            # Partial payment
            if "PART" in b_row["narration"].upper() and b_row["amount"] < total_amount:
                balance = round(total_amount - b_row["amount"], 2)
                reasoning_trace.append(f"[Partial Payment Found] Bank Txn {b_row['txn_id']} (₹{b_row['amount']:,.2f}) indicates partial payment. Balance due: ₹{balance:,.2f}.")
                
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                task_id = f"HITL-{uuid.uuid4().hex[:6].upper()}"
                prompt_text = f"Partial payment of ₹{b_row['amount']:,.2f} recorded for ₹{total_amount:,.2f} invoice. Balance remaining: ₹{balance:,.2f}."

                cur = self.conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO invoices (
                        invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                        subtotal, tax_amount, total_amount, due_date, source,
                        guardrail_passed, guardrail_violations_json, status, decision, confidence,
                        confidence_score, matched_txns_json, reconciliation_details_json,
                        reasoning_trace_json, trace_id, total_processing_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'HITL_PENDING', 'PARTIAL_PAYMENT_DETECTED', 'MEDIUM', 0.78, ?, ?, ?, ?, ?)
                """, (
                    inv_id, inv_num, supplier_info["name"], gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                    json.dumps([b_row["txn_id"]]),
                    json.dumps({"bank_txn_id": b_row["txn_id"], "paid_amount": b_row["amount"], "balance_due": balance}),
                    json.dumps(reasoning_trace), trace_id, duration_ms
                ))

                cur.execute("""
                    INSERT INTO hitl_tasks (task_id, invoice_id, task_type, title, prompt_text, options_json, status)
                    VALUES (?, ?, 'PARTIAL_PAYMENT', 'Confirm Partial Payment Posting', ?, ?, 'PENDING')
                """, (task_id, inv_id, prompt_text, json.dumps(["Record Partial Payment", "Flag Disputed"])))

                self.conn.commit()
                ACTIVE_HITL_TASKS.inc()
                INVOICE_PROCESSED_TOTAL.labels(source=source, status="HITL_PENDING", confidence="MEDIUM").inc()
                RECONCILIATION_LATENCY.labels(decision="PARTIAL_PAYMENT_DETECTED").observe(duration_ms / 1000.0)
                perf_tracker.record_invoice(duration_ms, "PARTIAL_PAYMENT_DETECTED", "MEDIUM", True)

                return {
                    "trace_id": trace_id,
                    "invoice_id": inv_id,
                    "invoice_number": inv_num,
                    "supplier_name": supplier_info["name"],
                    "status": "HITL_PENDING",
                    "decision": "PARTIAL_PAYMENT_DETECTED",
                    "confidence": "MEDIUM",
                    "confidence_score": 0.78,
                    "hitl_task_id": task_id,
                    "reasoning_trace": reasoning_trace,
                    "duration_ms": duration_ms
                }

            # Prompt discount variance
            discount_pct = (total_amount - b_row["amount"]) / total_amount
            if 0.0 < discount_pct <= 0.025:
                reasoning_trace.append(f"[Discount Variance] Bank debit ₹{b_row['amount']:,.2f} corresponds to {discount_pct*100:.1f}% prompt cash discount.")
                duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                task_id = f"HITL-{uuid.uuid4().hex[:6].upper()}"
                prompt_text = f"Bank debit ₹{b_row['amount']:,.2f} reflects a {discount_pct*100:.1f}% settlement discount against ₹{total_amount:,.2f}."

                cur = self.conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO invoices (
                        invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                        subtotal, tax_amount, total_amount, due_date, source,
                        guardrail_passed, guardrail_violations_json, status, decision, confidence,
                        confidence_score, matched_txns_json, reconciliation_details_json,
                        reasoning_trace_json, trace_id, total_processing_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'HITL_PENDING', 'CASH_DISCOUNT_SETTLEMENT', 'MEDIUM', 0.82, ?, ?, ?, ?, ?)
                """, (
                    inv_id, inv_num, supplier_info["name"], gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
                    json.dumps([b_row["txn_id"]]),
                    json.dumps({"bank_txn_id": b_row["txn_id"], "paid_amount": b_row["amount"], "discount_amount": round(total_amount - b_row["amount"], 2)}),
                    json.dumps(reasoning_trace), trace_id, duration_ms
                ))

                cur.execute("""
                    INSERT INTO hitl_tasks (task_id, invoice_id, task_type, title, prompt_text, options_json, status)
                    VALUES (?, ?, 'DISCOUNT_VARIANCE', 'Approve Cash Discount Adjustment', ?, ?, 'PENDING')
                """, (task_id, inv_id, prompt_text, json.dumps(["Approve Discount Write-Off", "Reject"])))

                self.conn.commit()
                ACTIVE_HITL_TASKS.inc()
                INVOICE_PROCESSED_TOTAL.labels(source=source, status="HITL_PENDING", confidence="MEDIUM").inc()
                RECONCILIATION_LATENCY.labels(decision="CASH_DISCOUNT_SETTLEMENT").observe(duration_ms / 1000.0)
                perf_tracker.record_invoice(duration_ms, "CASH_DISCOUNT_SETTLEMENT", "MEDIUM", True)

                return {
                    "trace_id": trace_id,
                    "invoice_id": inv_id,
                    "invoice_number": inv_num,
                    "supplier_name": supplier_info["name"],
                    "status": "HITL_PENDING",
                    "decision": "CASH_DISCOUNT_SETTLEMENT",
                    "confidence": "MEDIUM",
                    "confidence_score": 0.82,
                    "hitl_task_id": task_id,
                    "reasoning_trace": reasoning_trace,
                    "duration_ms": duration_ms
                }

        # Step 7: No bank debit found -> Draft approval-gated follow-up email
        reasoning_trace.append(f"[No Bank Match] No debit found for ₹{total_amount:,.2f} from {supplier_info['name']}.")
        reasoning_trace.append("[Tool: draft_email_tool] Status is UNPAID. Generated gated supplier follow-up email (Held in queue).")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO invoices (
                invoice_id, invoice_number, supplier_name, supplier_gstin, invoice_date,
                subtotal, tax_amount, total_amount, due_date, source,
                guardrail_passed, guardrail_violations_json, status, decision, confidence,
                confidence_score, matched_txns_json, reconciliation_details_json,
                reasoning_trace_json, trace_id, total_processing_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '[]', 'ESCALATED_UNPAID', 'UNPAID_EMAIL_DRAFTED', 'HIGH', 0.90, '[]', '{}', ?, ?, ?)
        """, (
            inv_id, inv_num, supplier_info["name"], gstin, inv_date, subtotal, tax_amount, total_amount, due_date, source,
            json.dumps(reasoning_trace), trace_id, duration_ms
        ))

        email_draft = self.tools.draft_email_tool(
            trace_id, inv_id,
            recipient_email=supplier_info.get("email") or "billing@supplier.com",
            supplier_name=supplier_info["name"],
            invoice_number=inv_num,
            amount=total_amount,
            reason=f"No matching bank debit identified. Due date: {due_date}."
        )
        self.conn.commit()

        INVOICE_PROCESSED_TOTAL.labels(source=source, status="ESCALATED_UNPAID", confidence="HIGH").inc()
        RECONCILIATION_LATENCY.labels(decision="UNPAID_EMAIL_DRAFTED").observe(duration_ms / 1000.0)
        perf_tracker.record_invoice(duration_ms, "UNPAID_EMAIL_DRAFTED", "HIGH", True)

        return {
            "trace_id": trace_id,
            "invoice_id": inv_id,
            "invoice_number": inv_num,
            "supplier_name": supplier_info["name"],
            "status": "ESCALATED_UNPAID",
            "decision": "UNPAID_EMAIL_DRAFTED",
            "confidence": "HIGH",
            "confidence_score": 0.90,
            "email_draft": email_draft,
            "reasoning_trace": reasoning_trace,
            "duration_ms": duration_ms
        }
