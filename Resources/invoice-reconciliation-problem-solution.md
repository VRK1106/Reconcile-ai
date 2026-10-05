# Invoice-to-Reconciliation Agent (n8n)

> Replace the example user below with a real shop or CA office before submitting. Replace every figure marked **[measure]** with a number you measured yourself.

---

## 1. The Problem

Small businesses in India receive supplier invoices by email, WhatsApp, or as paper photos. Someone must:

1. Read each invoice.
2. Type the details (supplier, invoice number, date, GSTIN, amount, tax) into Excel or Tally.
3. Check that the GSTIN and tax amount are correct.
4. Match each invoice against bank statement rows to see whether it is paid, unpaid, partially paid, or paid twice.

This work is slow, repetitive, and error-prone. Mistakes are costly:

- Duplicate payments that go unnoticed for weeks.
- Wrong GST input claims.
- Missed due dates and late fees.
- Month-end reconciliation that eats hours of an accountant's time.

**Who feels it:** small traders, shops, and the CA offices that handle their books.

---

## 2. Example Scenario

Ramesh runs a hardware shop and buys from about 40 suppliers. He receives roughly **300 invoices a month [measure]**. His accountant spends many hours on data entry and checking.

### Without the system
1. A supplier sends an invoice photo on WhatsApp.
2. The accountant types the details into Excel.
3. At month end, they search the bank statement to see whether it was paid.
4. A duplicate invoice slips through and is paid twice.

### With the system
1. The invoice arrives by email or is forwarded to a Telegram bot.
2. n8n picks it up automatically. An LLM extracts the fields.
3. Rule-based checks run (no LLM): GSTIN format, tax arithmetic, duplicate invoice number.
4. The workflow compares the amount against bank statement rows and labels the invoice: **matched**, **unpaid**, **partially paid**, or **possible duplicate**.
5. Clean invoices go straight to the Google Sheet or accounting file. Suspicious ones go to the accountant on Telegram with the reason, for example: "Possible duplicate of INV-1042. Approve or reject?"
6. Every decision is logged with who, what, and when.

The accountant reviews only the flagged invoices, not all 300.

---

## 3. The Solution

An n8n workflow that ingests invoices, extracts and validates them, reconciles them against bank payments, and routes only exceptions to a human.

### Workflow stages

| Stage | What happens | n8n building blocks (adjust to your build) |
|---|---|---|
| Intake | Invoice arrives by email attachment or Telegram upload | Email trigger (IMAP/Gmail), Telegram trigger |
| Extraction | LLM reads the document and returns structured fields | HTTP Request / LLM node, with a fixed JSON schema |
| Validation | GSTIN format check, tax math check, duplicate check | Code / IF / Switch nodes |
| Reconciliation | Match amount, supplier, and date window against bank statement rows | Google Sheets or file read, Code node |
| Routing | Clean goes to the ledger; flagged goes to human review | Switch node, Telegram message with approve/reject buttons |
| Audit | Log every decision and every workflow error | Google Sheets append, Error Trigger workflow |

### Design principle
The LLM does **only** the messy part: reading the document. Every decision (valid, duplicate, matched) is made by plain rules, so results are predictable and explainable.

---

## 4. Why n8n Fits

- The job crosses several systems: email, Telegram, an LLM, Sheets, and a bank file.
- It has branches: clean versus suspicious.
- It needs a human approval step and retries when something fails.
- Non-developers (a CA's staff) can read and adjust the visual workflow.

---

## 5. Failure Handling

| Failure | What the workflow does |
|---|---|
| Blurry or unreadable invoice | Sends it to manual review; never guesses |
| LLM returns invalid or incomplete JSON | Retries once, then flags for manual review |
| Low-confidence extraction | Flags it; never auto-approved |
| API timeout or rate limit | Retries with a delay, then alerts the owner |
| Same invoice submitted twice | Caught by the duplicate check and flagged |
| Partial payment | Labeled **partially paid** with the remaining amount shown |

---

## 6. Impact (fill with measured numbers)

- Time to process 10 invoices by hand: **[measure] minutes**
- Time to process 10 invoices through the workflow, including human review of flagged ones: **[measure] minutes**
- Estimated hours saved per month at 300 invoices: **[measure]**
- Duplicates caught in your test set: **[measure]**

**How to measure:** time yourself entering 10 invoices manually, then run 10 through the workflow. A measured result is stronger than any estimate.

---

## 7. Scope

**In scope for the submission (one narrow slice):**
- Invoices from email and Telegram
- Extraction, GSTIN and tax validation, duplicate detection
- Matching against an uploaded bank statement (CSV or Sheet)
- Human approval over Telegram
- Audit log

**Roadmap (state it, do not build it today):**
- WhatsApp intake
- Direct Tally integration
- Payment reminders for due dates
- Multi-business support

---

## 8. Limits and Responsible Use

- The system flags and suggests; a human makes the final call on anything uncertain.
- It does not file GST returns or move money.
- Extraction accuracy depends on invoice quality, so accuracy should be reported on your own test set.

---

## 9. One-Line Pitch

> "We turn 300 invoices a month of manual typing and checking into a few flagged exceptions for a human to approve."

---

## 10. Suggested Slide Order

1. Problem, with one concrete number
2. The specific user (a real name or business type)
3. Workflow diagram labeled with actual n8n nodes
4. Example invoice walked through end to end
5. Human-approval and error-handling path
6. Demo evidence: n8n canvas screenshot showing a successful execution
7. Measured impact
8. Scope and roadmap

---

## 11. Before You Submit

- [ ] Real user named, replacing Ramesh
- [ ] Working workflow run captured as a screenshot
- [ ] 10-invoice timing test done, and numbers filled in above
- [ ] At least one failure case demonstrated (bad invoice or duplicate)
- [ ] Slides could not be reused for a generic invoice tool without edits
