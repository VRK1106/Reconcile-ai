"""
Generates realistic test dataset for Sri Krishna Electricals & Hardware, Manipal.
Includes:
- 10 suppliers with GSTINs and known bank narration aliases
- 25 invoices covering clean cases, ambiguous cases, guardrail failures, and edge cases
- 30 bank statement entries from Canara Bank / HDFC Bank Manipal branch
- Ground truth answer key for benchmarking
"""
import json
import csv
import os

SUPPLIERS = [
    {
        "supplier_id": "SUP001",
        "name": "Sharma Trading Company",
        "gstin": "29AABCS1429B1Z2",
        "aliases": ["SHARMA TRDRS", "SHARMA TRADING", "SHARMA TRDRS BLR", "SHARMA TRAD CO"],
        "email": "accounts@sharmatrading.in",
        "phone": "+91 98450 11223",
        "city": "Bengaluru",
        "category": "Switches & Wiring Accessories"
    },
    {
        "supplier_id": "SUP002",
        "name": "Polycab Wires & Cables Ltd",
        "gstin": "29AAACP2194D1ZK",
        "aliases": ["POLYCAB WIRES", "POLYWIRES", "POLYCAB INDIA", "POLYCAB LTD"],
        "email": "billing.south@polycab.com",
        "phone": "+91 98451 22334",
        "city": "Bengaluru",
        "category": "Wires & Industrial Cables"
    },
    {
        "supplier_id": "SUP003",
        "name": "Havells India Limited",
        "gstin": "29AAACH1820F1ZX",
        "aliases": ["HAVELLS IND", "HAVELLS INDIA LTD", "HAVELLS KA"],
        "email": "support.karnataka@havells.com",
        "phone": "+91 98452 33445",
        "city": "Mangaluru",
        "category": "Fans, Lighting & Circuit Breakers"
    },
    {
        "supplier_id": "SUP004",
        "name": "Supreme Industries Ltd",
        "gstin": "29AAACS6328P1Z8",
        "aliases": ["SUPREME IND", "SUPREME PIPES", "SUPREME PLAST"],
        "email": "pipes.sales@supreme.co.in",
        "phone": "+91 98453 44556",
        "city": "Udupi",
        "category": "PVC Pipes & Plumbing Fittings"
    },
    {
        "supplier_id": "SUP005",
        "name": "Asian Paints Limited",
        "gstin": "29AAACA2155H1ZV",
        "aliases": ["ASIAN PAINTS", "ASIAN PAINTS LTD", "APL BLR DEPOT"],
        "email": "dealer.desk@asianpaints.com",
        "phone": "+91 98454 55667",
        "city": "Mangaluru",
        "category": "Paints, Primers & Waterproofing"
    },
    {
        "supplier_id": "SUP006",
        "name": "Finolex Cables Ltd",
        "gstin": "29AAACF1234L1ZN",
        "aliases": ["FINOLEX CABLES", "FINOLEX", "FINO CABLE BLR"],
        "email": "customercare@finolex.com",
        "phone": "+91 98455 66778",
        "city": "Bengaluru",
        "category": "Cables & Conduit Pipes"
    },
    {
        "supplier_id": "SUP007",
        "name": "Anchor by Panasonic",
        "gstin": "29AAACA9981K1ZM",
        "aliases": ["ANCHOR ELEC", "PANASONIC ANCHOR", "ANCHOR BY PANASONIC"],
        "email": "order.in@anchor-world.com",
        "phone": "+91 98456 77889",
        "city": "Hubballi",
        "category": "Modular Switches & Sockets"
    },
    {
        "supplier_id": "SUP008",
        "name": "Schneider Electric India",
        "gstin": "29AAACS7766M1Z5",
        "aliases": ["SCHNEIDER ELEC", "SCHNEIDER IND", "SCHNEIDER"],
        "email": "in.orders@se.com",
        "phone": "+91 98457 88990",
        "city": "Bengaluru",
        "category": "MCB & Distribution Boards"
    },
    {
        "supplier_id": "SUP009",
        "name": "Godrej Locking Solutions",
        "gstin": "29AAACG4411C1ZY",
        "aliases": ["GODREJ LOCKS", "GODREJ AND BOYCE", "GODREJ HARDWARE"],
        "email": "locks.care@godrej.com",
        "phone": "+91 98458 99001",
        "city": "Mangaluru",
        "category": "Door Hardware & Locks"
    },
    {
        "supplier_id": "SUP010",
        "name": "Mangalore Tools & Fasteners",
        "gstin": "29AABCM5522E1Z3",
        "aliases": ["MLORE TOOLS", "MANGALORE FASTENERS", "MANGALORE TOOLS"],
        "email": "sales@mtoolskarnataka.com",
        "phone": "+91 98459 00112",
        "city": "Mangaluru",
        "category": "Power Tools & Drill Bits"
    }
]

