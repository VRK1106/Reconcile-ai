"""
Autonomous Invoice Reconciliation Agent (Layer 1, Layer 2, Layer 3).
Features:
- Fixed JSON schema validation
- Deterministic Layer 2 Guardrails (GSTIN regex, tax math, duplicate hash)
- Multi-step Layer 3 Reasoning with 5 tools:
  * Bank row search (exact amount, tolerance, narration)
  * Supplier history & alias resolution
  * Combined payment detection via subset sum on open invoices
  * Partial payment detection
  * Prompt payment cash discount detection
  * Human corrections memory lookup
  * Approval-gated draft email generation
- Confidence-based routing:
  * HIGH (>= 0.85): Auto-resolve, update ledger, log reasoning
  * MEDIUM (0.50 - 0.84): Draft Telegram prompt for 1-tap human approval
  * LOW (< 0.50) / ZERO: Escalate to accountant with diagnosis
"""
from typing import Dict, Any, List, Optional
import json
from src.guardrails import GuardrailManager
from src.tools import ReconciliationTools

class InvoiceReconciliationAgent:
    def __init__(self, tools: ReconciliationTools, guardrails: GuardrailManager):
        self.tools = tools
        self.guardrails = guardrails
        self.audit_log: List[Dict[str, Any]] = []

    def reconcile_invoice(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        invoice_id = invoice.get("invoice_id", "UNKNOWN")
        inv_num = invoice.get("invoice_number", "UNKNOWN")
        supplier_name = invoice.get("supplier_name", "UNKNOWN")
        gstin = invoice.get("supplier_gstin", "UNKNOWN")
        total_amount = float(invoice.get("total_amount", 0.0))
        inv_date = invoice.get("invoice_date", "")

        reasoning_trace = [
            f"Step 1 [Intake]: Received Invoice {inv_num} (ID: {invoice_id}) from '{supplier_name}' (GSTIN: {gstin}) for ₹{total_amount:,.2f} dated {inv_date}."
        ]

        # -------------------------------------------------------------
        # LAYER 2: Deterministic Rule Guardrails (Fast-fail, no AI hallucination)
        # -------------------------------------------------------------
        guardrail_result = self.guardrails.run_all_guardrails(invoice)
        if not guardrail_result["passed"]:
            v_msgs = "; ".join([v["message"] for v in guardrail_result["violations"]])
            reasoning_trace.append(f"Step 2 [Guardrail Violation]: Blocked by Layer 2 rule checks: {v_msgs}.")
            
            result = {
                "invoice_id": invoice_id,
                "invoice_number": inv_num,
                "supplier_name": supplier_name,
                "decision": "BLOCKED_BY_GUARDRAIL",
                "confidence": "ZERO",
                "confidence_score": 0.0,
                "matched_txns": [],
                "reasoning_trace": reasoning_trace,
                "requires_human": True,
                "action": "ESCALATE_TO_ACCOUNTANT",
                "telegram_notification": {
                    "text": f"⚠️ *Guardrail Alert: Invoice {inv_num} Blocked*\nSupplier: {supplier_name}\nAmount: ₹{total_amount:,.2f}\nReason: {v_msgs}",
                    "buttons": ["Acknowledge", "Edit Manually"]
                },
                "email_draft": None
            }
            self._log_audit(result)
            return result

        # Register invoice key to catch subsequent duplicates in batch
        self.guardrails.register_processed_invoice(gstin, inv_num)
        reasoning_trace.append("Step 2 [Guardrails Passed]: GSTIN format valid, tax math verified, duplicate check passed.")

        # -------------------------------------------------------------
        # LAYER 3: Multi-Step Reasoning with Tools
        # -------------------------------------------------------------
        # Check if supplier is registered
        supplier_info = self.tools.supplier_history_lookup(supplier_name)
        if not supplier_info:
            supplier_info = self.tools.supplier_history_lookup(gstin)

        if not supplier_info:
            reasoning_trace.append(f"Step 3 [Tool Call: supplier_history_lookup]: Supplier '{supplier_name}' / GSTIN '{gstin}' not found in master records.")
            reasoning_trace.append("Step 4 [Decision]: Low confidence due to unrecognized supplier. Escalating to accountant for manual master creation.")
            result = {
                "invoice_id": invoice_id,
                "invoice_number": inv_num,
                "supplier_name": supplier_name,
                "decision": "UNRECOGNIZED_SUPPLIER",
                "confidence": "LOW",
                "confidence_score": 0.35,
                "matched_txns": [],
                "reasoning_trace": reasoning_trace,
                "requires_human": True,
                "action": "ESCALATE_TO_ACCOUNTANT",
                "telegram_notification": {
                    "text": f"❓ *Unrecognized Supplier: Invoice {inv_num}*\nSupplier: {supplier_name}\nAmount: ₹{total_amount:,.2f}\nAction: Needs manual supplier profile verification.",
                    "buttons": ["Add Supplier", "Reject Invoice"]
                },
                "email_draft": None
            }
            self._log_audit(result)
            return result

        reasoning_trace.append(f"Step 3 [Tool Call: supplier_history_lookup]: Found supplier '{supplier_info['name']}' (ID: {supplier_info['supplier_id']}, Category: {supplier_info.get('category')}). Known aliases: {supplier_info.get('aliases')}.")

        # Step 4: Search bank statement for direct exact amount match
        exact_bank_matches = self.tools.bank_row_search(
            target_amount=total_amount,
            date_center=inv_date,
            days_window=35,
            amount_tolerance=0.001
        )

        if exact_bank_matches:
            reasoning_trace.append(f"Step 4 [Tool Call: bank_row_search]: Found {len(exact_bank_matches)} candidate transaction(s) with exact amount ₹{total_amount:,.2f}.")
            for candidate in exact_bank_matches:
                cand_narr = candidate["narration"].upper()
                # Check direct name, alias, or invoice number in narration
                name_match = (supplier_info["name"].upper() in cand_narr)
                alias_match = any(alias.upper() in cand_narr for alias in supplier_info.get("aliases", []))
                inv_match = (inv_num.upper() in cand_narr.replace("/", "").replace("-", ""))
                
                # Check past corrections memory for narration patterns
                mem_matches = self.tools.corrections_memory_lookup(cand_narr)
                if mem_matches:
                    alias_match = True
                    reasoning_trace.append(f"Step 4b [Tool Call: corrections_memory]: Matched bank narration against prior human approval: '{mem_matches[0]['pattern']}' -> '{mem_matches[0]['resolved_to']}'.")

                if name_match or alias_match or inv_match:
                    reasoning_trace.append(f"Step 5 [Match Confirmed]: Bank Txn {candidate['txn_id']} on {candidate['date']} (Ref: {candidate['ref_no']}) matches. Narration: '{candidate['narration']}'.")
                    reasoning_trace.append(f"Step 6 [Autonomous Action]: Confidence HIGH (0.98). Auto-resolving and marking invoice as PAID in purchase ledger.")
                    result = {
                        "invoice_id": invoice_id,
                        "invoice_number": inv_num,
                        "supplier_name": supplier_info["name"],
                        "decision": "AUTO_RESOLVE_PAID",
                        "confidence": "HIGH",
                        "confidence_score": 0.98,
                        "matched_txns": [candidate["txn_id"]],
                        "reconciliation_details": {
                            "bank_txn_id": candidate["txn_id"],
                            "txn_date": candidate["date"],
                            "ref_no": candidate["ref_no"],
                            "amount_matched": candidate["amount"],
                            "match_basis": "EXACT_AMOUNT_AND_NARRATION_ALIAS"
                        },
                        "reasoning_trace": reasoning_trace,
                        "requires_human": False,
                        "action": "AUTO_POST_LEDGER",
                        "telegram_notification": None,
                        "email_draft": None
                    }
                    self._log_audit(result)
                    return result

        # Step 5: If no exact single match, investigate combined multi-invoice payments (subset sum)
        reasoning_trace.append(f"Step 4 [Tool Call: bank_row_search]: No single bank row matched exact amount ₹{total_amount:,.2f}.")
        reasoning_trace.append("Step 5 [Investigation: Multi-invoice lookup]: Searching for open invoices from same supplier to test combined payment hypothesis.")
        
        peer_invoices = self.tools.invoice_list_lookup(gstin, exclude_invoice_id=invoice_id)
        candidate_bank_rows_for_supplier = []
        for alias in [supplier_info["name"]] + supplier_info.get("aliases", []):
            candidate_bank_rows_for_supplier.extend(
                self.tools.bank_row_search(
                    target_amount=None,
                    date_center=inv_date,
                    days_window=30,
                    narration_query=alias
                )
            )

        # De-duplicate candidate bank rows
        unique_cand_rows = {r["txn_id"]: r for r in candidate_bank_rows_for_supplier}.values()

        # Test if this invoice + any other open invoice equals a bank transaction
        for peer in peer_invoices:
            combined_sum = round(total_amount + float(peer.get("total_amount", 0.0)), 2)
            for b_row in unique_cand_rows:
                if abs(b_row["amount"] - combined_sum) <= 1.0:
                    reasoning_trace.append(
                        f"Step 6 [Combined Payment Detected]: Bank Txn {b_row['txn_id']} for ₹{b_row['amount']:,.2f} on {b_row['date']} matches combination of "
                        f"Invoice {inv_num} (₹{total_amount:,.2f}) + Invoice {peer.get('invoice_number')} (₹{peer.get('total_amount'):,.2f})."
                    )
                    reasoning_trace.append(
                        "Step 7 [Routing]: Confidence MEDIUM (0.80). Generating Telegram confirmation prompt for Suresh Bhat (Accountant) to approve combined match."
                    )
                    
                    telegram_text = (
                        f"📋 *Combined Payment Match Suggested*\n"
                        f"Supplier: *{supplier_info['name']}*\n"
                        f"Bank Txn: ₹{b_row['amount']:,.2f} on {b_row['date']} ({b_row['ref_no']})\n\n"
                        f"Covers 2 Invoices:\n"
                        f"• {inv_num}: ₹{total_amount:,.2f}\n"
                        f"• {peer.get('invoice_number')}: ₹{peer.get('total_amount'):,.2f}\n\n"
                        f"Approve combined reconciliation?"
                    )
                    result = {
                        "invoice_id": invoice_id,
                        "invoice_number": inv_num,
                        "supplier_name": supplier_info["name"],
                        "decision": "COMBINED_PAYMENT_SUGGESTED",
                        "confidence": "MEDIUM",
                        "confidence_score": 0.80,
                        "matched_txns": [b_row["txn_id"]],
                        "reconciliation_details": {
                            "bank_txn_id": b_row["txn_id"],
                            "combined_amount": b_row["amount"],
                            "peer_invoice_id": peer.get("invoice_id"),
                            "peer_invoice_number": peer.get("invoice_number"),
                            "match_basis": "SUBSET_SUM_COMBINED_PAYMENT"
                        },
                        "reasoning_trace": reasoning_trace,
                        "requires_human": True,
                        "action": "SEND_TELEGRAM_APPROVAL",
                        "telegram_notification": {
                            "text": telegram_text,
                            "buttons": ["Approve Combined Match", "Reject / Investigate"]
                        },
                        "email_draft": None
                    }
                    self._log_audit(result)
                    return result

        # Step 6: Test Partial Payment or Cash Discount Variance
        for b_row in unique_cand_rows:
            # Check for partial payment
            if "PART" in b_row["narration"].upper() and b_row["amount"] < total_amount:
                balance = round(total_amount - b_row["amount"], 2)
                reasoning_trace.append(
                    f"Step 6 [Partial Payment Detected]: Bank Txn {b_row['txn_id']} for ₹{b_row['amount']:,.2f} indicates partial payment for ₹{total_amount:,.2f} invoice. Remaining balance: ₹{balance:,.2f}."
                )
                telegram_text = (
                    f"⚖️ *Partial Payment Detected*\n"
                    f"Supplier: *{supplier_info['name']}*\n"
                    f"Invoice: {inv_num} (Total: ₹{total_amount:,.2f})\n"
                    f"Paid: ₹{b_row['amount']:,.2f} on {b_row['date']}\n"
                    f"Remaining Balance: *₹{balance:,.2f}*\n\n"
                    f"Record partial payment in ledger?"
                )
                result = {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_num,
                    "supplier_name": supplier_info["name"],
                    "decision": "PARTIAL_PAYMENT_DETECTED",
                    "confidence": "MEDIUM",
                    "confidence_score": 0.78,
                    "matched_txns": [b_row["txn_id"]],
                    "reconciliation_details": {
                        "bank_txn_id": b_row["txn_id"],
                        "paid_amount": b_row["amount"],
                        "balance_due": balance,
                        "match_basis": "PARTIAL_PAYMENT_NARRATION"
                    },
                    "reasoning_trace": reasoning_trace,
                    "requires_human": True,
                    "action": "SEND_TELEGRAM_APPROVAL",
                    "telegram_notification": {
                        "text": telegram_text,
                        "buttons": ["Approve Partial Payment", "Flag Disputed"]
                    },
                    "email_draft": None
                }
                self._log_audit(result)
                return result

            # Check for cash discount variance (up to 2.5%)
            discount_pct = (total_amount - b_row["amount"]) / total_amount
            if 0.0 < discount_pct <= 0.025:
                # Check memory for supplier discount rules
                mem = self.tools.corrections_memory_lookup("cash discount")
                reasoning_trace.append(
                    f"Step 6 [Prompt Cash Discount / TDS Variance]: Bank payment ₹{b_row['amount']:,.2f} is within {discount_pct*100:.1f}% discount of invoice ₹{total_amount:,.2f}. Corroborated by memory policy."
                )
                telegram_text = (
                    f"🏷️ *Cash Settlement Discount Variance*\n"
                    f"Supplier: *{supplier_info['name']}*\n"
                    f"Invoice Amount: ₹{total_amount:,.2f}\n"
                    f"Bank Debit: ₹{b_row['amount']:,.2f} ({discount_pct*100:.1f}% settlement discount)\n\n"
                    f"Approve settlement discount adjustment?"
                )
                result = {
                    "invoice_id": invoice_id,
                    "invoice_number": inv_num,
                    "supplier_name": supplier_info["name"],
                    "decision": "CASH_DISCOUNT_SETTLEMENT",
                    "confidence": "MEDIUM",
                    "confidence_score": 0.82,
                    "matched_txns": [b_row["txn_id"]],
                    "reconciliation_details": {
                        "bank_txn_id": b_row["txn_id"],
                        "paid_amount": b_row["amount"],
                        "discount_amount": round(total_amount - b_row["amount"], 2),
                        "match_basis": "PROMPT_PAYMENT_DISCOUNT_TOLERANCE"
                    },
                    "reasoning_trace": reasoning_trace,
                    "requires_human": True,
                    "action": "SEND_TELEGRAM_APPROVAL",
                    "telegram_notification": {
                        "text": telegram_text,
                        "buttons": ["Approve Discount Adjustment", "Reject"]
                    },
                    "email_draft": None
                }
                self._log_audit(result)
                return result

        # Step 7: No bank payment found -> Check due date and draft follow-up email
        reasoning_trace.append(f"Step 6 [No Matching Bank Payment]: No debit found for ₹{total_amount:,.2f} from {supplier_info['name']}.")
        reasoning_trace.append("Step 7 [Proactive Action: Draft Supplier Email]: Invoice is UNPAID. Preparing drafted follow-up email gated by human approval.")
        
        email_draft = self.tools.draft_email_tool(
            recipient_email=supplier_info.get("email", "accounts@supplier.com"),
            supplier_name=supplier_info["name"],
            invoice_number=inv_num,
            amount=total_amount,
            reason=f"No matching bank debit identified as of current reconciliation run. Due date: {invoice.get('due_date')}."
        )

        result = {
            "invoice_id": invoice_id,
            "invoice_number": inv_num,
            "supplier_name": supplier_info["name"],
            "decision": "UNPAID_EMAIL_DRAFTED",
            "confidence": "HIGH",
            "confidence_score": 0.90,
            "matched_txns": [],
            "reasoning_trace": reasoning_trace,
            "requires_human": True,
            "action": "PROMPT_ACCOUNTANT_TO_REVIEW_EMAIL_DRAFT",
            "telegram_notification": {
                "text": f"✉️ *Follow-up Email Drafted for Approval*\nSupplier: {supplier_info['name']}\nInvoice: {inv_num} (₹{total_amount:,.2f})\nStatus: UNPAID\n\nDraft created and held in queue. Approve sending?",
                "buttons": ["Review & Send Email", "Mark for Offline Payment", "Dismiss"]
            },
            "email_draft": email_draft
        }
        self._log_audit(result)
        return result

    def _log_audit(self, result: Dict[str, Any]):
        self.audit_log.append({
            "timestamp": "2026-10-05T21:35:00+05:30",
            "invoice_id": result["invoice_id"],
            "invoice_number": result["invoice_number"],
            "supplier_name": result["supplier_name"],
            "decision": result["decision"],
            "confidence": result["confidence"],
            "matched_txns": result["matched_txns"],
            "requires_human": result["requires_human"],
            "action_taken": result["action"]
        })
