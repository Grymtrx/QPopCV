/* ═══════════════════════════════════════════════════════════════
   QPopCV — Frontend Logic
   JS → Python: fetch('/api/...')
   Python → JS: EventSource('/events') with SSE
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiGet(path) {
  const res = await fetch(path);
  return res.json();
}

async function apiPost(path, body = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

// ── State ─────────────────────────────────────────────────────────────────────

const state = {
  watching: false,
  monitors: [],
  updateClickable: false,
  MAX_REFS: 5,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const statusPill    = $('status-pill');
const statusText    = $('status-text');
const webhookInput  = $('webhook-url');
const userIdInput   = $('user-id');
const monitorSelect = $('monitor-select');
const refList       = $('ref-list');
const addImageBtn   = $('btn-add-image');
const watchBtn      = $('watch-btn');
const watchBtnIcon  = watchBtn.querySelector('.watch-btn-icon');
const watchBtnText  = watchBtn.querySelector('.watch-btn-text');
const versionText   = $('version-text');
const updateText    = $('update-text');
const toastContainer = $('toasts');
const afkNotifyCheckbox = $('afk-notify');

// ── Window controls ───────────────────────────────────────────────────────────

document.getElementById('titlebar-drag').addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  // Fire-and-forget: localhost round-trip is ~1-5ms; button will still be held
  fetch('/api/window_control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'drag_start' }),
  }).catch(() => {});
});

document.getElementById('win-btn-min').addEventListener('click', () => {
  fetch('/api/window_control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'minimize' }),
  }).catch(() => {});
});

document.getElementById('win-btn-close').addEventListener('click', () => {
  fetch('/api/window_control', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'close' }),
  }).catch(() => {});
});

// ── Server-Sent Events ────────────────────────────────────────────────────────

function connectEvents() {
  const es = new EventSource('/events');
  es.onmessage = e => {
    try {
      const event = JSON.parse(e.data);
      handlePushEvent(event);
    } catch (_) {}
  };
  es.onerror = () => {
    // Reconnect after 2s on error
    es.close();
    setTimeout(connectEvents, 2000);
  };
}

function handlePushEvent(event) {
  switch (event.type) {
    case 'detected':
      onDetected();
      break;
    case 'update_status':
      onUpdateStatus(event);
      break;
    case 'update_progress':
      onUpdateProgress(event.state, event.error);
      break;
    case 'heartbeat':
      break;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

window.addEventListener('load', async () => {
  connectEvents();

  try {
    const data = await apiPost('/api/initial_state');
    applyInitialState(data);
  } catch (e) {
    console.error('initial_state failed:', e);
    showToast('error', 'Failed to load configuration.');
    return;
  }

  // Kick off update check (result comes back via SSE)
  apiPost('/api/check_updates').catch(() => {});
});

function applyInitialState(data) {
  const { version, config, monitors } = data;

  versionText.textContent = `v${version}`;

  state.monitors = monitors;
  monitorSelect.innerHTML = '';
  monitors.forEach((label, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = label;
    monitorSelect.appendChild(opt);
  });
  monitorSelect.value = config.monitor_index;
  afkNotifyCheckbox.checked = !!config.afk_notify;

  webhookInput.value = config.webhook_url || '';
  userIdInput.value  = config.user_id || '';

  refList.innerHTML = '';
  const paths = config.reference_image_paths || [];
  (paths.length ? paths : ['']).forEach(p => addRefRow(p));
  refreshAddBtn();

  // Fit window to content after everything is laid out
  requestAnimationFrame(() => measureAndResize());
}

// ── Height adaptation ──────────────────────────────────────────────────────────

function measureAndResize() {
  const h = document.documentElement.scrollHeight;
  fetch('/api/resize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ height: h }),
  }).catch(() => {});
}

// ── Tab switching ──────────────────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const name = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`tab-${name}`).classList.add('active');
    measureAndResize();
  });
});

// ── Status management ──────────────────────────────────────────────────────────

function setStatus(stateVal) {
  statusPill.dataset.state = stateVal;
  statusText.textContent = { idle: 'Stopped', watching: 'Watching', detected: 'Detected!' }[stateVal] || stateVal;
}

// ── Detection callback ─────────────────────────────────────────────────────────

function onDetected() {
  const prev = statusPill.dataset.state;
  setStatus('detected');

  const overlay = document.createElement('div');
  overlay.className = 'detected-overlay';
  document.body.appendChild(overlay);
  overlay.addEventListener('animationend', () => overlay.remove(), { once: true });

  setTimeout(() => {
    if (statusPill.dataset.state === 'detected') setStatus(prev || 'watching');
  }, 1600);
}

// ── Update callbacks ───────────────────────────────────────────────────────────

function onUpdateStatus(data) {
  if (data.available && data.version) {
    updateText.textContent = `Update available: ${data.version}`;
    updateText.classList.add('is-clickable');
    state.updateClickable = true;
  } else {
    updateText.textContent = 'Up to date';
    updateText.classList.remove('is-clickable');
    state.updateClickable = false;
  }
}

function onUpdateProgress(progressState, errorMsg) {
  if (progressState === 'installed') {
    updateText.textContent = 'Installed — restarting…';
    showToast('success', 'Update installed! QPopCV is restarting.');
  } else if (progressState === 'failed') {
    updateText.textContent = 'Update failed';
    updateText.classList.add('is-clickable');
    state.updateClickable = true;
    showToast('error', errorMsg || 'Update failed. Please try again.');
  }
}

updateText.addEventListener('click', async () => {
  if (!state.updateClickable) return;
  if (!confirm('An update is available. Download and install now?\n\nThe app will restart automatically.')) return;

  updateText.textContent = 'Downloading…';
  updateText.classList.remove('is-clickable');
  state.updateClickable = false;

  try {
    const result = await apiPost('/api/install_update');
    if (!result.ok) {
      showToast('error', result.error || 'Could not start update.');
      updateText.textContent = 'Update failed';
      updateText.classList.add('is-clickable');
      state.updateClickable = true;
    }
  } catch (e) {
    showToast('error', 'Update request failed.');
  }
});

// ── Watch button ───────────────────────────────────────────────────────────────

watchBtn.addEventListener('click', async () => {
  if (state.watching) {
    await doStopWatch();
  } else {
    await doStartWatch();
  }
});

async function doStartWatch() {
  watchBtn.disabled = true;
  try {
    const result = await apiPost('/api/start_watch', collectFormData());
    if (!result.ok) {
      showToast('error', result.error);
      return;
    }
    if (result.warning) {
      showToast('warning', result.warning, 7000);
    }
    state.watching = true;
    setStatus('watching');
    watchBtn.classList.add('is-watching');
    watchBtnIcon.textContent = '■';
    watchBtnText.textContent = 'Stop';
  } catch (e) {
    showToast('error', 'Failed to start watcher.');
    console.error(e);
  } finally {
    watchBtn.disabled = false;
  }
}

async function doStopWatch() {
  watchBtn.disabled = true;
  try {
    await apiPost('/api/stop_watch');
    state.watching = false;
    setStatus('idle');
    watchBtn.classList.remove('is-watching');
    watchBtnIcon.textContent = '▶';
    watchBtnText.textContent = 'Watch';
  } catch (e) {
    showToast('error', 'Failed to stop watcher.');
    console.error(e);
  } finally {
    watchBtn.disabled = false;
  }
}

// ── Save config ────────────────────────────────────────────────────────────────

$('btn-save').addEventListener('click', async () => {
  const btn = $('btn-save');
  btn.textContent = 'Saving…';
  try {
    const result = await apiPost('/api/save_config', collectFormData());
    if (result.ok) {
      btn.textContent = 'Saved!';
      setTimeout(() => { btn.textContent = 'Save Configuration'; }, 1500);
    } else {
      btn.textContent = 'Save Configuration';
      showToast('error', result.error || 'Save failed.');
    }
  } catch (e) {
    btn.textContent = 'Save Configuration';
    showToast('error', 'Save request failed.');
  }
});

// ── Discord buttons ────────────────────────────────────────────────────────────

$('btn-test').addEventListener('click', async () => {
  const btn = $('btn-test');
  btn.disabled = true;
  btn.textContent = 'Testing…';
  try {
    const result = await apiPost('/api/test_discord', {
      webhook_url: webhookInput.value,
      user_id: userIdInput.value,
    });
    if (result.ok) {
      showToast('success', 'Test message sent successfully!');
    } else {
      showToast('error', result.error);
    }
  } catch (e) {
    showToast('error', 'Test request failed.');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test Connection';
  }
});

$('btn-discord').addEventListener('click', () => {
  apiPost('/api/open_discord').catch(() => {});
});

// ── Reference image rows ───────────────────────────────────────────────────────

addImageBtn.addEventListener('click', () => {
  addRefRow('');
  refreshAddBtn();
  measureAndResize();
});

function addRefRow(path) {
  if (refList.querySelectorAll('.ref-row').length >= state.MAX_REFS) return;

  const row = document.createElement('div');
  row.className = 'ref-row';

  const label = document.createElement('span');
  label.className = 'field-label';
  label.textContent = 'Ref Image';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'field-input';
  input.value = path || '';
  input.placeholder = 'Path to reference image…';
  input.spellcheck = false;

  const browseBtn = document.createElement('button');
  browseBtn.className = 'ref-btn';
  browseBtn.textContent = '…';
  browseBtn.title = 'Browse for image';
  browseBtn.addEventListener('click', async () => {
    browseBtn.disabled = true;
    try {
      const result = await apiPost('/api/browse_image');
      if (result && result.path) {
        input.value = result.path;
      }
    } finally {
      browseBtn.disabled = false;
    }
  });

  const removeBtn = document.createElement('button');
  removeBtn.className = 'ref-btn ref-btn-remove';
  removeBtn.textContent = '✕';
  removeBtn.title = 'Remove row';
  removeBtn.addEventListener('click', () => {
    row.remove();
    refreshRemoveBtns();
    refreshAddBtn();
    measureAndResize();
  });

  row.appendChild(label);
  row.appendChild(input);
  row.appendChild(browseBtn);
  row.appendChild(removeBtn);
  refList.appendChild(row);

  refreshRemoveBtns();
}

function refreshRemoveBtns() {
  const rows = refList.querySelectorAll('.ref-row');
  const onlyOne = rows.length <= 1;
  rows.forEach(row => {
    const btn = row.querySelector('.ref-btn-remove');
    if (btn) btn.disabled = onlyOne;
  });
}

function refreshAddBtn() {
  const count = refList.querySelectorAll('.ref-row').length;
  addImageBtn.classList.toggle('hidden', count >= state.MAX_REFS);
}

// ── Form data collection ───────────────────────────────────────────────────────

function collectFormData() {
  const paths = [];
  refList.querySelectorAll('.ref-row .field-input').forEach(inp => {
    const v = inp.value.trim();
    if (v) paths.push(v);
  });
  return {
    webhook_url: webhookInput.value.trim(),
    user_id: userIdInput.value.trim(),
    reference_image_paths: paths,
    monitor_index: parseInt(monitorSelect.value, 10) || 0,
    afk_notify: afkNotifyCheckbox.checked,
  };
}

// ── Toast system ───────────────────────────────────────────────────────────────

const TOAST_ICONS = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };

function showToast(type, message, duration = 4000) {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icon = document.createElement('span');
  icon.className = 'toast-icon';
  icon.textContent = TOAST_ICONS[type] || 'ℹ';

  const body = document.createElement('span');
  body.className = 'toast-body';
  body.textContent = message;

  toast.appendChild(icon);
  toast.appendChild(body);
  toastContainer.appendChild(toast);

  const dismiss = () => {
    toast.classList.add('toast-exiting');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  const timer = setTimeout(dismiss, duration);
  toast.addEventListener('click', () => { clearTimeout(timer); dismiss(); });
}
