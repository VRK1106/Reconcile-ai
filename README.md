# Autonomous Invoice Reconciliation Enterprise System

> **HackSprint Manipal Submission**  
> Complete enterprise-grade autonomous invoice-to-bank reconciliation system featuring:
> - **3-Layer Architecture** (Intake & Normalization → Deterministic Rule Guardrails → AI Tool Reasoning)
> - **Production FastAPI Backend** with ACID SQLite WAL-mode persistence
> - **Professional Observability & Monitoring** (Prometheus `/metrics`, OpenTelemetry p50/p95/p99 latency tracking, host CPU/RAM utilization)
> - **Human-in-the-Loop (HITL) Governance Queue** with real-time ledger authorization
> - **Approval-Gated Supplier Email Outbox** with strict human dispatch locks
> - **Enterprise Operations Console** at `http://127.0.0.1:8000/console/`

---

## 🏛️ System Architecture

```
                                      ┌────────────────────────────────────────┐
                                      │   Layer 1: Multi-Channel Ingestion     │
                                      │  • Email / IMAP Ingest                 │
                                      │  • Telegram Bot Webhook                │
                                      │  • REST API (/api/v1/invoices/ingest)  │
                                      └──────────────────┬─────────────────────┘
                                                         │
                                                         ▼
                                      ┌────────────────────────────────────────┐
                                      │   Layer 2: Deterministic Guardrails    │
                                      │  • Indian 15-char GSTIN regex & state  │
                                      │  • Tax arithmetic (0/5/12/18/28% slabs)│
                                      │  • Duplicate hash lock (zero AI drift) │
                                      └──────────┬───────────────────┬─────────┘
                                       Passed    │                   │ Violations
                                                 ▼                   ▼
                     ┌────────────────────────────────────────┐   ┌───────────────────────────┐
                     │    Layer 3: AI Tool-Augmented Agent    │   │  Blocked / Alert Queue    │
                     │  • bank_row_search                     │   │  • Blocked before AI      │
                     │  • supplier_history_lookup (aliases)   │   │  • Zero ledger corruption │
                     │  • invoice_list_lookup (subset sum)    │   └───────────────────────────┘
                     │  • corrections_memory_lookup           │
                     │  • draft_email_tool (gated outbox)     │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
                     ┌────────────────────────────────────────────────────────┐
                     │              Confidence-Based Governance               │
                     └───────┬──────────────────────┬──────────────────┬──────┘
                             │                      │                  │
         High Confidence     │  Medium Confidence   │   Low Conf /     │
         (>= 0.85)           │  (0.50 - 0.84)       │   Unrecognized   │
                             ▼                      ▼                  ▼
                 ┌──────────────────────┐┌──────────────────────┐┌──────────────────────┐
                 │ Auto-Reconciled      ││ Telegram HITL Queue  ││ Escalation Incident  │
                 │ Purchase Ledger      ││ Suresh Bhat 1-tap    ││ Vendor onboarding /  │
                 │ (ACID DB Commit)     ││ ledger authorization ││ inquiry draft        │
                 └──────────────────────┘└──────────────────────┘└──────────────────────┘
                             │                      │                  │
                             └──────────────────────┼──────────────────┘
                                                    │
                                                    ▼
                     ┌────────────────────────────────────────────────────────┐
                     │       Enterprise Observability & Monitoring Engine     │
                     │  • Prometheus Scrape Endpoint (/metrics)               │
                     │  • Rolling Window P50, P95, P99 Latency percentiles    │
                     │  • Per-Tool Execution Duration Histograms              │
                     │  • Host Process Resource Monitor (CPU %, RSS MB)       │
                     │  • Immutable Audit Log (RFC 5424 structured traces)    │
                     └────────────────────────────────────────────────────────┘
```

---

## 📈 Measured Performance & SLAs

Evaluated on **Sri Krishna Electricals & Hardware, Tiger Circle, Manipal** (Proprietor: K. Rajesh Shenoy, Accountant: Suresh Bhat):
- **Dataset**: 25 realistic GST invoices + 22 Canara/HDFC Bank transactions (including 10 complex ambiguous edge cases).
- **Auto-Resolution Rate**: **56.0%** (14 of 25 zero human touch).
- **Agent Precision on Auto-Resolved**: **100.0%** (0 false positive reconciliations).
- **Accuracy on Ambiguous Cases**: **100.0%** (10 of 10 ambiguous cases correctly classified).
- **P95 Latency**: **5.18 ms** (Average: **2.00 ms**, well below the 100 ms SLA target).
- **SLA Compliance**: **100.0%**.
- **Accountant Effort**: **75.0 minutes manual baseline → 10.5 minutes review** (**86.0% time reduction**).
- **Monthly Savings at 300 Invoices**: **12.9 hours / month**.

---

## 🛠️ REST API Specification

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health` | Health & liveness probe (DB, WAL, governance mode) |
| `GET` | `/metrics` | Standard Prometheus scrape endpoint (OpenMetrics) |
| `GET` | `/api/v1/telemetry/performance` | Real-time JSON telemetry (p50/p95/p99 latency, SLA compliance, tool breakdown) |
| `POST` | `/api/v1/invoices/ingest` | Ingest single invoice via JSON payload |
| `GET` | `/api/v1/invoices` | List invoices with status, confidence, and search filters |
| `GET` | `/api/v1/invoices/{id}` | Deep dive invoice detail, matched bank UTR, tool latency logs, and reasoning trace |
| `GET` | `/api/v1/bank/transactions` | Bank statement ledger and reconciliation matching status |
| `GET` | `/api/v1/hitl/tasks` | List pending Human-in-the-Loop approval requests |
| `POST` | `/api/v1/hitl/tasks/{id}/resolve` | Resolve HITL review (`APPROVE` or `REJECT`) with ACID DB commit |
| `GET` | `/api/v1/email-drafts` | Gated supplier inquiry outbox |
| `POST` | `/api/v1/email-drafts/{id}/dispatch` | Authorize and dispatch drafted supplier follow-up email |
| `GET` | `/api/v1/audit/logs` | Immutable audit trail with trace IDs |
| `POST` | `/api/v1/system/reconcile-benchmark-batch` | Re-run benchmark batch through pipeline |
| `GET` | `/console/` | Enterprise Operations & Observability Console |

---

## 🚀 Running the System

### 1. Launch the Backend Engine & Monitoring Server
```bash
python -m uvicorn backend.api.server:app --host 127.0.0.1 --port 8000
```

### 2. Access the Enterprise Operations Console
Open **[http://127.0.0.1:8000/console/](http://127.0.0.1:8000/console/)** in any browser.
The console provides:
1. **System Topology**: Live diagram with active node counters and data flow.
2. **Reconciled Purchase Ledger**: Live table with instant search, status badges, and deep-dive drawer inspection.
3. **HITL Review Queue**: Actionable tasks for combined payments, partial payments, and prompt discounts with live 1-click **Approve & Post** or **Reject** buttons that trigger real API calls.
4. **Approval-Gated Outbox**: Review generated inquiry drafts, verify safety locks, and click **Authorize & Dispatch Email**.
5. **Observability & Performance**: Real-time Prometheus metrics, p50/p95/p99 latency histograms, tool breakdown, and raw OpenMetrics terminal.
6. **Immutable Audit Stream**: Cryptographically correlated RFC 5424 audit logs.

### 3. Scrape Prometheus Metrics
```bash
curl http://127.0.0.1:8000/metrics
```
Ready to be scraped by Prometheus or Grafana.
