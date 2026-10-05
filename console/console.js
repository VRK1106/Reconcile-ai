// ReconcileAI Enterprise Command Center Client Logic
let activeTab = 'tab-command-center';
let invoicesList = [];
let selectedInvoice = null;
let currentFilter = 'all';
let pollingInterval = null;

async function initConsole() {
  setupTabs();
  setupFiltersAndSearch();
  setupBatchButton();
  await refreshAll();

  // Auto-select INV-115 (featured ambiguous multi-invoice case) on boot
  if (invoicesList.length > 0) {
    const featured = invoicesList.find(i => i.invoice_id === 'INV-115') || invoicesList[0];
    selectInvoice(featured);
  }

  // Poll telemetry every 3 seconds
  pollingInterval = setInterval(refreshTelemetry, 3000);
}

function setupTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      tab.classList.add('active');
      activeTab = tab.dataset.tab;
      const target = document.getElementById(activeTab);
      if (target) target.classList.add('active');

      if (activeTab === 'tab-command-center') renderCommandTable();
      if (activeTab === 'tab-hitl') loadHitlTasks();
      if (activeTab === 'tab-outbox') loadOutbox();
      if (activeTab === 'tab-monitoring') loadMonitoring();
      if (activeTab === 'tab-audit') loadAuditLogs();
    });
  });
}

function setupFiltersAndSearch() {
  // Pill filters
  document.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderCommandTable();
    });
  });

  // Search input
  const searchInput = document.getElementById('liveSearchInput');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      renderCommandTable();
    });
  }
}

function setupBatchButton() {
  const btn = document.getElementById('batchReRunBtn');
  if (!btn) return;
  btn.onclick = async () => {
    btn.disabled = true;
    btn.innerText = '⚡ Processing Batch...';
    try {
      const res = await fetch('/api/v1/system/reconcile-benchmark-batch', { method: 'POST' });
      const data = await res.json();
      btn.innerText = `✓ Processed ${data.processed_count} Invoices`;
      await refreshAll();
      setTimeout(() => {
        btn.disabled = false;
        btn.innerText = '⚡ Re-Run Benchmark';
      }, 1500);
    } catch (e) {
      console.error(e);
      btn.disabled = false;
      btn.innerText = '⚡ Re-Run Benchmark';
    }
  };
}

async function refreshAll() {
  await Promise.all([
    refreshTelemetry(),
    loadInvoices(),
    loadHitlTasks(),
    loadOutbox(),
    loadMonitoring(),
    loadAuditLogs()
  ]);
}

// 1. Live Telemetry Poller
async function refreshTelemetry() {
  try {
    const res = await fetch('/api/v1/telemetry/performance');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('telemetryCpu').innerText = `${data.host_telemetry.cpu_percent}%`;
    document.getElementById('telemetryMem').innerText = `${data.host_telemetry.memory_rss_mb} MB`;
    document.getElementById('telemetryP95').innerText = `${data.sla_performance.p95_latency_ms} ms`;

    // KPI Banner
    const autoEl = document.getElementById('kpiAutoRate');
    if (autoEl) autoEl.innerText = `${data.conversion_rates.auto_resolution_rate_pct}%`;

    const p95El = document.getElementById('kpiP95');
    if (p95El) p95El.innerText = `${data.sla_performance.p95_latency_ms} ms`;

    // Monitoring Cards
    const totalEl = document.getElementById('statTotalInvoices');
    if (totalEl) totalEl.innerText = data.sla_performance.total_invoices_reconciled;

    const avgEl = document.getElementById('statAvgLatency');
    if (avgEl) avgEl.innerText = `${data.sla_performance.avg_latency_ms} ms`;

    const statP95 = document.getElementById('statP95Latency');
    if (statP95) statP95.innerText = `${data.sla_performance.p95_latency_ms} ms`;

    const slaEl = document.getElementById('statSlaCompliance');
    if (slaEl) slaEl.innerText = `${data.sla_performance.sla_compliance_pct}%`;

    renderToolTelemetry(data.tool_telemetry);
  } catch (e) {
    console.warn('Telemetry error', e);
  }
}

// 2. Load Invoices
async function loadInvoices() {
  try {
    const res = await fetch('/api/v1/invoices?limit=100');
    const data = await res.json();
    invoicesList = data.invoices;
    renderCommandTable();
    updateTopologyCounters();
  } catch (e) {
    console.error('Failed to load invoices', e);
  }
}

