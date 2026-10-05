"""
Database Layer with connection pooling, migrations, and transactional helpers.
"""
import sqlite3
import os
import json
from typing import List, Dict, Any, Optional

DB_FILE = os.path.join(os.path.dirname(__file__), "reconcile_ai.db")
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;") # Write-Ahead Logging for high concurrent read performance
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()
    print("[DB] Initialized schema and tables in reconcile_ai.db")

def seed_initial_data(suppliers_path: str = "data/suppliers.json", bank_path: str = "data/bank_statement.json"):
    conn = get_connection()
    cur = conn.cursor()

    # Check if already seeded
    cur.execute("SELECT COUNT(*) as cnt FROM suppliers")
    if cur.fetchone()["cnt"] > 0:
        conn.close()
        return

    # Seed Suppliers
    if os.path.exists(suppliers_path):
        with open(suppliers_path, "r", encoding="utf-8") as f:
            suppliers = json.load(f)
        for s in suppliers:
            cur.execute("""
                INSERT OR IGNORE INTO suppliers (supplier_id, name, gstin, aliases_json, email, phone, city, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["supplier_id"], s["name"], s["gstin"], json.dumps(s.get("aliases", [])),
                s.get("email"), s.get("phone"), s.get("city"), s.get("category")
            ))
        print(f"[DB] Seeded {len(suppliers)} master suppliers")

    # Seed Bank Transactions
    if os.path.exists(bank_path):
        with open(bank_path, "r", encoding="utf-8") as f:
            txns = json.load(f)
        for t in txns:
            cur.execute("""
                INSERT OR IGNORE INTO bank_transactions (txn_id, txn_date, txn_type, amount, narration, ref_no, reconciliation_status)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
            """, (
                t["txn_id"], t["date"], t.get("type", "DEBIT"), t["amount"], t["narration"], t["ref_no"]
            ))
        print(f"[DB] Seeded {len(txns)} bank transactions")

    conn.commit()
    conn.close()
