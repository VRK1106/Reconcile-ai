"""
Layer 2 Guardrail Service: Deterministic rule verification with zero AI drift.
Validates:
1. Indian GSTIN standard format (15 characters: State + PAN + Entity + Z + Checksum)
2. Tax arithmetic check (subtotal + tax == total within 0.05 tolerance)
3. Standard Indian GST slab adherence (0%, 5%, 12%, 18%, 28%)
4. Duplicate invoice detection (against persistent database table)
"""
import re
import time
from typing import Dict, Any, Tuple, Optional, List
import sqlite3
from backend.telemetry.prometheus import GUARDRAIL_VIOLATIONS_TOTAL

GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

class GuardrailService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def validate_gstin(self, gstin: str) -> Tuple[bool, Optional[str]]:
        if not gstin or not isinstance(gstin, str):
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="INVALID_GSTIN").inc()
            return False, "Missing or non-string GSTIN"
        g = gstin.strip().upper()
        if len(g) != 15:
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="INVALID_GSTIN").inc()
            return False, f"Invalid GSTIN length {len(g)} (expected 15 alphanumeric characters)"
        if not GSTIN_REGEX.match(g):
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="INVALID_GSTIN").inc()
            return False, f"GSTIN '{g}' violates Indian GST format (2-digit state + 10-char PAN + entity + Z + check digit)"
        state_code = int(g[:2]) if g[:2].isdigit() else -1
        if not (1 <= state_code <= 38 or state_code in [97, 99]):
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="INVALID_GSTIN").inc()
            return False, f"Invalid Indian GST state code '{g[:2]}'"
        return True, None

    def validate_tax_math(self, subtotal: float, tax_amount: float, total_amount: float) -> Tuple[bool, Optional[str]]:
        calc_total = round(subtotal + tax_amount, 2)
        total = round(total_amount, 2)
        diff = abs(calc_total - total)
        if diff > 0.05:
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="TAX_MATH_MISMATCH").inc()
            return False, f"Tax arithmetic mismatch: Subtotal (₹{subtotal:,.2f}) + Tax (₹{tax_amount:,.2f}) = ₹{calc_total:,.2f} != Total (₹{total:,.2f})"
        
        # Check standard GST slabs: 0%, 5%, 12%, 18%, 28%
        if subtotal > 0:
            rate = round(tax_amount / subtotal, 4)
            valid_slabs = [0.0, 0.05, 0.12, 0.18, 0.28]
            if not any(abs(rate - s) < 0.0075 for s in valid_slabs):
                GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="INVALID_GST_SLAB").inc()
                return False, f"Effective tax rate {rate*100:.1f}% does not match standard Indian GST slabs (0%, 5%, 12%, 18%, 28%)"

        return True, None

    def check_duplicate(self, gstin: str, invoice_number: str) -> Tuple[bool, Optional[str]]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT invoice_id FROM invoices 
            WHERE UPPER(TRIM(supplier_gstin)) = ? AND UPPER(TRIM(invoice_number)) = ?
        """, (gstin.strip().upper(), invoice_number.strip().upper()))
        row = cur.fetchone()
        if row:
            GUARDRAIL_VIOLATIONS_TOTAL.labels(rule_type="DUPLICATE_INVOICE").inc()
            return False, f"Duplicate invoice detected: Invoice '{invoice_number}' from GSTIN '{gstin}' is already recorded (ID: {row['invoice_id']})"
        return True, None

    def execute_guardrails(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter()
        violations: List[str] = []

        # 1. Duplicate check
        dup_ok, dup_err = self.check_duplicate(
            invoice_data.get("supplier_gstin", ""),
            invoice_data.get("invoice_number", "")
        )
        if not dup_ok and dup_err:
            violations.append(dup_err)

        # 2. GSTIN format check
        gst_ok, gst_err = self.validate_gstin(invoice_data.get("supplier_gstin", ""))
        if not gst_ok and gst_err:
            violations.append(gst_err)

        # 3. Tax math check
        tax_ok, tax_err = self.validate_tax_math(
            float(invoice_data.get("subtotal", 0.0)),
            float(invoice_data.get("tax_amount", 0.0)),
            float(invoice_data.get("total_amount", 0.0))
        )
        if not tax_ok and tax_err:
            violations.append(tax_err)

        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        passed = len(violations) == 0

        return {
            "passed": passed,
            "violations": violations,
            "duration_ms": duration_ms,
            "blocked_at": None if passed else "LAYER_2_GUARDRAILS"
        }