function updateTopologyCounters() {
  const auto = invoicesList.filter(i => i.status === 'AUTO_RECONCILED').length;
  const hitl = invoicesList.filter(i => i.status.includes('HITL')).length;
  const blocked = invoicesList.filter(i => i.status.includes('BLOCKED') || i.status.includes('ESCALATED')).length;

  const autoEl = document.getElementById('statAutoCount');
  if (autoEl) autoEl.innerText = `${auto} Invoices (${Math.round(auto/invoicesList.length*100 || 0)}%)`;

  const hitlEl = document.getElementById('statHitlCount');
  if (hitlEl) hitlEl.innerText = `${hitl} Invoices (${Math.round(hitl/invoicesList.length*100 || 0)}%)`;

  const blkEl = document.getElementById('statBlockedCount');
  if (blkEl) blkEl.innerText = `${blocked} Invoices (${Math.round(blocked/invoicesList.length*100 || 0)}%)`;
}

function getFilteredInvoices() {
  const q = (document.getElementById('liveSearchInput')?.value || '').toLowerCase();

  return invoicesList.filter(inv => {
    // Search match
    const matchSearch = inv.supplier_name.toLowerCase().includes(q) ||
                        inv.invoice_number.toLowerCase().includes(q) ||
                        inv.supplier_gstin.toLowerCase().includes(q);

    // Filter match
    let matchFilter = true;
    if (currentFilter === 'auto') {
      matchFilter = (inv.status === 'AUTO_RECONCILED');
    } else if (currentFilter === 'hitl') {
      matchFilter = inv.status.includes('HITL');
    } else if (currentFilter === 'blocked') {
      matchFilter = inv.status.includes('BLOCKED') || inv.status.includes('ESCALATED');
    }

    return matchSearch && matchFilter;
  });
}

