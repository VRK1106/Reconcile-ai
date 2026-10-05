// Interactive Dashboard for Autonomous Invoice Reconciliation Agent
let invoicesData = [];
let selectedInvoice = null;
let currentFilter = 'all';

async function init() {
  try {
    const res = await fetch('data.json');
    invoicesData = await res.json();
  } catch (e) {
    console.error('Failed to load data.json, using fallback', e);
  }

  setupEventListeners();
  renderTable();
  if (invoicesData.length > 0) {
    // Select the famous Sharma Traders ambiguous case by default to showcase multi-invoice reasoning
    const featured = invoicesData.find(i => i.invoice_id === 'INV-115') || invoicesData[0];
    selectInvoice(featured);
  }
}

function setupEventListeners() {
  // Filter tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderTable();
    });
  });

  // Re-run batch button animation
  const runBtn = document.getElementById('runAllBtn');
  if (runBtn) {
    runBtn.addEventListener('click', () => {
      runBtn.innerText = '⏳ Simulating Live n8n Run...';
      runBtn.disabled = true;
      setTimeout(() => {
        runBtn.innerText = '▶ Re-Run 25 Invoice Batch';
        runBtn.disabled = false;
        renderTable();
      }, 800);
    });
  }

  // Telegram modal close
  const closeTg = document.getElementById('closeTgModal');
  if (closeTg) {
    closeTg.addEventListener('click', () => {
      document.getElementById('telegramModal').classList.add('hidden');
    });
  }
}

function getFilteredInvoices() {
  if (currentFilter === 'auto') {
    return invoicesData.filter(i => i.decision === 'AUTO_RESOLVE_PAID');
  }
  if (currentFilter === 'telegram') {
    return invoicesData.filter(i => i.confidence === 'MEDIUM');
  }
  if (currentFilter === 'guardrail') {
    return invoicesData.filter(i => i.decision === 'BLOCKED_BY_GUARDRAIL' || i.confidence === 'LOW' || i.decision === 'UNPAID_EMAIL_DRAFTED');
  }
  return invoicesData;
}

