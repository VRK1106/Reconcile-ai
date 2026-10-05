"""
Layer 2 Guardrails for Autonomous Invoice Reconciliation.
Deterministic rule-based checks that run before the AI agent.
Fails fast on:
- Invalid GSTIN format (Indian standard 15-character regex: 2 digits state + 10 chars PAN + 1 entity + 1 Z + 1 checksum)
- Tax arithmetic errors (subtotal + tax_amount != total_amount within 0.05 tolerance)
- Duplicate invoice detection (invoice_number + supplier_gstin already in ledger)
"""
import re
from typing import Dict, Any, Tuple, Optional, Set

# Indian GSTIN regex: e.g. 29AABCS1429B1Z2
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

class GuardrailManager:
    def __init__(self):
        # In-memory processed invoice registry (for duplicate detection)
        self.processed_invoice_keys: Set[str] = set()

    def register_processed_invoice(self, supplier_gstin: str, invoice_number: str):
        key = f"{supplier_gstin.strip().upper()}#{invoice_number.strip().upper()}"
        self.processed_invoice_keys.add(key)

    def validate_gstin(self, gstin: str) -> Tuple[bool, Optional[str]]:
        if not gstin or not isinstance(gstin, str):
            return False, "Missing or non-string GSTIN"
        gstin_clean = gstin.strip().upper()
        if len(gstin_clean) != 15:
            return False, f"Invalid GSTIN length {len(gstin_clean)} (expected 15 characters)"
        if not GSTIN_REGEX.match(gstin_clean):
            return False, f"GSTIN '{gstin_clean}' does not match standard Indian GSTIN format (State + PAN + Entity + Z + Checksum)"
        # Valid state code between 01 and 38 or 97/99
        state_code = int(gstin_clean[:2]) if gstin_clean[:2].isdigit() else -1
        if not (1 <= state_code <= 38 or state_code in [97, 99]):
            return False, f"Invalid Indian GST state code '{gstin_clean[:2]}'"
        return True, None

    def validate_tax_math(self, subtotal: float, tax_amount: float, total_amount: float) -> Tuple[bool, Optional[str]]:
        calculated = round(subtotal + tax_amount, 2)
        total = round(total_amount, 2)
        diff = abs(calculated - total)
        if diff > 0.05: # Allow small rounding tolerance of 5 paise
            return False, f"Tax arithmetic mismatch: Subtotal (₹{subtotal:,.2f}) + Tax (₹{tax_amount:,.2f}) = ₹{calculated:,.2f}, but Total is ₹{total:,.2f} (variance: ₹{diff:,.2f})"
        
        # Check against standard Indian GST slabs: 0%, 5%, 12%, 18%, 28% (within 0.75% tolerance for composition/rounding)
        if subtotal > 0:
            effective_rate = round(tax_amount / subtotal, 4)
            valid_slabs = [0.0, 0.05, 0.12, 0.18, 0.28]
            is_valid_slab = any(abs(effective_rate - slab) < 0.0075 for slab in valid_slabs)
            if not is_valid_slab:
                return False, f"Invalid GST rate slab: Effective tax rate is {effective_rate*100:.1f}%, which does not match any standard Indian GST slab (0%, 5%, 12%, 18%, 28%)"

        return True, None

    def check_duplicate(self, supplier_gstin: str, invoice_number: str) -> Tuple[bool, Optional[str]]:
        key = f"{supplier_gstin.strip().upper()}#{invoice_number.strip().upper()}"
        if key in self.processed_invoice_keys:
            return False, f"Duplicate invoice detected: Invoice '{invoice_number}' from GSTIN '{supplier_gstin}' was already processed"
        return True, None

    def run_all_guardrails(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes all deterministic Layer 2 guardrails.
        Returns a dict with passed status and list of violations.
        """
        violations = []

        # 1. Duplicate check
        dup_ok, dup_err = self.check_duplicate(invoice.get("supplier_gstin", ""), invoice.get("invoice_number", ""))
        if not dup_ok:
            violations.append({"type": "DUPLICATE_INVOICE", "message": dup_err})

        # 2. GSTIN check
        gst_ok, gst_err = self.validate_gstin(invoice.get("supplier_gstin", ""))
        if not gst_ok:
            violations.append({"type": "INVALID_GSTIN", "message": gst_err})

        # 3. Tax math check
        tax_ok, tax_err = self.validate_tax_math(
            float(invoice.get("subtotal", 0.0)),
            float(invoice.get("tax_amount", 0.0)),
            float(invoice.get("total_amount", 0.0))
        )
        if not tax_ok:
            violations.append({"type": "TAX_ARITHMETIC_MISMATCH", "message": tax_err})

        passed = len(violations) == 0
        return {
            "passed": passed,
            "violations": violations,
            "requires_human": not passed,
            "blocked_at": "LAYER_2_GUARDRAILS" if not passed else None
        }
