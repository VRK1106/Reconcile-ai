"""
Agent Tools for Autonomous Invoice Reconciliation.
Implements the 5 tools described in invoice-agent-problem-solution-v2.md:
1. bank_row_search: Searches bank ledger by amount, date window, and narration query.
2. supplier_history_lookup: Retrieves supplier metadata, known aliases, and historical transactions.
3. invoice_list_lookup: Retrieves open/pending invoices for the supplier (enabling combined multi-invoice payment matching).
4. corrections_memory: Retrieves human-approved decisions from past edge cases as few-shot memory.
5. draft_email_tool: Drafts a supplier query/follow-up email gated by human approval.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class ReconciliationTools:
    def __init__(self, suppliers: List[Dict[str, Any]], bank_transactions: List[Dict[str, Any]], all_invoices: List[Dict[str, Any]]):
        self.suppliers = suppliers
        self.bank_transactions = bank_transactions
        self.all_invoices = all_invoices
        
        # Memory of past human corrections
        self.memory = [
            {
                "case_type": "alias_name_resolution",
                "pattern": "SHARMA TRDRS BLR",
                "resolved_to": "Sharma Trading Company",
                "supplier_id": "SUP001",
                "notes": "Approved by Suresh Bhat (Accountant) on 2026-08-15"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "POLYWIRES",
                "resolved_to": "Polycab Wires & Cables Ltd",
                "supplier_id": "SUP002",
                "notes": "Approved on 2026-08-20"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "HAVELLS KA",
                "resolved_to": "Havells India Limited",
                "supplier_id": "SUP003",
                "notes": "Approved on 2026-08-28"
            },
            {
                "case_type": "alias_name_resolution",
                "pattern": "SUPREME PLAST",
                "resolved_to": "Supreme Industries Ltd",
                "supplier_id": "SUP004",
                "notes": "Approved on 2026-08-30"
            },
            {
                "case_type": "cash_discount_tolerance",
                "pattern": "LESS 2PCT CASH DISC",
                "rule": "Allow up to 2.5% settlement discount if narration specifies cash discount or prompt payment",
                "supplier_id": "SUP009",
                "notes": "Godrej standard dealer prompt payment discount terms"
            }
        ]
        
        # Draft emails log (gated, never sent autonomously)
        self.drafted_emails: List[Dict[str, Any]] = []

    def supplier_history_lookup(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Looks up supplier by name, GSTIN, or alias.
        """
        q = query.strip().lower()
        for s in self.suppliers:
            if s["gstin"].lower() == q or s["name"].lower() == q:
                return s
            if any(alias.lower() in q or q in alias.lower() for alias in s.get("aliases", [])):
                return s
            if s["name"].lower() in q or q in s["name"].lower():
                return s
        return None

    def bank_row_search(
        self,
        target_amount: Optional[float] = None,
        date_center: Optional[str] = None,
        days_window: int = 45,
        narration_query: Optional[str] = None,
        amount_tolerance: float = 0.05
    ) -> List[Dict[str, Any]]:
        """
        Searches bank statement transactions by amount tolerance, date window, and optional narration query.
        """
        matches = []
        center_dt = None
        if date_center:
            try:
                center_dt = datetime.strptime(date_center, "%Y-%m-%d")
            except ValueError:
                pass

        for txn in self.bank_transactions:
            # 1. Date window check
            if center_dt:
                try:
                    txn_dt = datetime.strptime(txn["date"], "%Y-%m-%d")
                    diff_days = abs((txn_dt - center_dt).days)
                    if diff_days > days_window:
                        continue
                except ValueError:
                    pass

            # 2. Amount check
            amount_match = True
            if target_amount is not None:
                diff = abs(txn["amount"] - target_amount)
                amount_match = (diff <= (target_amount * amount_tolerance)) or (diff <= 1.0)

            # 3. Narration query check
            narration_match = True
            if narration_query:
                query_clean = narration_query.lower().strip()
                txn_narr = txn["narration"].lower()
                # Direct phrase match
                if query_clean in txn_narr:
                    narration_match = True
                else:
                    # Filter out generic stop words
                    GENERIC_STOP_WORDS = {"elec", "ltd", "india", "co", "trading", "and", "cables", "wires", "solutions", "industries", "company"}
                    q_words = [w for w in query_clean.replace("/", " ").replace("-", " ").split() if len(w) > 2 and w not in GENERIC_STOP_WORDS]
                    if q_words:
                        narration_match = any(w in txn_narr for w in q_words)
                    else:
                        narration_match = query_clean in txn_narr

            if target_amount is not None and narration_query is not None:
                if amount_match and narration_match:
                    matches.append(txn)
            elif target_amount is not None:
                if amount_match:
                    matches.append(txn)
            elif narration_query is not None:
                if narration_match:
                    matches.append(txn)
            else:
                matches.append(txn)

        return matches

    def invoice_list_lookup(self, supplier_gstin: str, exclude_invoice_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Finds open/pending invoices from the same supplier to check for combined payments.
        """
        return [
            inv for inv in self.all_invoices
            if inv.get("supplier_gstin") == supplier_gstin and inv.get("invoice_id") != exclude_invoice_id
        ]

    def corrections_memory_lookup(self, text: str) -> List[Dict[str, Any]]:
        """
        Retrieves matching past human corrections or alias approvals.
        """
        text_lower = text.lower()
        results = []
        for mem in self.memory:
            if mem["pattern"].lower() in text_lower or text_lower in mem["pattern"].lower():
                results.append(mem)
        return results

    def draft_email_tool(
        self,
        recipient_email: str,
        supplier_name: str,
        invoice_number: str,
        amount: float,
        reason: str
    ) -> Dict[str, Any]:
        """
        Prepares a drafted supplier follow-up email.
        CRITICAL SAFETY RULE: Never sends automatically. Gated with status 'PENDING_HUMAN_APPROVAL'.
        """
        draft = {
            "draft_id": f"DRAFT-{len(self.drafted_emails) + 1:03d}",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "to": recipient_email,
            "subject": f"Inquiry regarding Invoice {invoice_number} / Payment Status - Sri Krishna Electricals Manipal",
            "body": (
                f"Dear {supplier_name} Accounts Team,\n\n"
                f"We refer to Invoice No. {invoice_number} dated for ₹{amount:,.2f}.\n"
                f"Our automated reconciliation system noted the following query:\n"
                f"'{reason}'.\n\n"
                f"Could you please confirm the payment UTR / bank reference or provide an updated statement of account?\n\n"
                f"Warm regards,\n"
                f"Accounts Department\n"
                f"Sri Krishna Electricals & Hardware, Tiger Circle, Manipal - 576104\n"
                f"Phone: +91 98450 12345"
            ),
            "status": "PENDING_HUMAN_APPROVAL",
            "safety_gate": "HOLD_FOR_ACCOUNTANT_APPROVAL"
        }
        self.drafted_emails.append(draft)
        return draft
