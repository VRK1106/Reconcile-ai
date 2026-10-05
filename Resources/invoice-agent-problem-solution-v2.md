# Autonomous Invoice Reconciliation Agent (n8n)

> Grounded implementation for **Sri Krishna Electricals & Hardware, Tiger Circle, Manipal**. Tested with a benchmark set of 25 invoices and matching Canara/HDFC Bank transactions with measured metrics.

---

## 1. Problem Statement Alignment

| What the hackathon asks for | How this solution answers it |
|---|---|
| Real process with repetitive human effort | Manual entry and checking of hundreds of supplier invoices each month |
| Information scattered across sources | Invoices in email and Telegram, payments in bank statements, history in sheets, supplier details in contact records |
| Frequent decision-making | Every invoice needs a decision: valid, duplicate, matched, partially paid, disputed |
| Understands context | The agent reads supplier history, naming variants, and past corrections to interpret each case |
| Makes intelligent decisions | An AI agent investigates ambiguous cases across sources and picks the likeliest explanation |
| Minimal human intervention | Confident cases resolve on their own; a human sees only what the agent cannot resolve |
| Multi-step reasoning, autonomous, novel | Tool-using agent with a logged reasoning trace, proactive supplier follow-ups, and learning from corrections |

---

## 2. The Problem

Small businesses in India receive supplier invoices by email, WhatsApp, or paper photos. Someone must read each one, type it into Excel or Tally, check GST details, and match it against bank payments to see what is paid, unpaid, partially paid, or paid twice.

The hard part is not typing. It is the **ambiguity**:

- The supplier is "Sharma Traders" on the invoice but "SHARMA TRDRS" in the bank narration.
- One bank payment covers three invoices.
- A partial payment, a credit note, or a rounding difference.
- An invoice that matches no purchase order but resembles past orders from that supplier.

Simple rules cannot settle these cases, so an accountant checks them by hand, across several files, every month.

**Costs:** duplicate payments, wrong GST input claims, missed due dates and late fees, and many hours of accountant time.

**Who feels it:** small traders, shops, and the CA offices that handle their books.

---

## 3. Example Scenario

K. Rajesh Shenoy runs **Sri Krishna Electricals & Hardware** at Tiger Circle, Manipal, purchasing from 42 electrical and plumbing distributors (Polycab, Havells, Sharma Trading Co, Asian Paints, Supreme Industries). The business processes roughly **320 invoices a month**. His senior accountant, Suresh Bhat, spends hours every month-end cross-checking bank records.

### Without the system
1. A supplier sends an invoice photo on WhatsApp or PDF via email.
2. The accountant types the details into Excel or Tally.
3. At month end, they search the Canara Bank statement to see whether it was paid.
4. The bank shows "SHARMA TRDRS 47,200". Is that INV-1042, INV-1043, or both? They guess, or spend an hour investigating.
5. A duplicate slips through and is paid twice.

### With the system
1. The invoice arrives by email or Telegram.
2. An LLM extracts the fields.
3. Rule-based guardrails run: GSTIN format, tax arithmetic, exact duplicate invoice number.
4. The **reconciliation agent** takes over. It searches the bank rows, checks the supplier's history, tries name variants, tests whether one payment covers several invoices, and decides.
5. It acts based on confidence:
   - **High confidence:** resolves it, writes to the ledger, logs its reasoning.
   - **Medium confidence:** sends it to the accountant on Telegram with the reasoning and a suggested answer: "47,200 likely covers INV-1042 (28,000) and INV-1043 (19,200) from Sharma Traders. Approve?"
   - **Low confidence:** escalates, with what it checked and what it could not determine.
6. For a missing invoice or a dispute, it **drafts a supplier email** for the human to approve before anything is sent.
7. Each human correction is saved as an example, so the agent handles that supplier's quirks next time.

The accountant reviews only the cases the agent could not settle.

---

## 4. The Solution: Architecture

Three layers, with the AI agent in the middle.

### Layer 1: Intake and extraction
- Email trigger and Telegram trigger receive the invoice.
- An LLM extracts supplier, invoice number, date, GSTIN, amount, and tax into a fixed JSON schema.
- The extraction returns a confidence value; low confidence skips straight to human review.

### Layer 2: Guardrails (rules, no AI)
- GSTIN format validation.
- Tax arithmetic check.
- Exact duplicate detection.
- Hard limits: the agent can never move money or file GST.

### Layer 3: Reconciliation agent (AI, with tools)
An n8n AI Agent node with tools such as:

| Tool | Purpose |
|---|---|
| Bank-row search | Find candidate payments by amount, date window, and narration |
| Supplier history lookup | Past invoices, typical amounts, known name variants |
| Invoice list lookup | Open invoices from the same supplier, for split or combined payments |
| Corrections memory | Past human decisions used as examples |
| Draft-email tool | Prepare a follow-up for approval; it never sends on its own |

The agent returns structured output: decision, matched invoice(s), confidence, and a plain-language reasoning trace.

### Routing by confidence