# 25 Invoices designed with real Indian GST, varied dates (Sept-Oct 2026), and clear difficulty levels
INVOICES = [
    # 1. Clean Match 1
    {
        "invoice_id": "INV-101",
        "supplier_name": "Sharma Trading Company",
        "supplier_gstin": "29AABCS1429B1Z2",
        "invoice_number": "STC/26/1041",
        "invoice_date": "2026-09-02",
        "subtotal": 15000.00,
        "tax_amount": 2700.00, # 18% GST
        "total_amount": 17700.00,
        "due_date": "2026-10-02",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Standard clean single invoice matching bank payment"
    },
    # 2. Clean Match 2
    {
        "invoice_id": "INV-102",
        "supplier_name": "Polycab Wires & Cables Ltd",
        "supplier_gstin": "29AAACP2194D1ZK",
        "invoice_number": "POL-98214",
        "invoice_date": "2026-09-04",
        "subtotal": 35000.00,
        "tax_amount": 6300.00, # 18%
        "total_amount": 41300.00,
        "due_date": "2026-10-04",
        "source": "telegram",
        "case_type": "clean_single_match",
        "description": "Clean match from Telegram photo upload"
    },
    # 3. Clean Match 3
    {
        "invoice_id": "INV-103",
        "supplier_name": "Havells India Limited",
        "supplier_gstin": "29AAACH1820F1ZX",
        "invoice_number": "HAV-KA-4412",
        "invoice_date": "2026-09-05",
        "subtotal": 22000.00,
        "tax_amount": 3960.00, # 18%
        "total_amount": 25960.00,
        "due_date": "2026-10-05",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match Havells circuit breakers"
    },
    # 4. Clean Match 4
    {
        "invoice_id": "INV-104",
        "supplier_name": "Supreme Industries Ltd",
        "supplier_gstin": "29AAACS6328P1Z8",
        "invoice_number": "SUP-UD-0911",
        "invoice_date": "2026-09-06",
        "subtotal": 18500.00,
        "tax_amount": 3330.00, # 18%
        "total_amount": 21830.00,
        "due_date": "2026-10-06",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match Supreme PVC pipes"
    },
    # 5. Clean Match 5
    {
        "invoice_id": "INV-105",
        "supplier_name": "Asian Paints Limited",
        "supplier_gstin": "29AAACA2155H1ZV",
        "invoice_number": "APL-MNG-771",
        "invoice_date": "2026-09-08",
        "subtotal": 52000.00,
        "tax_amount": 14560.00, # 28% GST
        "total_amount": 66560.00,
        "due_date": "2026-10-08",
        "source": "telegram",
        "case_type": "clean_single_match",
        "description": "Clean match paints with 28% GST"
    },
    # 6. Clean Match 6
    {
        "invoice_id": "INV-106",
        "supplier_name": "Finolex Cables Ltd",
        "supplier_gstin": "29AAACF1234L1ZN",
        "invoice_number": "FIN-00921",
        "invoice_date": "2026-09-10",
        "subtotal": 12400.00,
        "tax_amount": 2232.00, # 18%
        "total_amount": 14632.00,
        "due_date": "2026-10-10",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match Finolex flexible wires"
    },
    # 7. Clean Match 7
    {
        "invoice_id": "INV-107",
        "supplier_name": "Anchor by Panasonic",
        "supplier_gstin": "29AAACA9981K1ZM",
        "invoice_number": "ANC-HB-3012",
        "invoice_date": "2026-09-11",
        "subtotal": 8900.00,
        "tax_amount": 1602.00, # 18%
        "total_amount": 10502.00,
        "due_date": "2026-10-11",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match modular switches"
    },
    # 8. Clean Match 8
    {
        "invoice_id": "INV-108",
        "supplier_name": "Schneider Electric India",
        "supplier_gstin": "29AAACS7766M1Z5",
        "invoice_number": "SEI-BLR-5541",
        "invoice_date": "2026-09-12",
        "subtotal": 31000.00,
        "tax_amount": 5580.00, # 18%
        "total_amount": 36580.00,
        "due_date": "2026-10-12",
        "source": "telegram",
        "case_type": "clean_single_match",
        "description": "Clean match Schneider distribution boards"
    },
    # 9. Clean Match 9
    {
        "invoice_id": "INV-109",
        "supplier_name": "Godrej Locking Solutions",
        "supplier_gstin": "29AAACG4411C1ZY",
        "invoice_number": "GLS-26-8801",
        "invoice_date": "2026-09-13",
        "subtotal": 14200.00,
        "tax_amount": 2556.00, # 18%
        "total_amount": 16756.00,
        "due_date": "2026-10-13",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match Godrej mortise locks"
    },
    # 10. Clean Match 10
    {
        "invoice_id": "INV-110",
        "supplier_name": "Mangalore Tools & Fasteners",
        "supplier_gstin": "29AABCM5522E1Z3",
        "invoice_number": "MTF-0492",
        "invoice_date": "2026-09-14",
        "subtotal": 7800.00,
        "tax_amount": 1404.00, # 18%
        "total_amount": 9204.00,
        "due_date": "2026-10-14",
        "source": "email",
        "case_type": "clean_single_match",
        "description": "Clean match drill bits & masonry anchors"
    },

    # --- AMBIGUOUS CASE 1: Supplier Name Variant (The famous "Sharma Traders" vs "SHARMA TRDRS BLR")
    {
        "invoice_id": "INV-111",
        "supplier_name": "Sharma Trading Company",
        "supplier_gstin": "29AABCS1429B1Z2",
        "invoice_number": "STC/26/1088",
        "invoice_date": "2026-09-15",
        "subtotal": 24000.00,
        "tax_amount": 4320.00,
        "total_amount": 28320.00,
        "due_date": "2026-10-15",
        "source": "telegram",
        "case_type": "ambiguous_name_variant",
        "description": "Bank row has narration 'NEFT/SHARMA TRDRS BLR/AXIS00091' with no exact match on 'Sharma Trading Company'"
    },

    # --- AMBIGUOUS CASE 2: Supplier Name Variant 2 (Polycab -> "POLYWIRES UDUPI")
    {
        "invoice_id": "INV-112",
        "supplier_name": "Polycab Wires & Cables Ltd",
        "supplier_gstin": "29AAACP2194D1ZK",
        "invoice_number": "POL-99042",
        "invoice_date": "2026-09-16",
        "subtotal": 19500.00,
        "tax_amount": 3510.00,
        "total_amount": 23010.00,
        "due_date": "2026-10-16",
        "source": "email",
        "case_type": "ambiguous_name_variant",
        "description": "Bank row narration says 'RTGS/POLYWIRES/CBIN0280' instead of full company name"
    },

    # --- AMBIGUOUS CASE 3: Supplier Name Variant 3 (Havells -> "HAVELLS KA")
    {
        "invoice_id": "INV-113",
        "supplier_name": "Havells India Limited",
        "supplier_gstin": "29AAACH1820F1ZX",
        "invoice_number": "HAV-KA-4520",
        "invoice_date": "2026-09-17",
        "subtotal": 38000.00,
        "tax_amount": 6840.00,
        "total_amount": 44840.00,
        "due_date": "2026-10-17",
        "source": "email",
        "case_type": "ambiguous_name_variant",
        "description": "Bank row narration says 'HAVELLS KA CLG CHQ 7712' matching alias"
    },

    # --- AMBIGUOUS CASE 4: Supplier Name Variant 4 (Supreme Industries -> "SUPREME PLAST")
    {
        "invoice_id": "INV-114",
        "supplier_name": "Supreme Industries Ltd",
        "supplier_gstin": "29AAACS6328P1Z8",
        "invoice_number": "SUP-UD-0988",
        "invoice_date": "2026-09-18",
        "subtotal": 16000.00,
        "tax_amount": 2880.00,
        "total_amount": 18880.00,
        "due_date": "2026-10-18",
        "source": "telegram",
        "case_type": "ambiguous_name_variant",
        "description": "Bank row narration says 'NEFT/SUPREME PLAST/HDFC0012'"
    },

    # --- AMBIGUOUS CASE 5 & 6: Combined Multi-Invoice Payment (1 Bank row covers 2 Invoices)
    # Bank row has 47,200 covering INV-1042 (28,000) and INV-1043 (19,200) from Sharma Traders!
    {
        "invoice_id": "INV-115",
        "supplier_name": "Sharma Trading Company",
        "supplier_gstin": "29AABCS1429B1Z2",
        "invoice_number": "STC/26/1042",
        "invoice_date": "2026-09-19",
        "subtotal": 23728.81,
        "tax_amount": 4271.19,
        "total_amount": 28000.00,
        "due_date": "2026-10-19",
        "source": "email",
        "case_type": "ambiguous_combined_payment",
        "description": "Part 1 of combined payment: Rs 28,000"
    },
    {
        "invoice_id": "INV-116",
        "supplier_name": "Sharma Trading Company",
        "supplier_gstin": "29AABCS1429B1Z2",
        "invoice_number": "STC/26/1043",
        "invoice_date": "2026-09-19",
        "subtotal": 16271.19,
        "tax_amount": 2928.81,
        "total_amount": 19200.00,
        "due_date": "2026-10-19",
        "source": "email",
        "case_type": "ambiguous_combined_payment",
        "description": "Part 2 of combined payment: Rs 19,200 (Total in Bank = 47,200)"
    },

    # --- AMBIGUOUS CASE 7: Combined Multi-Invoice Payment for Asian Paints
    # Bank row has 85,000 covering INV-117 (50,000) and INV-118 (35,000)
    {
        "invoice_id": "INV-117",
        "supplier_name": "Asian Paints Limited",
        "supplier_gstin": "29AAACA2155H1ZV",
        "invoice_number": "APL-MNG-801",
        "invoice_date": "2026-09-20",
        "subtotal": 39062.50,
        "tax_amount": 10937.50, # 28%
        "total_amount": 50000.00,
        "due_date": "2026-10-20",
        "source": "email",
        "case_type": "ambiguous_combined_payment",
        "description": "Part of Rs 85,000 combined payment for Asian Paints"
    },
    {
        "invoice_id": "INV-118",
        "supplier_name": "Asian Paints Limited",
        "supplier_gstin": "29AAACA2155H1ZV",
        "invoice_number": "APL-MNG-802",
        "invoice_date": "2026-09-20",
        "subtotal": 27343.75,
        "tax_amount": 7656.25, # 28%
        "total_amount": 35000.00,
        "due_date": "2026-10-20",
        "source": "email",
        "case_type": "ambiguous_combined_payment",
        "description": "Second part of Rs 85,000 combined payment for Asian Paints"
    },

    # --- AMBIGUOUS CASE 8: Partial Payment
    # Invoice is Rs 50,000, bank shows payment of Rs 30,000 with narration "PART PYMT ANCHOR ELEC"
    {
        "invoice_id": "INV-119",
        "supplier_name": "Anchor by Panasonic",
        "supplier_gstin": "29AAACA9981K1ZM",
        "invoice_number": "ANC-HB-3199",
        "invoice_date": "2026-09-21",
        "subtotal": 42372.88,
        "tax_amount": 7627.12,
        "total_amount": 50000.00,
        "due_date": "2026-10-21",
        "source": "email",
        "case_type": "ambiguous_partial_payment",
        "description": "Invoice 50,000 with partial bank payment of 30,000 (balance 20,000 due)"
    },

    # --- AMBIGUOUS CASE 9: Small Rounding / Cash Discount Difference (TDS / 2% cash discount)
    # Invoice is Rs 25,000, but payment is Rs 24,500 (2% prompt discount)
    {
        "invoice_id": "INV-120",
        "supplier_name": "Godrej Locking Solutions",
        "supplier_gstin": "29AAACG4411C1ZY",
        "invoice_number": "GLS-26-8910",
        "invoice_date": "2026-09-22",
        "subtotal": 21186.44,
        "tax_amount": 3813.56,
        "total_amount": 25000.00,
        "due_date": "2026-10-22",
        "source": "email",
        "case_type": "ambiguous_discount_difference",
        "description": "2% cash settlement discount: Invoice Rs 25,000 vs Bank Rs 24,500"
    },

    # --- GUARDRAIL FAILURE 1: Exact Duplicate Invoice
    {
        "invoice_id": "INV-121",
        "supplier_name": "Sharma Trading Company",
        "supplier_gstin": "29AABCS1429B1Z2",
        "invoice_number": "STC/26/1041", # Exact duplicate of INV-101
        "invoice_date": "2026-09-02",
        "subtotal": 15000.00,
        "tax_amount": 2700.00,
        "total_amount": 17700.00,
        "due_date": "2026-10-02",
        "source": "telegram",
        "case_type": "guardrail_exact_duplicate",
        "description": "Exact duplicate submission of INV-101 forwarded via Telegram"
    },

    # --- GUARDRAIL FAILURE 2: Invalid GSTIN Format
    {
        "invoice_id": "INV-122",
        "supplier_name": "Local Wire Mart",
        "supplier_gstin": "29INVALID12345", # Bad GSTIN format (length 14, invalid regex)
        "invoice_number": "LWM-0012",
        "invoice_date": "2026-09-24",
        "subtotal": 10000.00,
        "tax_amount": 1800.00,
        "total_amount": 11800.00,
        "due_date": "2026-10-24",
        "source": "email",
        "case_type": "guardrail_invalid_gstin",
        "description": "Invalid GSTIN format violating Indian 15-char alphanumeric check"
    },

    # --- GUARDRAIL FAILURE 3: Tax Arithmetic Mismatch
    {
        "invoice_id": "INV-123",
        "supplier_name": "Finolex Cables Ltd",
        "supplier_gstin": "29AAACF1234L1ZN",
        "invoice_number": "FIN-00999",
        "invoice_date": "2026-09-25",
        "subtotal": 20000.00,
        "tax_amount": 1200.00, # Incorrect: 18% of 20,000 should be 3,600, not 1,200!
        "total_amount": 21200.00, # Mismatch
        "due_date": "2026-10-25",
        "source": "email",
        "case_type": "guardrail_tax_arithmetic_mismatch",
        "description": "Tax arithmetic mismatch (6% charged instead of standard 18% slab)"
    },

    # --- UNPAID / DISPUTED CASE: Missing Bank Payment -> Trigger Draft Follow-up Email
    {
        "invoice_id": "INV-124",
        "supplier_name": "Schneider Electric India",
        "supplier_gstin": "29AAACS7766M1Z5",
        "invoice_number": "SEI-BLR-5890",
        "invoice_date": "2026-09-26",
        "subtotal": 65000.00,
        "tax_amount": 11700.00,
        "total_amount": 76700.00,
        "due_date": "2026-10-15",
        "source": "email",
        "case_type": "unpaid_due_soon",
        "description": "No bank payment found, due in 10 days, agent drafts payment voucher / query"
    },

    # --- LOW CONFIDENCE CASE: Blurry Extraction / Unknown Vendor
    {
        "invoice_id": "INV-125",
        "supplier_name": "Unknown Crushed Stone Supplier",
        "supplier_gstin": "29AABCU0000Z1ZZ",
        "invoice_number": "UNKNOWN-99",
        "invoice_date": "2026-09-27",
        "subtotal": 11500.00,
        "tax_amount": 575.00,
        "total_amount": 12075.00,
        "due_date": "2026-10-27",
        "source": "telegram",
        "case_type": "low_confidence_unrecognized",
        "description": "Unregistered supplier with blurry photo, low confidence extraction"
    }
]

