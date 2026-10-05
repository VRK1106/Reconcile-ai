// Enterprise Operations & Observability Console Logic
let activeTab = 'tab-topology';
let invoicesList = [];
let pollingInterval = null;

async function initConsole() {
  setupTabs();
  setupDrawer();
  setupBatchButton();
  await refreshAll();

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

      if (activeTab === 'tab-ledger') loadLedger();
      if (activeTab === 'tab-hitl') loadHitlTasks();
      if (activeTab === 'tab-outbox') loadOutbox();
      if (activeTab === 'tab-monitoring') loadMonitoring();
      if (activeTab === 'tab-audit') loadAuditLogs();
    });
  });
}

function setupDrawer() {
  const closeBtn = document.getElementById('drawerCloseBtn');
  const overlay = document.getElementById('drawerOverlay');
  if (closeBtn) closeBtn.onclick = () => overlay.classList.add('hidden');
  if (overlay) {
    overlay.onclick = (e) => {
      if (e.target === overlay) overlay.classList.add('hidden');
    };
  }

  // Search & filter in ledger
  const searchInput = document.getElementById('ledgerSearchInput');
  const statusFilter = document.getElementById('ledgerStatusFilter');
  if (searchInput) searchInput.oninput = () => renderLedgerRows();
  if (statusFilter) statusFilter.onchange = () => renderLedgerRows();
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
    loadLedger(),
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

    // Monitoring Cards
    const totalEl = document.getElementById('statTotalInvoices');
    if (totalEl) totalEl.innerText = data.sla_performance.total_invoices_reconciled;

    const avgEl = document.getElementById('statAvgLatency');
    if (avgEl) avgEl.innerText = `${data.sla_performance.avg_latency_ms} ms`;

    const p95El = document.getElementById('statP95Latency');
    if (p95El) p95El.innerText = `${data.sla_performance.p95_latency_ms} ms`;

    const slaEl = document.getElementById('statSlaCompliance');
    if (slaEl) slaEl.innerText = `${data.sla_performance.sla_compliance_pct}%`;

    // Tool telemetry table
    renderToolTelemetry(data.tool_telemetry);
  } catch (e) {
    console.warn('Telemetry poll error', e);
  }
}