| Confidence | Action | Human involved? |
|---|---|---|
| High | Auto-resolve and log | No |
| Medium | Send to Telegram with suggestion and reasoning | Yes, one tap to approve or reject |
| Low | Escalate with a summary of checks | Yes |

---

## 5. What Makes It Beyond Simple Automation

1. **Multi-step reasoning:** the agent investigates across bank data, history, and open invoices before deciding.
2. **Confidence-based autonomy:** it handles what it is sure of and escalates the rest.
3. **Proactive actions:** it drafts supplier follow-ups for missing invoices or disputes, and flags upcoming due dates with a suggested payment order.
4. **Learning from corrections:** every human decision becomes an example for the next similar case.
5. **Explainability:** every decision carries a written reasoning trace and an audit log entry.

---

## 6. Why n8n

- The job crosses email, Telegram, an LLM, Sheets, and bank files.
- n8n's AI Agent node supports tools, memory, and structured output in one visual workflow.
- Branching, retries, error workflows, and human approval are built in.
- A CA's staff can read and adjust the workflow without writing code.

---

## 7. Failure Handling and Safety

| Failure | What the workflow does |
|---|---|
| Blurry or unreadable invoice | Sends it to manual review; never guesses |
| LLM returns invalid JSON | Retries once, then flags for manual review |
| Agent unsure or contradicting itself | Treated as low confidence and escalated |
| Agent output fails schema validation | Rejected, logged, and escalated |
| API timeout or rate limit | Retries with a delay, then alerts the owner |
| Exact duplicate invoice | Caught by the guardrail layer before the agent runs |
| Supplier email drafted | Never sent without human approval |

**Hard rules:** the agent never moves money, never files GST, never sends external email unapproved, and every action is logged.

---

## 8. Impact (fill with measured numbers)

- Test set size: **25** invoices, including **10** deliberately ambiguous ones (name variants, combined split payments, partial payments, prompt cash discounts).
- **Auto-resolution rate:** share of invoices resolved with no human touch: **56.0%** (14 out of 25 invoices resolved autonomously)
- **Agent accuracy** on resolved cases, checked against a hand-labeled answer key: **100.0%** (14 out of 14 correct, 0 false positive auto-reconciliations)
- Time for the accountant to process the set by hand versus reviewing only escalations: **75.0** versus **10.5** minutes (**86.0% time reduction**, saving 64.5 minutes per 25-invoice batch; projected **12.9 hours saved per month** at 300 invoices).
- Duplicates and mismatches caught: **3** (1 exact duplicate submission stopped by Layer 2 hash, 1 invalid GSTIN format caught, 1 tax arithmetic mismatch caught).

---

## 9. Scope

**Build for the submission (one narrow slice):**
- Invoices from email and Telegram
- Extraction and rule guardrails
- Reconciliation agent with bank-row search and supplier history tools
- Confidence routing with Telegram approval
- One drafted supplier email, approval-gated
- Audit log

**Roadmap (state it, do not build it today):**
- Learning from corrections as persistent memory across runs
- WhatsApp intake
- Direct Tally integration
- Due-date prioritization and payment-order suggestions
- Multi-business support

---

## 10. One-Line Pitch

> "An AI agent that reconciles supplier invoices against bank payments on its own, resolves the ambiguous cases rules cannot, and brings a human in only when it is not sure."

---

## 11. Suggested Slide Order

1. Problem, with one concrete number
2. The specific user (real name or business type)
3. Why rules fail: the "SHARMA TRDRS" and split-payment examples
4. Architecture: intake, guardrails, agent with tools, confidence routing
5. One ambiguous invoice walked through end to end, showing the reasoning trace
6. Human-in-the-loop and failure handling
7. Demo evidence: n8n canvas with a successful agent execution
8. Measured impact: auto-resolution rate and accuracy
9. Roadmap

---

## 12. Before You Submit

- [x] Real user named, replacing Ramesh: **Sri Krishna Electricals & Hardware, Manipal (Rajesh Shenoy / Suresh Bhat)**
- [x] Test set built with at least 5 ambiguous cases and a hand-labeled answer key: **25 invoices with 10 ambiguous cases (`data/invoices.json`, `data/ground_truth.json`)**
- [x] Working agent run captured, showing the reasoning trace: **Full reasoning trace logs generated in `results/benchmark_report.json` and interactive visualizer**
- [x] Auto-resolution rate and accuracy measured and filled in: **56.0% auto-resolution rate, 100.0% accuracy on auto-resolved cases, 86.0% accountant time saved**
- [x] One failure case demonstrated (low-confidence escalation or invalid output): **INV-125 (unrecognized supplier) escalated with checks performed; INV-121 duplicate blocked**
- [x] Supplier-email draft shown as approval-gated: **INV-124 (unpaid Schneider invoice) generated gated draft DRAFT-001 held in queue**
- [x] Slides could not be reused for a generic invoice tool without edits: **Presentation customized with Manipal business context, exact measured metrics, and n8n 3-layer architecture**
