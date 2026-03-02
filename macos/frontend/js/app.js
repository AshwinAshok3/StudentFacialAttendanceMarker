/**
 * app.js — Session management, routing helpers, toast notifications.
 */

// -------------------------------------------------------------------------
// roundRect polyfill — Chrome < 99, older WebViews don't have it natively
// -------------------------------------------------------------------------
if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
        var radius = Array.isArray(r) ? r[0] : (r || 0);
        radius = Math.min(radius, w / 2, h / 2);
        this.beginPath();
        this.moveTo(x + radius, y);
        this.lineTo(x + w - radius, y);
        this.quadraticCurveTo(x + w, y, x + w, y + radius);
        this.lineTo(x + w, y + h - radius);
        this.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
        this.lineTo(x + radius, y + h);
        this.quadraticCurveTo(x, y + h, x, y + h - radius);
        this.lineTo(x, y + radius);
        this.quadraticCurveTo(x, y, x + radius, y);
        this.closePath();
        return this;
    };
}

// -------------------------------------------------------------------------
// Session storage (sessionStorage — cleared on tab close)
// -------------------------------------------------------------------------

function saveSession(token, user) {
    sessionStorage.setItem('sfam_token', token);
    sessionStorage.setItem('sfam_user', JSON.stringify(user));
}

function getSession() {
    const token = sessionStorage.getItem('sfam_token');
    const user = sessionStorage.getItem('sfam_user');
    if (!token || !user) return null;
    try { return { token, user: JSON.parse(user) }; }
    catch { return null; }
}

function clearSession() {
    sessionStorage.removeItem('sfam_token');
    sessionStorage.removeItem('sfam_user');
}

// -------------------------------------------------------------------------
// Routing
// -------------------------------------------------------------------------

function redirectToDashboard(role) {
    if (role === 'staff' || role === 'admin') {
        window.location.href = 'staff.html';
    } else {
        window.location.href = 'dashboard.html';
    }
}

function requireAuth() {
    const s = getSession();
    if (!s) {
        window.location.href = 'login.html';
        return null;
    }
    return s;
}

function requireRole(role) {
    const s = requireAuth();
    if (!s) return null;
    if (s.user.role !== role && s.user.role !== 'admin') {
        window.location.href = 'index.html';
        return null;
    }
    return s;
}

// -------------------------------------------------------------------------
// Toast notifications
// -------------------------------------------------------------------------

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${message}`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 400);
    }, duration);
}

// -------------------------------------------------------------------------
// Chart helpers (no library — pure Canvas)
// -------------------------------------------------------------------------

/**
 * Draw a simple bar chart on a canvas element.
 * @param {HTMLCanvasElement} canvas
 * @param {string[]} labels
 * @param {number[]} values
 * @param {object} opts
 */
function drawBarChart(canvas, labels, values, opts = {}) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;
    const pad = opts.pad || { top: 20, right: 15, bottom: 35, left: 35 };
    const color = opts.color || '#00b4d8';
    const max = Math.max(...values, 1);

    ctx.clearRect(0, 0, W, H);

    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;
    const barW = Math.max(4, (chartW / labels.length) * 0.6);
    const gap = chartW / labels.length;

    // Y gridlines
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + chartH - (i / 4) * chartH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(Math.round((i / 4) * max), pad.left - 5, y + 3);
    }

    // Bars
    values.forEach((v, i) => {
        const x = pad.left + i * gap + gap / 2 - barW / 2;
        const bH = (v / max) * chartH;
        const y = pad.top + chartH - bH;

        const grad = ctx.createLinearGradient(0, y, 0, y + bH);
        grad.addColorStop(0, color);
        grad.addColorStop(1, color + '80');
        ctx.fillStyle = bH > 0 ? grad : 'transparent';
        ctx.beginPath();
        ctx.roundRect(x, y, barW, bH, [4, 4, 0, 0]);
        ctx.fill();

        // Label
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(labels[i], pad.left + i * gap + gap / 2, H - 8);
    });
}

/**
 * Draw a simple line chart on a canvas element.
 */
function drawLineChart(canvas, labels, values, opts = {}) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;
    const pad = opts.pad || { top: 20, right: 15, bottom: 35, left: 35 };
    const color = opts.color || '#2dc653';
    const max = Math.max(...values, 1);

    ctx.clearRect(0, 0, W, H);
    if (values.length < 2) return;

    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;
    const stepX = chartW / (values.length - 1);

    const xOf = (i) => pad.left + i * stepX;
    const yOf = (v) => pad.top + chartH - (v / max) * chartH;

    // Gridlines
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + chartH - (i / 4) * chartH;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();
    }

    // Fill under line
    const fill = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
    fill.addColorStop(0, color + '30');
    fill.addColorStop(1, color + '00');
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(values[0]));
    values.forEach((v, i) => { if (i > 0) ctx.lineTo(xOf(i), yOf(v)); });
    ctx.lineTo(xOf(values.length - 1), pad.top + chartH);
    ctx.lineTo(xOf(0), pad.top + chartH);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();

    // Line
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(values[0]));
    values.forEach((v, i) => { if (i > 0) ctx.lineTo(xOf(i), yOf(v)); });
    ctx.stroke();

    // Dots
    values.forEach((v, i) => {
        ctx.beginPath();
        ctx.arc(xOf(i), yOf(v), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
    });

    // X labels (show first, middle, last)
    const show = new Set([0, Math.floor(labels.length / 2), labels.length - 1]);
    labels.forEach((l, i) => {
        if (!show.has(i)) return;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(l, xOf(i), H - 8);
    });
}

/**
 * Draw an SVG ring chart for attendance %.
 */
function drawAttendanceRing(containerId, percentage) {
    const el = document.getElementById(containerId);
    if (!el) return;

    const r = 48;
    const cx = 60; const cy = 60;
    const circumference = 2 * Math.PI * r;
    const offset = circumference - (percentage / 100) * circumference;

    // Color based on percentage
    const color = percentage >= 75 ? '#2dc653' : percentage >= 50 ? '#f4a261' : '#e63946';

    el.innerHTML = `
    <svg viewBox="0 0 120 120" width="120" height="120">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
              stroke="#e2e8f0" stroke-width="10"/>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
              stroke="${color}" stroke-width="10"
              stroke-dasharray="${circumference}"
              stroke-dashoffset="${offset}"
              stroke-linecap="round"
              style="transition: stroke-dashoffset 1s ease; transform: rotate(-90deg); transform-origin: center;"/>
    </svg>
    <div class="attendance-ring-text">
      <span class="attendance-ring-pct">${percentage}%</span>
      <span class="attendance-ring-label">Attendance</span>
    </div>`;
}

// -------------------------------------------------------------------------
// Misc helpers
// -------------------------------------------------------------------------

function formatDate(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatTime(isoStr) {
    if (!isoStr) return '—';
    const d = new Date(isoStr);
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(isoStr) {
    return formatDate(isoStr) + ' ' + formatTime(isoStr);
}

function setLoading(btn, loading, label = 'Loading...') {
    if (loading) {
        btn._original = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner"></span> ${label}`;
    } else {
        btn.disabled = false;
        btn.innerHTML = btn._original || label;
    }
}