// 2. Load Ledger Table
async function loadLedger() {
  try {
    const res = await fetch('/api/v1/invoices?limit=100');
    const data = await res.json();
    invoicesList = data.invoices;
    renderLedgerRows();
    updateTopologyCounters();
  } catch (e) {
    console.error('Failed to load ledger', e);
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

function renderLedgerRows() {
  const tbody = document.getElementById('ledgerTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const q = (document.getElementById('ledgerSearchInput')?.value || '').toLowerCase();
  const sFilter = document.getElementById('ledgerStatusFilter')?.value || '';

  const filtered = invoicesList.filter(inv => {
    const matchesQ = inv.supplier_name.toLowerCase().includes(q) || inv.invoice_number.toLowerCase().includes(q);
    const matchesS = !sFilter || inv.status === sFilter;
    return matchesQ && matchesS;
  });

  filtered.forEach(inv => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.onclick = () => openDrawer(inv.invoice_id);

    let statusPillClass = 'auto';
    if (inv.status === 'HITL_PENDING') statusPillClass = 'hitl';
    else if (inv.status === 'HITL_APPROVED') statusPillClass = 'hitl-approved';
    else if (inv.status.includes('BLOCKED')) statusPillClass = 'blocked';
    else if (inv.status.includes('ESCALATED')) statusPillClass = 'escalated';

    tr.innerHTML = `
      <td><span class="trace-id-badge">${inv.trace_id || 'TRC-N/A'}</span></td>
      <td><strong>${inv.invoice_number}</strong><br><span style="font-size:10px; color:var(--text-muted);">${inv.invoice_date}</span></td>
      <td><div>${inv.supplier_name}</div><div style="font-family:var(--font-mono); font-size:10px; color:var(--text-muted);">${inv.supplier_gstin}</div></td>
      <td style="font-family:var(--font-mono); font-weight:700;">₹${inv.total_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
      <td style="font-family:var(--font-mono); color:var(--text-muted);">₹${inv.tax_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
      <td><span class="status-pill ${inv.confidence === 'HIGH' ? 'auto' : 'hitl'}">${inv.confidence}</span></td>
      <td><span class="status-pill ${statusPillClass}">${inv.status}</span></td>
      <td style="font-family:var(--font-mono); font-size:11px;">${inv.total_processing_ms || 1.2} ms</td>
      <td><button class="btn btn-sm" style="background:var(--bg-accent); color:var(--text-primary);" onclick="event.stopPropagation(); openDrawer('${inv.invoice_id}')">Inspect ↗</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// 3. Open Deep Dive Drawer
async function openDrawer(invoiceId) {
  try {
    const res = await fetch(`/api/v1/invoices/${invoiceId}`);
    if (!res.ok) return;
    const inv = await res.json();

    document.getElementById('drawerInvNumber').innerText = inv.invoice_number;
    document.getElementById('drawerSupplier').innerText = `${inv.supplier_name} (${inv.supplier_gstin})`;

    const tag = document.getElementById('drawerStatusTag');
    tag.innerText = inv.status;
    tag.className = `drawer-tag ${inv.status === 'AUTO_RECONCILED' ? 'status-pill auto' : 'status-pill hitl'}`;

    // Financials
    document.getElementById('drawerFinancials').innerHTML = `
      <div><span style="color:var(--text-muted)">Subtotal:</span> ₹${inv.subtotal.toLocaleString('en-IN')}</div>
      <div><span style="color:var(--text-muted)">Tax Amount:</span> ₹${inv.tax_amount.toLocaleString('en-IN')}</div>
      <div><span style="color:var(--text-muted)">Total Amount:</span> <strong>₹${inv.total_amount.toLocaleString('en-IN')}</strong></div>
      <div><span style="color:var(--text-muted)">Due Date:</span> ${inv.due_date || 'N/A'}</div>
      <div><span style="color:var(--text-muted)">Source:</span> ${inv.source}</div>
      <div><span style="color:var(--text-muted)">Trace ID:</span> ${inv.trace_id}</div>
    `;

    // Matched Bank Row
    const bankBox = document.getElementById('drawerBankMatch');
    if (inv.matched_bank_rows && inv.matched_bank_rows.length > 0) {
      const b = inv.matched_bank_rows[0];
      bankBox.innerHTML = `
        <div style="font-weight:700; color:var(--accent-emerald);">✓ Matched: ${b.txn_id} (${b.ref_no})</div>
        <div style="font-family:var(--font-mono); font-size:11px; margin-top:4px;">${b.narration}</div>
        <div style="margin-top:4px;">Date: ${b.txn_date} • Amount: ₹${b.amount.toLocaleString('en-IN')} • Status: ${b.reconciliation_status}</div>
      `;
    } else {
      bankBox.innerHTML = `<span style="color:var(--text-muted);">No matched bank debit row found. (Status: ${inv.status})</span>`;
    }

    // Reasoning Trace
    const traceStream = document.getElementById('drawerReasoningTrace');
    traceStream.innerHTML = inv.reasoning_trace.map(t => `<div class="trace-line">${t}</div>`).join('');

    // Tool calls
    const toolsStream = document.getElementById('drawerToolCalls');
    if (inv.tool_calls && inv.tool_calls.length > 0) {
      toolsStream.innerHTML = inv.tool_calls.map(tc => `
        <div class="tool-chip">
          <span>🛠️ ${tc.tool_name}</span>
          <span style="color:var(--accent-cyan);">${tc.duration_ms} ms</span>
        </div>
      `).join('');
    } else {
      toolsStream.innerHTML = `<span style="font-size:11px; color:var(--text-muted);">No tool calls (stopped at Layer 2 Guardrails).</span>`;
    }

    document.getElementById('drawerOverlay').classList.remove('hidden');
  } catch (e) {
    console.error('Drawer load failed', e);
  }
}

// 4. Load HITL Review Queue
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
      card.className = `hitl-card ${t.status !== 'PENDING' ? 'approved' : ''}`;

      const buttonsHtml = t.status === 'PENDING' ? `
        <div class="hitl-actions">
          <button class="btn btn-sm btn-approve" onclick="resolveHitl('${t.task_id}', 'APPROVE')">✓ Approve & Post</button>
          <button class="btn btn-sm btn-reject" onclick="resolveHitl('${t.task_id}', 'REJECT')">✕ Reject / Dispute</button>
        </div>
      ` : `<div style="font-size:11px; color:var(--accent-emerald); font-weight:700;">✓ Resolved (${t.status}) by ${t.resolved_by || 'Suresh Bhat'}</div>`;

      card.innerHTML = `
        <div class="hitl-card-header">
          <div>
            <div class="hitl-card-title">${t.title}</div>
            <div class="hitl-card-meta">Invoice: ${t.invoice_number} • ${t.supplier_name} (₹${t.total_amount.toLocaleString('en-IN')})</div>
          </div>
          <span class="status-pill ${t.status === 'PENDING' ? 'hitl' : 'auto'}">${t.status}</span>
        </div>
        <div class="hitl-card-prompt">${t.prompt_text}</div>
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
      body: JSON.stringify({ action: action, reviewer: 'Suresh Bhat (Senior Accountant)', notes: 'Approved via Enterprise Console' })
    });
    if (res.ok) {
      await refreshAll();
    }
  } catch (e) {
    console.error(e);
  }
}

// 5. Load Gated Outbox
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
        <div class="outbox-body">${d.body}</div>
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

// 6. Monitoring & Tool Latency
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

// 7. Load Audit Logs
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
        <td><span class="trace-id-badge">${l.trace_id}</span></td>
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