function renderCommandTable() {
  const tbody = document.getElementById('commandTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const list = getFilteredInvoices();

  list.forEach(inv => {
    const tr = document.createElement('tr');
    tr.className = `table-row-item ${selectedInvoice && selectedInvoice.invoice_id === inv.invoice_id ? 'selected' : ''}`;
    tr.id = `inv-row-${inv.invoice_id}`;
    tr.onclick = () => selectInvoice(inv);

    let statusPillClass = 'auto';
    if (inv.status === 'HITL_PENDING') statusPillClass = 'hitl';
    else if (inv.status === 'HITL_APPROVED') statusPillClass = 'hitl-approved';
    else if (inv.status.includes('BLOCKED')) statusPillClass = 'blocked';
    else if (inv.status.includes('ESCALATED')) statusPillClass = 'escalated';

    tr.innerHTML = `
      <td>
        <div class="inv-code">${inv.invoice_number}</div>
        <div class="inv-date">${inv.invoice_date} • ${inv.source}</div>
      </td>
      <td>
        <div class="vendor-title">${inv.supplier_name}</div>
        <div class="vendor-gstin">${inv.supplier_gstin}</div>
      </td>
      <td class="amount-text">₹${inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
      <td><span class="status-pill ${inv.confidence === 'HIGH' ? 'auto' : 'hitl'}">${inv.confidence}</span></td>
      <td><span class="status-pill ${statusPillClass}">${inv.status}</span></td>
      <td>
        <button class="btn btn-sm" style="background:var(--bg-accent); color:var(--text-primary);" onclick="event.stopPropagation(); selectInvoiceById('${inv.invoice_id}')">
          Inspect ↗
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function selectInvoiceById(id) {
  const inv = invoicesList.find(i => i.invoice_id === id);
  if (inv) selectInvoice(inv);
}

async function selectInvoice(inv) {
  selectedInvoice = inv;
  document.querySelectorAll('.table-row-item').forEach(r => r.classList.remove('selected'));
  const row = document.getElementById(`inv-row-${inv.invoice_id}`);
  if (row) row.classList.add('selected');

  // Fetch full details with tool calls and matched bank transaction
  try {
    const res = await fetch(`/api/v1/invoices/${inv.invoice_id}`);
    if (res.ok) {
      const fullDetail = await res.json();
      renderInspector(fullDetail);
    } else {
      renderInspector(inv);
    }
  } catch (e) {
    renderInspector(inv);
  }
}

function renderInspector(inv) {
  const container = document.getElementById('inspectorContent');
  if (!container) return;

  // Timeline reasoning steps
  const traceHtml = (inv.reasoning_trace || []).map(step => {
    let cls = '';
    if (step.includes('Verified') || step.includes('Auto-Post') || step.includes('Passed')) cls = 'success';
    else if (step.includes('Failure') || step.includes('Blocked') || step.includes('Escalation')) cls = 'alert';
    else if (step.includes('Combined') || step.includes('Partial') || step.includes('HITL')) cls = 'hitl';

    return `
      <div class="trace-item ${cls}">
        <div class="trace-text">${step}</div>
      </div>
    `;
  }).join('');

  // Matched bank record callout
  let bankMatchHtml = '';
  if (inv.matched_bank_rows && inv.matched_bank_rows.length > 0) {
    const b = inv.matched_bank_rows[0];
    bankMatchHtml = `
      <div class="tool-callout-box">
        <div class="tool-callout-title">
          <span>🏦</span> Matched Bank Debit: ${b.txn_id} (${b.ref_no})
        </div>
        <div style="font-family:var(--font-mono); font-size:11px; margin-top:2px;">
          ${b.narration}
        </div>
        <div style="margin-top:4px;">
          Date: ${b.txn_date} • Amount: <strong>₹${b.amount.toLocaleString('en-IN')}</strong> • Status: ${b.reconciliation_status}
        </div>
      </div>
    `;
  }

  // HITL Action Prompt if pending
  let hitlActionHtml = '';
  if (inv.status === 'HITL_PENDING') {
    hitlActionHtml = `
      <div class="inline-hitl-card">
        <div class="inline-hitl-header">
          <span>👤</span> Telegram HITL Prompt: Suresh Bhat Review Required
        </div>
        <div class="inline-hitl-prompt">
          Decision: ${inv.decision}\nConfidence: ${inv.confidence} (${inv.confidence_score})\nAmbiguity flagged for accountant confirmation.
        </div>
        <div class="inline-hitl-actions">
          <button class="btn btn-sm btn-approve" onclick="resolveInvoiceHitl('${inv.invoice_id}', 'APPROVE')">
            ✓ 1-Tap Approve & Post to Ledger
          </button>
          <button class="btn btn-sm btn-reject" onclick="resolveInvoiceHitl('${inv.invoice_id}', 'REJECT')">
            ✕ Reject / Flag Disputed
          </button>
        </div>
      </div>
    `;
  } else if (inv.status === 'HITL_APPROVED') {
    hitlActionHtml = `
      <div style="background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; padding:10px; margin-top:12px; font-size:11px; color:#34d399; font-weight:700;">
        ✓ Authorized and Reconciled by Suresh Bhat (Senior Accountant)
      </div>
    `;
  }

  // Gated email draft if present
  let emailDraftHtml = '';
  if (inv.status === 'ESCALATED_UNPAID') {
    emailDraftHtml = `
      <div class="inline-email-card">
        <div class="inline-email-header">
          <span>✉️ Gated Supplier Email Inquiry</span>
          <span style="font-size:10px; color:var(--accent-amber);">APPROVAL REQUIRED</span>
        </div>
        <div class="inline-email-body">To: ${inv.supplier_name} Billing Team\nSubject: Inquiry: Payment Status for ${inv.invoice_number} (₹${inv.total_amount.toLocaleString('en-IN')})\n\nDear Accounts Team,\nNo matching bank debit identified as of current reconciliation run.\nCould you please confirm the payment UTR / bank reference?\n\n- Accounts Department, Sri Krishna Electricals Manipal</div>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:11px; color:var(--accent-amber); font-weight:600;">🔒 Safety Lock Active</span>
          <button class="btn btn-sm btn-accent" onclick="dispatchDirectEmail('${inv.invoice_id}')">
            Authorize & Dispatch Email
          </button>
        </div>
      </div>
    `;
  }

  // Tool calls chips
  let toolChipsHtml = '';
  if (inv.tool_calls && inv.tool_calls.length > 0) {
    toolChipsHtml = `
      <div style="margin-top:14px;">
        <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px;">
          Tools Executed (${inv.tool_calls.length})
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:6px;">
          ${inv.tool_calls.map(tc => `<span style="font-size:10px; font-family:var(--font-mono); background:var(--bg-accent); padding:3px 7px; border-radius:4px; border:1px solid var(--border); color:var(--accent-purple);">🛠️ ${tc.tool_name} (${tc.duration_ms}ms)</span>`).join('')}
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    <div class="inspector-top-row">
      <div>
        <div class="inspector-inv-title">${inv.invoice_number}</div>
        <div class="inspector-sup-name">${inv.supplier_name}</div>
        <div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">GSTIN: ${inv.supplier_gstin}</div>
      </div>
      <div class="inspector-amount-col">
        <div class="inspector-amt-val">₹${inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
        <div class="badge-row">
          <span class="status-pill ${inv.confidence === 'HIGH' ? 'auto' : 'hitl'}">${inv.confidence}</span>
          <span class="status-pill auto">${inv.status}</span>
        </div>
      </div>
    </div>

    ${bankMatchHtml}

    <div style="margin-top:12px;">
      <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.04em;">
        Multi-Step Agent Reasoning Trace
      </div>
      <div class="trace-timeline">
        ${traceHtml || '<div style="font-size:11px; color:var(--text-muted);">No trace recorded.</div>'}
      </div>
    </div>

    ${toolChipsHtml}
    ${hitlActionHtml}
    ${emailDraftHtml}
  `;
}

async function resolveInvoiceHitl(invoiceId, action) {
  try {
    // Find the task for this invoice
    const tasksRes = await fetch('/api/v1/hitl/tasks?status=');
    const tasks = await tasksRes.json();
    const task = tasks.find(t => t.invoice_id === invoiceId);

    if (task) {
      await fetch(`/api/v1/hitl/tasks/${task.task_id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action, reviewer: 'Suresh Bhat (Senior Accountant)', notes: 'Approved from Command Center' })
      });
      await refreshAll();
      selectInvoiceById(invoiceId);
    } else {
      alert('Task already resolved or not found.');
    }
  } catch (e) {
    console.error(e);
  }
}