# Bank Statement: 30 transactions from Canara Bank / HDFC Bank Manipal Branch (Account: 0182101009844)
BANK_STATEMENT = [
    {"txn_id": "TXN-20260902-01", "date": "2026-09-03", "type": "DEBIT", "amount": 17700.00, "narration": "NEFT/SHARMA TRADING COMPANY/CANB000182/INV1041", "ref_no": "UTR-CNB0903001"},
    {"txn_id": "TXN-20260904-02", "date": "2026-09-05", "type": "DEBIT", "amount": 41300.00, "narration": "RTGS/POLYCAB WIRES AND CABLES/HDFC000021/POL98214", "ref_no": "UTR-HDF0905002"},
    {"txn_id": "TXN-20260905-03", "date": "2026-09-06", "type": "DEBIT", "amount": 25960.00, "narration": "NEFT/HAVELLS INDIA LIMITED/YESB000014/HAV4412", "ref_no": "UTR-YES0906003"},
    {"txn_id": "TXN-20260906-04", "date": "2026-09-07", "type": "DEBIT", "amount": 21830.00, "narration": "IMPS/SUPREME INDUSTRIES LTD/PUNB0021/0911", "ref_no": "UTR-PUN0907004"},
    {"txn_id": "TXN-20260908-05", "date": "2026-09-09", "type": "DEBIT", "amount": 66560.00, "narration": "RTGS/ASIAN PAINTS LIMITED/SBIN000412/771", "ref_no": "UTR-SBI0909005"},
    {"txn_id": "TXN-20260910-06", "date": "2026-09-11", "type": "DEBIT", "amount": 14632.00, "narration": "NEFT/FINOLEX CABLES LTD/ICIC000091/00921", "ref_no": "UTR-ICI0911006"},
    {"txn_id": "TXN-20260911-07", "date": "2026-09-12", "type": "DEBIT", "amount": 10502.00, "narration": "UPI/ANCHOR BY PANASONIC/KKBK00011/3012", "ref_no": "UTR-KKB0912007"},
    {"txn_id": "TXN-20260912-08", "date": "2026-09-13", "type": "DEBIT", "amount": 36580.00, "narration": "RTGS/SCHNEIDER ELECTRIC INDIA/AXIS0009/5541", "ref_no": "UTR-AXI0913008"},
    {"txn_id": "TXN-20260913-09", "date": "2026-09-14", "type": "DEBIT", "amount": 16756.00, "narration": "NEFT/GODREJ LOCKING SOLUTIONS/CORP0001/8801", "ref_no": "UTR-COR0914009"},
    {"txn_id": "TXN-20260914-10", "date": "2026-09-15", "type": "DEBIT", "amount": 9204.00, "narration": "IMPS/MANGALORE TOOLS & FASTENERS/SYNB001/0492", "ref_no": "UTR-SYN0915010"},

    # Bank row with alias "SHARMA TRDRS BLR" for INV-111 (Rs 28,320)
    {"txn_id": "TXN-20260916-11", "date": "2026-09-17", "type": "DEBIT", "amount": 28320.00, "narration": "NEFT/SHARMA TRDRS BLR/AXIS00091/SETTL", "ref_no": "UTR-AXI0917011"},

    # Bank row with alias "POLYWIRES" for INV-112 (Rs 23,010)
    {"txn_id": "TXN-20260917-12", "date": "2026-09-18", "type": "DEBIT", "amount": 23010.00, "narration": "RTGS/POLYWIRES/CBIN0280/WIREPYMT", "ref_no": "UTR-CBI0918012"},

    # Bank row with alias "HAVELLS KA" for INV-113 (Rs 44,840)
    {"txn_id": "TXN-20260918-13", "date": "2026-09-19", "type": "DEBIT", "amount": 44840.00, "narration": "HAVELLS KA CLG CHQ 7712/MANIPAL BR", "ref_no": "UTR-CHQ0919013"},

    # Bank row with alias "SUPREME PLAST" for INV-114 (Rs 18,880)
    {"txn_id": "TXN-20260919-14", "date": "2026-09-20", "type": "DEBIT", "amount": 18880.00, "narration": "NEFT/SUPREME PLAST/HDFC0012/FITTINGS", "ref_no": "UTR-HDF0920014"},

    # Combined payment for INV-115 (28,000) + INV-116 (19,200) = Rs 47,200!
    {"txn_id": "TXN-20260920-15", "date": "2026-09-21", "type": "DEBIT", "amount": 47200.00, "narration": "RTGS/SHARMA TRDRS/AXIS00091/BULK STC1042-43", "ref_no": "UTR-AXI0921015"},

    # Combined payment for INV-117 (50,000) + INV-118 (35,000) = Rs 85,000!
    {"txn_id": "TXN-20260921-16", "date": "2026-09-22", "type": "DEBIT", "amount": 85000.00, "narration": "RTGS/APL BLR DEPOT/SBIN000412/CONSOLIDATED", "ref_no": "UTR-SBI0922016"},

    # Partial payment for INV-119 (50,000 invoice, 30,000 paid)
    {"txn_id": "TXN-20260922-17", "date": "2026-09-23", "type": "DEBIT", "amount": 30000.00, "narration": "NEFT/ANCHOR ELEC/KKBK00011/PART PYMT 3199", "ref_no": "UTR-KKB0923017"},

    # Discounted payment for INV-120 (Rs 24,500 vs 25,000)
    {"txn_id": "TXN-20260923-18", "date": "2026-09-24", "type": "DEBIT", "amount": 24500.00, "narration": "NEFT/GODREJ LOCKS/CORP0001/LESS 2PCT CASH DISC", "ref_no": "UTR-COR0924018"},

    # Other routine shop expenses (not matching supplier invoices)
    {"txn_id": "TXN-20260925-19", "date": "2026-09-25", "type": "DEBIT", "amount": 15000.00, "narration": "CHQ WDL/SHOP RENT TIGER CIRCLE/SRI KRISHNA COMPLEX", "ref_no": "UTR-CHQ0925019"},
    {"txn_id": "TXN-20260926-20", "date": "2026-09-26", "type": "DEBIT", "amount": 4200.00, "narration": "MESCOM ELECTRICITY BILL/MANIPAL SUBDIV", "ref_no": "UTR-MES0926020"},
    {"txn_id": "TXN-20260927-21", "date": "2026-09-27", "type": "DEBIT", "amount": 3500.00, "narration": "STAFF TEA AND LUNCH ALLOWANCE/CASH", "ref_no": "UTR-CSH0927021"},
    {"txn_id": "TXN-20260928-22", "date": "2026-09-28", "type": "DEBIT", "amount": 50000.00, "narration": "TRANSFER TO CURRENT ACC OVERDRAFT", "ref_no": "UTR-TRF0928022"}
]

