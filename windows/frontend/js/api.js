/**
 * api.js — All fetch calls to the Flask backend.
 * No auth headers for kiosk and health endpoints.
 * All others send Bearer token from sessionStorage.
 */

const API_BASE = '';  // Same origin

// -------------------------------------------------------------------------
// Internal helpers
// -------------------------------------------------------------------------

function _authHeaders() {
    var session = getSession();
    var token = session ? session.token : null;
    return Object.assign(
        { 'Content-Type': 'application/json' },
        token ? { 'Authorization': 'Bearer ' + token } : {}
    );
}

async function _post(url, body, auth) {
    auth = (auth !== false);
    var res = await fetch(API_BASE + url, {
        method: 'POST',
        headers: auth ? _authHeaders() : { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json();
}

async function _get(url, params) {
    var qs = params ? ('?' + new URLSearchParams(params).toString()) : '';
    var res = await fetch(API_BASE + url + qs, { headers: _authHeaders() });
    return res.json();
}

async function _delete(url) {
    var res = await fetch(API_BASE + url, {
        method: 'DELETE',
        headers: _authHeaders(),
    });
    return res.json();
}

async function _patch(url, body) {
    var res = await fetch(API_BASE + url, {
        method: 'PATCH',
        headers: _authHeaders(),
        body: JSON.stringify(body),
    });
    return res.json();
}

// -------------------------------------------------------------------------
// P4: Health check — polled by loading screen
// -------------------------------------------------------------------------

async function apiHealthCheck() {
    var res = await fetch(API_BASE + '/api/health');
    return res.json();
}

// -------------------------------------------------------------------------
// Auth
// -------------------------------------------------------------------------

async function apiLogin(identifier, password, role) {
    return _post('/api/auth/login', { identifier: identifier, password: password, role: role || 'student' }, false);
}

async function apiRegisterStudent(data) {
    return _post('/api/auth/register/student', data, false);
}

async function apiRegisterStaff(data) {
    return _post('/api/auth/register/staff', data, false);
}

// -------------------------------------------------------------------------
// Kiosk (no auth)
// -------------------------------------------------------------------------

async function apiKioskRecognize(frameBase64) {
    return _post('/api/recognize/kiosk', { frame: frameBase64 }, false);
}

// -------------------------------------------------------------------------
// Student dashboard
// -------------------------------------------------------------------------

async function apiStudentDashboard(userId) {
    return _get('/api/dashboard/' + userId);
}

async function apiGetAttendance(userId, start, end) {
    var params = {};
    if (start) params.start = start;
    if (end) params.end = end;
    return _get('/api/attendance/' + userId, params);
}

// -------------------------------------------------------------------------
// Staff dashboard
// -------------------------------------------------------------------------

async function apiStaffDashboard(userId, date) {
    return _get('/api/dashboard/staff/' + userId, date ? { date: date } : null);
}

// -------------------------------------------------------------------------
// P1: Admin endpoints
// -------------------------------------------------------------------------

async function apiAdminListUsers(role) {
    return _get('/api/admin/users', (role && role !== 'all') ? { role: role } : null);
}

async function apiAdminDeleteUser(userId) {
    return _delete('/api/admin/users/' + userId + '/delete');
}

async function apiAdminEditUser(userId, fields) {
    return _patch('/api/admin/users/' + userId + '/edit', fields);
}

async function apiAdminAttendanceLogs(date, limit, offset) {
    var params = {};
    if (date) params.date = date;
    if (limit) params.limit = limit;
    if (offset) params.offset = offset;
    return _get('/api/admin/attendance/logs', params);
}

async function apiListStaff() {
    return _get('/api/staff');
}

// ---------- Backwards-compat aliases used by admin.html ----------

async function apiGetStudents() {
    return _get('/api/students');
}

async function apiMarkAttendance(userId, courseId) {
    return _post('/api/attendance/mark', { user_id: userId, course_id: courseId || null });
}

async function apiGetSystemInfo() {
    return _get('/api/system/info');
}
