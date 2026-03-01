/**
 * api.js — REST API client for Facial Attendance System.
 *
 * All functions return Promises that resolve to JSON responses.
 * Uses fetch() with auth token from localStorage.
 * No external dependencies.
 */

var API_BASE = '/api';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Make an authenticated API request.
 * Automatically attaches the Bearer token if present.
 */
function apiRequest(endpoint, options) {
    options = options || {};
    var url = API_BASE + endpoint;
    var headers = options.headers || {};

    // Attach auth token
    var token = localStorage.getItem('sfam_token');
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }

    // Default to JSON content type for POST
    if (options.method === 'POST' && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    return fetch(url, {
        method: options.method || 'GET',
        headers: headers,
        body: options.body || null,
    }).then(function (response) {
        // Handle 401 — force logout
        if (response.status === 401) {
            clearSession();
            window.location.href = 'index.html';
            return { error: 'Session expired. Please login again.' };
        }
        return response.json();
    }).catch(function (err) {
        console.error('[API] Request failed:', err);
        throw err;
    });
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

/**
 * Login with email and password.
 * Returns: { token, user: {id, name, email, role, department} }
 */
function apiLogin(email, password) {
    return apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email, password: password }),
    });
}

/**
 * Register a new student with face frames.
 * data: { name, email, department, password, frames: [base64...] }
 */
function apiRegister(data) {
    return apiRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

// ---------------------------------------------------------------------------
// Recognition API
// ---------------------------------------------------------------------------

/**
 * Send a frame for face recognition.
 * frame: base64 image string
 * Returns: { faces: [{bbox, matched, user_id, name, similarity}], message }
 */
function apiRecognize(frame) {
    return apiRequest('/recognize', {
        method: 'POST',
        body: JSON.stringify({ frame: frame }),
    });
}

// ---------------------------------------------------------------------------
// Attendance API
// ---------------------------------------------------------------------------

/**
 * Mark attendance for a recognized student.
 * Returns: { message, stats }
 */
function apiMarkAttendance(userId, courseId) {
    return apiRequest('/attendance/mark', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, course_id: courseId || null }),
    });
}

/**
 * Get attendance records for a student.
 * Returns: { records: [{id, timestamp, status, ...}] }
 */
function apiGetAttendance(userId, startDate, endDate) {
    var query = '';
    if (startDate) query += '?start=' + startDate;
    if (endDate) query += (query ? '&' : '?') + 'end=' + endDate;
    return apiRequest('/attendance/' + userId + query);
}

// ---------------------------------------------------------------------------
// Dashboard API
// ---------------------------------------------------------------------------

/**
 * Get dashboard data for a student.
 * Returns: { user, stats, weekly, courses }
 */
function apiGetDashboard(userId) {
    return apiRequest('/dashboard/' + userId);
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

/**
 * Get all registered students with their stats.
 * Returns: { students: [{id, name, email, department, stats}] }
 */
function apiGetStudents() {
    return apiRequest('/students');
}

/**
 * Get system information (GPU, model, OS).
 * Returns: { os, python_version, gpu_device, gpu_name, model_ready, ... }
 */
function apiGetSystemInfo() {
    return apiRequest('/system/info');
}