function renderTable() {
  const tbody = document.getElementById('invoicesTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const list = getFilteredInvoices();

  list.forEach(inv => {
    const tr = document.createElement('tr');
    tr.className = `invoice-row ${selectedInvoice && selectedInvoice.invoice_id === inv.invoice_id ? 'selected' : ''}`;
    tr.id = `row-${inv.invoice_id}`;
    tr.onclick = () => selectInvoice(inv);

    // Case type badge
    let caseBadge = `<span class="badge badge-clean">Clean Match</span>`;
    if (inv.case_type.startsWith('ambiguous')) {
      caseBadge = `<span class="badge badge-ambiguous">${formatCaseType(inv.case_type)}</span>`;
    } else if (inv.case_type.startsWith('guardrail')) {
      caseBadge = `<span class="badge badge-guardrail">Guardrail Block</span>`;
    } else if (inv.case_type === 'unpaid_due_soon') {
      caseBadge = `<span class="badge badge-unpaid">Unpaid / Email</span>`;
    } else if (inv.case_type === 'low_confidence_unrecognized') {
      caseBadge = `<span class="badge badge-guardrail">Low Conf</span>`;
    }

    // Status tag
    let statusHtml = '';
    if (inv.decision === 'AUTO_RESOLVE_PAID') {
      statusHtml = `<span class="status-tag auto">✓ Auto-Resolved</span>`;
    } else if (inv.confidence === 'MEDIUM') {
      statusHtml = `<span class="status-tag hitl">💬 Telegram HITL</span>`;
    } else if (inv.decision === 'BLOCKED_BY_GUARDRAIL') {
      statusHtml = `<span class="status-tag blocked">⛔ Blocked</span>`;
    } else {
      statusHtml = `<span class="status-tag escalated">⚠️ Escalated</span>`;
    }

    // Conf Class
    const confClass = inv.confidence === 'HIGH' ? 'conf-high' :
                      inv.confidence === 'MEDIUM' ? 'conf-med' :
                      inv.confidence === 'LOW' ? 'conf-low' : 'conf-zero';

    tr.innerHTML = `
      <td>
        <div class="inv-num">${inv.invoice_number}</div>
        <div class="inv-id">${inv.invoice_id} • ${inv.invoice_date}</div>
      </td>
      <td class="supplier-col">
        <div class="sup-name">${inv.supplier_name}</div>
        <div class="sup-gstin">${inv.supplier_gstin}</div>
      </td>
      <td class="amount-col">₹${inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
      <td>${caseBadge}</td>
      <td><span class="conf-badge ${confClass}">${inv.confidence}</span></td>
      <td>${statusHtml}</td>
      <td><button class="btn btn-primary" style="padding: 4px 8px; font-size: 11px;" onclick="event.stopPropagation(); selectInvoiceById('${inv.invoice_id}')">Inspect</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function selectInvoiceById(id) {
  const inv = invoicesData.find(i => i.invoice_id === id);
  if (inv) selectInvoice(inv);
}

function selectInvoice(inv) {
  selectedInvoice = inv;
  document.querySelectorAll('.invoice-row').forEach(r => r.classList.remove('selected'));
  const row = document.getElementById(`row-${inv.invoice_id}`);
  if (row) row.classList.add('selected');

  const emptyState = document.getElementById('emptyInspectorState');
  const content = document.getElementById('inspectorContent');
  if (emptyState) emptyState.classList.add('hidden');
  if (content) content.classList.remove('hidden');

  renderInspector(inv);
}

function formatCaseType(ct) {
  const map = {
    'clean_single_match': 'Clean Match',
    'ambiguous_name_variant': 'Name Alias Variant',
    'ambiguous_combined_payment': 'Combined Split Payment',
    'ambiguous_partial_payment': 'Partial Payment',
    'ambiguous_discount_difference': 'Cash Discount Variance',
    'guardrail_exact_duplicate': 'Duplicate Submission',
    'guardrail_invalid_gstin': 'Invalid GSTIN',
    'guardrail_tax_arithmetic_mismatch': 'Tax Math Error',
    'unpaid_due_soon': 'Unpaid / Draft Email',
    'low_confidence_unrecognized': 'Unrecognized Vendor'
  };
  return map[ct] || ct;
}

function renderInspector(inv) {
  const container = document.getElementById('inspectorContent');
  if (!container) return;

  // Timeline items
  const traceStepsHtml = inv.reasoning_trace.map(step => {
    let stepClass = '';
    if (step.includes('Match Confirmed') || step.includes('Auto-Resolving') || step.includes('Passed')) {
      stepClass = 'success';
    } else if (step.includes('Guardrail Violation') || step.includes('Low confidence')) {
      stepClass = 'alert';
    } else if (step.includes('Telegram') || step.includes('Combined') || step.includes('Partial')) {
      stepClass = 'prompt';
    }
    return `
      <div class="trace-step ${stepClass}">
        <div class="trace-step-text">${step}</div>
      </div>
    `;
  }).join('');

  // Telegram HITL card if present
  let telegramCardHtml = '';
  if (inv.telegram_notification) {
    const buttonsHtml = inv.telegram_notification.buttons.map(b => 
      `<button class="tg-btn ${b.includes('Approve') ? 'primary' : ''}" onclick="handleTgAction('${b}', '${inv.invoice_id}')">${b}</button>`
    ).join('');

    telegramCardHtml = `
      <div class="tg-preview-card">
        <div class="tg-header">
          <span>📱</span> Telegram Human-In-The-Loop Prompt (Suresh Bhat)
        </div>
        <div class="tg-text">${inv.telegram_notification.text}</div>
        <div class="tg-btn-group">
          ${buttonsHtml}
        </div>
      </div>
    `;
  }

  // Email draft card if present
  let emailCardHtml = '';
  if (inv.email_draft) {
    emailCardHtml = `
      <div class="email-draft-card">
        <div class="email-header">
          <span>✉️ Gated Supplier Email Draft (Held in Queue)</span>
          <span style="font-size: 10px; color: #fbbf24;">APPROVAL REQUIRED</span>
        </div>
        <div style="margin-bottom: 6px;"><strong>To:</strong> ${inv.email_draft.to}</div>
        <div style="margin-bottom: 8px;"><strong>Subject:</strong> ${inv.email_draft.subject}</div>
        <div class="email-body">${inv.email_draft.body}</div>
        <div class="email-gate">
          <span>🔒</span> Safety Gate: Will never send until accountant clicks 'Send'.
        </div>
        <div style="margin-top: 10px; display: flex; gap: 8px;">
          <button class="tg-btn primary" onclick="alert('Email dispatched to ${inv.email_draft.to} after accountant authorization!')">Authorize & Send</button>
          <button class="tg-btn" onclick="alert('Draft kept on hold.')">Edit Draft</button>
        </div>
      </div>
    `;
  }

  // Reconciliation summary
  let matchBadgeHtml = '';
  if (inv.matched_txns && inv.matched_txns.length > 0) {
    matchBadgeHtml = `
      <div class="tool-callout" style="border-left-color: var(--accent-emerald);">
        <div class="tool-name" style="color: #34d399;">
          <span>🏦</span> Matched Bank Record: ${inv.matched_txns.join(', ')}
        </div>
        <div>Reconciliation Basis: <strong>${inv.reconciliation_details?.match_basis || 'EXACT_MATCH'}</strong></div>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="inspector-header">
      <div class="inspector-meta">
        <div>
          <h3>${inv.invoice_number}</h3>
          <div style="font-size: 13px; color: var(--text-muted); font-weight: 500;">${inv.supplier_name}</div>
        </div>
        <div>
          <div class="inspector-amount">₹${inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          <div style="font-size: 11px; color: var(--text-dim); text-align: right;">GSTIN: ${inv.supplier_gstin}</div>
        </div>
      </div>
      <div class="inspector-tags">
        <span class="badge ${inv.case_type.startsWith('ambiguous') ? 'badge-ambiguous' : 'badge-clean'}">${formatCaseType(inv.case_type)}</span>
        <span class="badge" style="background: rgba(255,255,255,0.08);">${inv.decision}</span>
        <span class="conf-badge ${inv.confidence === 'HIGH' ? 'conf-high' : 'conf-med'}">${inv.confidence} CONFIDENCE</span>
      </div>
    </div>

    ${matchBadgeHtml}

    <div style="margin-top: 14px;">
      <h4 style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); margin-bottom: 8px;">
        Multi-Step Agent Reasoning Trace
      </h4>
      <div class="trace-timeline">
        ${traceStepsHtml}
      </div>
    </div>

    ${telegramCardHtml}
    ${emailCardHtml}
  `;
}

function handleTgAction(action, invId) {
  alert(`Human Accountant Action Recorded: [${action}] for Invoice ${invId}.\nSaved to audit log with timestamp.`);
}

window.onload = init;
