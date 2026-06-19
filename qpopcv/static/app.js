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
  metricsData: { all_time: null, today: null },
  metricsPeriod: 'all',
  watchTimerInterval: null,
  watchTimerSeconds: 0,
  watchTimerPaused: false,
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const statusPill    = $('status-pill');
const statusText    = $('status-text');
const userIdInput   = $('user-id');
const eyeBtn        = $('eye-btn');
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
const discordWarn        = $('discord-warn');
const discordContinueBtn = $('discord-continue-btn');
const watchTimer        = $('watch-timer');
const watchTimerValue   = $('watch-timer-value');
const watchTimerPaused  = $('watch-timer-paused');
const afkBanner         = $('afk-banner');
const afkResetBtn       = $('afk-reset-btn');

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

// ── Eye-toggle (User ID) ──────────────────────────────────────────────────────

(function () {
  let eyeTimer = null;

  function hideUserId() {
    userIdInput.type = 'password';
    eyeBtn.classList.remove('is-visible');
    eyeTimer = null;
  }

  eyeBtn.addEventListener('click', () => {
    clearTimeout(eyeTimer);
    userIdInput.type = 'text';
    eyeBtn.classList.add('is-visible');
    eyeTimer = setTimeout(hideUserId, 5000);
  });
})();

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
    case 'afk_warning':
      onAfkWarning();
      break;
    case 'afk_logout':
      onAfkLogout();
      break;
    case 'afk_reset':
      onAfkReset();
      break;
    case 'metrics_update':
      onMetricsUpdate(event);
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

  userIdInput.value  = config.user_id || '';

  refList.innerHTML = '';
  const paths = config.reference_image_paths || [];
  (paths.length ? paths : ['']).forEach(p => addRefRow(p));
  refreshAddBtn();

  // Fit window to content after everything is laid out
  measureAndResize();

  if (data.metrics) {
    state.metricsData = data.metrics;
    renderMetrics();
  }
}

// ── Height adaptation ──────────────────────────────────────────────────────────

function measureAndResize() {
  requestAnimationFrame(() => {
    const card = document.querySelector('.app-card');
    const h = card ? card.offsetHeight : document.documentElement.scrollHeight;
    fetch('/api/resize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ height: h }),
    }).catch(() => {});
  });
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
  statusText.textContent = { idle: 'Stopped', watching: 'Watching', detected: 'Detected!', afk: 'AFK Warning' }[stateVal] || stateVal;
}

// ── Detection callback ─────────────────────────────────────────────────────────

function onDetected() {
  state.watching = false;
  stopWatchTimer();
  afkBanner.classList.add('hidden');
  watchBtn.classList.remove('is-watching');
  watchBtnIcon.textContent = '▶';
  watchBtnText.textContent = 'Watch';
  setStatus('detected');

  const overlay = document.createElement('div');
  overlay.className = 'detected-overlay';
  document.body.appendChild(overlay);
  overlay.addEventListener('animationend', () => overlay.remove(), { once: true });
}

// ── Watch timer ────────────────────────────────────────────────────────────────

function formatHMS(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return String(h).padStart(2, '0') + ':' +
         String(m).padStart(2, '0') + ':' +
         String(s).padStart(2, '0');
}

function startWatchTimer() {
  state.watchTimerSeconds = 0;
  state.watchTimerPaused = false;
  watchTimerValue.textContent = '00:00:00';
  watchTimer.classList.remove('hidden', 'is-paused');
  watchTimerPaused.classList.add('hidden');

  state.watchTimerInterval = setInterval(() => {
    if (!state.watchTimerPaused) {
      state.watchTimerSeconds++;
      watchTimerValue.textContent = formatHMS(state.watchTimerSeconds);
    }
  }, 1000);
  measureAndResize();
}

function stopWatchTimer() {
  if (state.watchTimerInterval) {
    clearInterval(state.watchTimerInterval);
    state.watchTimerInterval = null;
  }
  watchTimer.classList.add('hidden');
  watchTimer.classList.remove('is-paused');
  watchTimerPaused.classList.add('hidden');
  state.watchTimerPaused = false;
  measureAndResize();
}

function pauseWatchTimer() {
  state.watchTimerPaused = true;
  watchTimer.classList.add('is-paused');
  watchTimerPaused.classList.remove('hidden');
}

function resumeWatchTimer() {
  state.watchTimerPaused = false;
  watchTimer.classList.remove('is-paused');
  watchTimerPaused.classList.add('hidden');
}

// ── AFK banner ─────────────────────────────────────────────────────────────────

function onAfkWarning() {
  afkBanner.classList.remove('hidden');
  pauseWatchTimer();
  statusPill.dataset.state = 'afk';
  statusText.textContent = 'AFK Warning';
  measureAndResize();
}

function onAfkLogout() {
  state.watching = false;
  stopWatchTimer();
  afkBanner.classList.add('hidden');
  watchBtn.classList.remove('is-watching');
  watchBtnIcon.textContent = '▶';
  watchBtnText.textContent = 'Watch';
  setStatus('idle');
  measureAndResize();
}

function onAfkReset() {
  afkBanner.classList.add('hidden');
  resumeWatchTimer();
  setStatus('watching');
  measureAndResize();
}

afkResetBtn.addEventListener('click', async () => {
  afkResetBtn.disabled = true;
  try {
    const result = await apiPost('/api/reset_afk');
    if (!result.ok) {
      showToast('error', result.error || 'Reset failed.');
    }
  } catch (e) {
    showToast('error', 'Reset request failed.');
  } finally {
    afkResetBtn.disabled = false;
  }
});

// ── Metrics tab ────────────────────────────────────────────────────────────────

function formatDuration(totalSeconds) {
  if (totalSeconds <= 0) return '0m';
  const d = Math.floor(totalSeconds / 86400);
  const h = Math.floor((totalSeconds % 86400) / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function renderMetrics() {
  const data = state.metricsPeriod === 'all'
    ? state.metricsData.all_time
    : state.metricsData.today;
  if (!data) return;

  $('metric-total-time-val').textContent = formatDuration(data.total_time_saved);
  $('metric-effective-time-val').textContent = formatDuration(data.effective_time_saved);
  $('metric-pops-val').textContent = String(data.pops_detected);
  $('metric-avg-wait-val').textContent = formatDuration(data.avg_queue_wait);
  $('metric-longest-val').textContent = formatDuration(data.longest_session);
}

function onMetricsUpdate(event) {
  state.metricsData.all_time = event.all_time || state.metricsData.all_time;
  state.metricsData.today = event.today || state.metricsData.today;
  renderMetrics();
}

document.querySelectorAll('.metrics-toggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.metrics-toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.metricsPeriod = btn.dataset.period;
    renderMetrics();
  });
});

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


discordContinueBtn.addEventListener('click', async () => {
  discordWarn.classList.add('hidden');
  measureAndResize();
  await doStartWatch(true);
});

async function doStartWatch(skipDiscordCheck = false) {
  watchBtn.disabled = true;
  try {
    const data = { ...collectFormData(), skip_discord_check: skipDiscordCheck };
    const result = await apiPost('/api/start_watch', data);
    if (result.discord_running) {
      discordWarn.classList.remove('hidden');
      measureAndResize();
      return;
    }
    if (!result.ok) {
      showToast('error', result.error);
      return;
    }
    discordWarn.classList.add('hidden');
    measureAndResize();
    if (result.warning) {
      showToast('warning', result.warning, 7000);
    }
    state.watching = true;
    startWatchTimer();
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
    stopWatchTimer();
    afkBanner.classList.add('hidden');
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