async function dispatchDirectEmail(invoiceId) {
  try {
    const draftsRes = await fetch('/api/v1/email-drafts');
    const drafts = await draftsRes.json();
    const draft = drafts.find(d => d.invoice_id === invoiceId);

    if (draft) {
      await fetch(`/api/v1/email-drafts/${draft.draft_id}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ authorized_by: 'Suresh Bhat (Senior Accountant)' })
      });
      alert(`Email draft authorized and dispatched to ${draft.recipient_email}.`);
      await refreshAll();
      selectInvoiceById(invoiceId);
    }
  } catch (e) {
    console.error(e);
  }
}

// 3. Load HITL Review Queue Tab
async function loadHitlTasks() {
  try {
    const res = await fetch('/api/v1/hitl/tasks?status=');
    const tasks = await res.json();
    const pending = tasks.filter(t => t.status === 'PENDING');

    document.getElementById('hitlBadgeCount').innerText = pending.length;
    document.getElementById('telemetryHitl').innerText = `${pending.length} open`;

    const container = document.getElementById('hitlCardsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (tasks.length === 0) {
      container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted);">No pending human review tasks. All cases resolved!</div>`;
      return;
    }

    tasks.forEach(t => {
      const card = document.createElement('div');
      card.className = `hitl-card ${t.status === 'PENDING' ? 'pending' : 'approved'}`;

      const buttonsHtml = t.status === 'PENDING' ? `
        <div class="inline-hitl-actions">
          <button class="btn btn-sm btn-approve" onclick="resolveHitl('${t.task_id}', 'APPROVE')">✓ Approve & Post to Ledger</button>
          <button class="btn btn-sm btn-reject" onclick="resolveHitl('${t.task_id}', 'REJECT')">✕ Reject / Dispute</button>
        </div>
      ` : `<div style="font-size:11px; color:var(--accent-emerald); font-weight:700;">✓ Resolved (${t.status}) by ${t.resolved_by || 'Suresh Bhat'}</div>`;

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div style="font-size:14px; font-weight:700; color:var(--accent-amber);">${t.title}</div>
            <div style="font-size:11px; color:var(--text-muted);">Invoice: ${t.invoice_number} • ${t.supplier_name} (₹${t.total_amount.toLocaleString('en-IN')})</div>
          </div>
          <span class="status-pill ${t.status === 'PENDING' ? 'hitl' : 'auto'}">${t.status}</span>
        </div>
        <div class="inline-hitl-prompt">${t.prompt_text}</div>
        ${buttonsHtml}
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load HITL tasks', e);
  }
}

async function resolveHitl(taskId, action) {
  try {
    const res = await fetch(`/api/v1/hitl/tasks/${taskId}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, reviewer: 'Suresh Bhat (Senior Accountant)', notes: 'Approved via Console' })
    });
    if (res.ok) {
      await refreshAll();
    }
  } catch (e) {
    console.error(e);
  }
}

// 4. Load Outbox Tab
async function loadOutbox() {
  try {
    const res = await fetch('/api/v1/email-drafts');
    const drafts = await res.json();
    const held = drafts.filter(d => d.status === 'HELD_FOR_APPROVAL');
    document.getElementById('outboxBadgeCount').innerText = held.length;

    const container = document.getElementById('outboxCardsContainer');
    if (!container) return;
    container.innerHTML = '';

    if (drafts.length === 0) {
      container.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:var(--text-muted);">No drafted supplier emails in outbox.</div>`;
      return;
    }

    drafts.forEach(d => {
      const card = document.createElement('div');
      card.className = 'outbox-card';

      const actionHtml = d.status === 'HELD_FOR_APPROVAL' ? `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
          <span style="font-size:11px; color:var(--accent-amber); font-weight:600;">🔒 Mandatory Human Authorization Required</span>
          <button class="btn btn-sm btn-accent" onclick="dispatchEmail('${d.draft_id}')">Authorize & Dispatch Email</button>
        </div>
      ` : `<div style="font-size:11px; color:var(--accent-emerald); font-weight:700;">✓ Dispatched to ${d.recipient_email} by ${d.authorized_by}</div>`;

      card.innerHTML = `
        <div style="display:flex; justify-content:space-between;">
          <strong>Draft ID: ${d.draft_id}</strong>
          <span class="status-pill ${d.status === 'HELD_FOR_APPROVAL' ? 'hitl' : 'auto'}">${d.status}</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary);">
          <div><strong>To:</strong> ${d.recipient_email}</div>
          <div><strong>Subject:</strong> ${d.subject}</div>
        </div>
        <div class="inline-email-body">${d.body}</div>
        ${actionHtml}
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.error('Failed to load outbox', e);
  }
}

async function dispatchEmail(draftId) {
  try {
    const res = await fetch(`/api/v1/email-drafts/${draftId}/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ authorized_by: 'Suresh Bhat (Senior Accountant)' })
    });
    if (res.ok) {
      alert(`Email draft ${draftId} successfully dispatched to vendor.`);
      await loadOutbox();
    }
  } catch (e) {
    console.error(e);
  }
}

// 5. Tool Telemetry Rendering
function renderToolTelemetry(toolData) {
  const tbody = document.getElementById('toolTelemetryTableBody');
  if (!tbody || !toolData) return;
  tbody.innerHTML = '';

  for (const [toolName, stats] of Object.entries(toolData)) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${toolName}</strong></td>
      <td>${stats.invocations}</td>
      <td style="color:var(--accent-cyan);">${stats.avg_ms} ms</td>
      <td style="color:var(--accent-purple);">${stats.p95_ms} ms</td>
    `;
    tbody.appendChild(tr);
  }
}

async function loadMonitoring() {
  await refreshTelemetry();
  try {
    const res = await fetch('/metrics');
    const text = await res.text();
    const preview = document.getElementById('prometheusScrapePreview');
    if (preview) {
      preview.innerText = text.slice(0, 1500) + '\n\n... [Truncated for preview, click Full OpenMetrics Stream above]';
    }
  } catch (e) {
    console.warn('Could not load /metrics text', e);
  }
}

// 6. Audit Logs Tab
async function loadAuditLogs() {
  try {
    const res = await fetch('/api/v1/audit/logs?limit=50');
    const logs = await res.json();
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    logs.forEach(l => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted);">${l.created_at}</td>
        <td><span style="font-family:var(--font-mono); color:var(--accent-cyan); font-size:11px;">${l.trace_id}</span></td>
        <td><span class="status-pill auto">${l.event_type}</span></td>
        <td><span style="font-family:var(--font-mono);">${l.actor}</span></td>
        <td>${l.entity_type} (${l.entity_id})</td>
        <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary); max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
          ${JSON.stringify(l.payload)}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.error('Failed to load audit logs', e);
  }
}

window.onload = initConsole;