# Ground Truth Answer Key
GROUND_TRUTH = {
    "INV-101": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260902-01"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 17700 and narration match"
    },
    "INV-102": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260904-02"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 41300 and invoice number in narration"
    },
    "INV-103": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260905-03"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 25960"
    },
    "INV-104": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260906-04"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 21830"
    },
    "INV-105": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260908-05"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 66560"
    },
    "INV-106": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260910-06"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 14632"
    },
    "INV-107": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260911-07"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 10502"
    },
    "INV-108": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260912-08"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 36580"
    },
    "INV-109": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260913-09"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 16756"
    },
    "INV-110": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260914-10"],
        "reconciliation_type": "EXACT_SINGLE_MATCH",
        "requires_human": False,
        "expected_action": "Write to ledger, mark PAID",
        "notes": "Exact amount 9204"
    },
    "INV-111": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260916-11"],
        "reconciliation_type": "ALIAS_NAME_MATCH",
        "requires_human": False,
        "expected_action": "Matched via known alias 'SHARMA TRDRS BLR', auto-resolved",
        "notes": "Agent resolves via supplier alias memory"
    },
    "INV-112": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260917-12"],
        "reconciliation_type": "ALIAS_NAME_MATCH",
        "requires_human": False,
        "expected_action": "Matched via known alias 'POLYWIRES', auto-resolved",
        "notes": "Resolved via supplier alias memory"
    },
    "INV-113": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260918-13"],
        "reconciliation_type": "ALIAS_NAME_MATCH",
        "requires_human": False,
        "expected_action": "Matched via known alias 'HAVELLS KA', auto-resolved",
        "notes": "Resolved via cheque narration alias"
    },
    "INV-114": {
        "status": "AUTO_RESOLVED",
        "confidence": "HIGH",
        "matched_txns": ["TXN-20260919-14"],
        "reconciliation_type": "ALIAS_NAME_MATCH",
        "requires_human": False,
        "expected_action": "Matched via known alias 'SUPREME PLAST', auto-resolved",
        "notes": "Resolved via alias memory"
    },
    "INV-115": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260920-15"],
        "reconciliation_type": "COMBINED_PAYMENT_MATCH",
        "requires_human": True,
        "expected_action": "Send Telegram approval prompt for combined Rs 47,200 payment covering INV-115 + INV-116",
        "notes": "Subset sum tool identified 28,000 + 19,200 = 47,200"
    },
    "INV-116": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260920-15"],
        "reconciliation_type": "COMBINED_PAYMENT_MATCH",
        "requires_human": True,
        "expected_action": "Send Telegram approval prompt for combined Rs 47,200 payment covering INV-115 + INV-116",
        "notes": "Subset sum tool identified 28,000 + 19,200 = 47,200"
    },
    "INV-117": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260921-16"],
        "reconciliation_type": "COMBINED_PAYMENT_MATCH",
        "requires_human": True,
        "expected_action": "Send Telegram approval prompt for combined Rs 85,000 covering INV-117 + INV-118",
        "notes": "50,000 + 35,000 = 85,000"
    },
    "INV-118": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260921-16"],
        "reconciliation_type": "COMBINED_PAYMENT_MATCH",
        "requires_human": True,
        "expected_action": "Send Telegram approval prompt for combined Rs 85,000 covering INV-117 + INV-118",
        "notes": "50,000 + 35,000 = 85,000"
    },
    "INV-119": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260922-17"],
        "reconciliation_type": "PARTIAL_PAYMENT_MATCH",
        "requires_human": True,
        "expected_action": "Prompt accountant on Telegram: Rs 30,000 paid against Rs 50,000 invoice (balance 20,000 due)",
        "notes": "Narration confirms 'PART PYMT'"
    },
    "INV-120": {
        "status": "TELEGRAM_APPROVAL",
        "confidence": "MEDIUM",
        "matched_txns": ["TXN-20260923-18"],
        "reconciliation_type": "CASH_DISCOUNT_MATCH",
        "requires_human": True,
        "expected_action": "Prompt accountant: Rs 24,500 paid for Rs 25,000 invoice (2% discount/TDS variance)",
        "notes": "Variance within 2% cash discount threshold"
    },
    "INV-121": {
        "status": "GUARDRAIL_BLOCKED",
        "confidence": "ZERO",
        "matched_txns": [],
        "reconciliation_type": "DUPLICATE_DETECTED",
        "requires_human": True,
        "expected_action": "Guardrail Layer 2 stops execution before agent: duplicate of INV-101",
        "notes": "Exact hash and invoice number duplicate caught"
    },
    "INV-122": {
        "status": "GUARDRAIL_BLOCKED",
        "confidence": "ZERO",
        "matched_txns": [],
        "reconciliation_type": "INVALID_GSTIN_FORMAT",
        "requires_human": True,
        "expected_action": "Guardrail Layer 2 rejects: GSTIN format fails regex check",
        "notes": "No AI call made, deterministic fail"
    },
    "INV-123": {
        "status": "GUARDRAIL_BLOCKED",
        "confidence": "ZERO",
        "matched_txns": [],
        "reconciliation_type": "TAX_ARITHMETIC_ERROR",
        "requires_human": True,
        "expected_action": "Guardrail Layer 2 rejects: subtotal + tax != total",
        "notes": "Tax math 20000 + 1200 != 21200 with standard 18% slab"
    },
    "INV-124": {
        "status": "ESCALATED_UNPAID",
        "confidence": "HIGH",
        "matched_txns": [],
        "reconciliation_type": "UNPAID_DRAFT_EMAIL",
        "requires_human": True,
        "expected_action": "Draft supplier follow-up email / payment voucher for Rs 76,700, hold for approval",
        "notes": "Gated action: email draft created, never sent autonomously"
    },
    "INV-125": {
        "status": "ESCALATED_LOW_CONFIDENCE",
        "confidence": "LOW",
        "matched_txns": [],
        "reconciliation_type": "UNRECOGNIZED_SUPPLIER",
        "requires_human": True,
        "expected_action": "Escalate to accountant with summary of checks performed and reasons",
        "notes": "Supplier not found, blurry extraction"
    }
}

def main():
    os.makedirs("data", exist_ok=True)
    with open("data/suppliers.json", "w", encoding="utf-8") as f:
        json.dump(SUPPLIERS, f, indent=2)
    print("Saved data/suppliers.json (10 suppliers)")

    with open("data/invoices.json", "w", encoding="utf-8") as f:
        json.dump(INVOICES, f, indent=2)
    print("Saved data/invoices.json (25 invoices)")

    with open("data/bank_statement.json", "w", encoding="utf-8") as f:
        json.dump(BANK_STATEMENT, f, indent=2)
    print("Saved data/bank_statement.json (22 transactions)")

    # Also save bank statement as CSV for standard accounting workflow compatibility
    with open("data/bank_statement.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["txn_id", "date", "type", "amount", "narration", "ref_no"])
        writer.writeheader()
        writer.writerows(BANK_STATEMENT)
    print("Saved data/bank_statement.csv")

    with open("data/ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(GROUND_TRUTH, f, indent=2)
    print("Saved data/ground_truth.json (25 ground truth entries)")

if __name__ == "__main__":
    main()
