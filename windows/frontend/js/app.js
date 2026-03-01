/**
 * app.js — Core application logic for Facial Attendance System.
 *
 * Session management (localStorage), toast notifications,
 * form validation, page routing helpers.
 * No external dependencies.
 */

// ---------------------------------------------------------------------------
// Session Management
// ---------------------------------------------------------------------------

/**
 * Save auth session to localStorage.
 */
function saveSession(token, user) {
    localStorage.setItem('sfam_token', token);
    localStorage.setItem('sfam_user', JSON.stringify(user));
}

/**
 * Get the current session user object, or null if not logged in.
 */
function getSession() {
    var userStr = localStorage.getItem('sfam_user');
    if (!userStr) return null;
    try {
        return JSON.parse(userStr);
    } catch (e) {
        return null;
    }
}

/**
 * Get the current auth token, or null.
 */
function getToken() {
    return localStorage.getItem('sfam_token');
}

/**
 * Clear session data and token.
 */
function clearSession() {
    localStorage.removeItem('sfam_token');
    localStorage.removeItem('sfam_user');
}

/**
 * Logout: clear session and redirect to login.
 */
function logout() {
    clearSession();
    window.location.href = 'index.html';
}

/**
 * Redirect to the appropriate dashboard based on role.
 */
function redirectToDashboard(role) {
    if (role === 'admin' || role === 'staff') {
        window.location.href = 'admin.html';
    } else {
        window.location.href = 'dashboard.html';
    }
}

// ---------------------------------------------------------------------------
// Toast Notifications
// ---------------------------------------------------------------------------

var _toastCounter = 0;

/**
 * Show a toast notification.
 *
 * @param {string} message - The message to display
 * @param {string} type - 'success', 'error', 'warning', or 'info'
 * @param {number} duration - Auto-dismiss duration in ms (default: 4000)
 */
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = document.getElementById('toastContainer');
    if (!container) return;

    var id = 'toast-' + (++_toastCounter);

    var icons = {
        success: '✓',
        error: '✗',
        warning: '⚠',
        info: 'ℹ',
    };

    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.id = id;
    toast.innerHTML =
        '<span class="toast-icon">' + (icons[type] || 'ℹ') + '</span>' +
        '<span class="toast-message">' + escapeHtml(message) + '</span>' +
        '<button class="toast-close" onclick="dismissToast(\'' + id + '\')">&times;</button>';

    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(function () {
        dismissToast(id);
    }, duration);
}

/**
 * Dismiss a toast by ID.
 */
function dismissToast(id) {
    var toast = document.getElementById(id);
    if (toast) {
        toast.style.animation = 'slideIn 0.3s ease-out reverse';
        toast.style.opacity = '0';
        setTimeout(function () {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }
}

// ---------------------------------------------------------------------------
// Utility Helpers
// ---------------------------------------------------------------------------

/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

/**
 * Format a date string for display.
 */
function formatDate(dateStr) {
    try {
        var d = new Date(dateStr);
        return d.toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric'
        });
    } catch (e) {
        return dateStr;
    }
}

/**
 * Format a time string for display.
 */
function formatTime(dateStr) {
    try {
        var d = new Date(dateStr);
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit', minute: '2-digit'
        });
    } catch (e) {
        return dateStr;
    }
}
