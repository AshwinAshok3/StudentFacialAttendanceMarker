/**
 * camera.js — Continuous scanning engine for SFAM (Student Facial Attendance Marker).
 *
 * P2 Fix: Per-user feedback cooldown — prevents toast/banner spam.
 * P5:     Renamed all "kiosk" terminology to "SFAM".
 * Design:
 *  - requestAnimationFrame loop (no setInterval drift)
 *  - Recognition throttled: 1 API call per FRAME_SKIP frames
 *  - Per-user feedback cooldown (FEEDBACK_COOLDOWN_MS)
 *  - Bounding boxes on canvas overlay (no oval)
 *  - Non-blocking alert banner (auto-fades in ALERT_DURATION_MS)
 */

const SFAMCamera = (() => {
    // -----------------------------------------------------------------------
    // Constants
    // -----------------------------------------------------------------------
    const FRAME_SKIP = 8;      // ~4 fps recognition at 30fps render
    const FEEDBACK_COOLDOWN_MS = 90000;  // 90s per-user "marked" toast cooldown
    const ALREADY_MARKED_MS = 30000;  // 30s "already marked" banner cooldown
    const ALERT_DURATION_MS = 5000;   // Alert banner auto-hides after 5s

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    let videoEl = null;
    let canvasEl = null;
    let ctx = null;
    let stream = null;
    let rafId = null;
    let running = false;
    let busy = false;
    let frameCount = 0;
    let lastResults = [];
    let lastAlert = null;
    let alertEl = null;

    // Per-user cooldown maps
    const feedbackCooldown = {};    // userId → timestamp (attendance marked toast)
    const alreadyCooldown = {};    // userId → timestamp (already marked banner)
    const unknownCooldown = { _last: 0 };  // global unknown alert throttle

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    async function start(videoId, canvasId, alertContainerId) {
        videoEl = document.getElementById(videoId);
        canvasEl = document.getElementById(canvasId);
        alertEl = document.getElementById(alertContainerId);

        if (!videoEl || !canvasEl) {
            console.error('SFAMCamera: video or canvas element not found');
            return false;
        }
        ctx = canvasEl.getContext('2d');

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
                audio: false,
            });
            videoEl.srcObject = stream;
            await videoEl.play();
            running = true;
            _loop();
            _updateStatus('active', 'Live — Scanning for faces');
            return true;
        } catch (err) {
            console.error('SFAMCamera start error:', err);
            _updateStatus('inactive', 'Camera access denied — check browser permissions');
            return false;
        }
    }

    function stop() {
        running = false;
        if (rafId) cancelAnimationFrame(rafId);
        if (stream) stream.getTracks().forEach(t => t.stop());
        stream = null;
        _updateStatus('inactive', 'Camera stopped');
    }

    /** Grab a single JPEG frame as bare base64. */
    function captureFrame(quality) {
        quality = quality || 0.85;
        if (!videoEl || !videoEl.videoWidth) return null;
        var tmp = document.createElement('canvas');
        tmp.width = videoEl.videoWidth;
        tmp.height = videoEl.videoHeight;
        tmp.getContext('2d').drawImage(videoEl, 0, 0);
        return tmp.toDataURL('image/jpeg', quality).split(',')[1];
    }

    // -----------------------------------------------------------------------
    // Core loop
    // -----------------------------------------------------------------------

    function _loop() {
        if (!running) return;
        rafId = requestAnimationFrame(_loop);

        if (canvasEl.width !== videoEl.videoWidth || canvasEl.height !== videoEl.videoHeight) {
            canvasEl.width = videoEl.videoWidth || canvasEl.offsetWidth;
            canvasEl.height = videoEl.videoHeight || canvasEl.offsetHeight;
        }

        _drawOverlay();

        if (busy) return;
        if (++frameCount % FRAME_SKIP !== 0) return;

        var frame = captureFrame(0.7);
        if (!frame) return;

        busy = true;
        apiKioskRecognize(frame)
            .then(_handleResults)
            .catch(function (err) { console.warn('SFAMCamera recognize error:', err); })
            .finally(function () { busy = false; });
    }

    // -----------------------------------------------------------------------
    // Result handling — P2: throttled per user
    // -----------------------------------------------------------------------

    function _handleResults(data) {
        if (!data || data.error) return;

        lastResults = data.known || [];
        var unknownCount = data.unknown_count || 0;
        var msg = data.message || '';
        var now = Date.now();

        lastResults.forEach(function (r) {
            var uid = r.user_id;

            if (r.attendance_marked) {
                // Newly marked — toast + banner, but throttled
                var last = feedbackCooldown[uid] || 0;
                if (now - last > FEEDBACK_COOLDOWN_MS) {
                    feedbackCooldown[uid] = now;
                    _showAlert('Attendance Marked Successfully — ' + r.name, 'success');
                    if (typeof showToast === 'function') {
                        showToast('✓ Attendance marked — ' + r.name, 'success', 3000);
                    }
                }
            } else {
                // Already marked — throttled banner only (no repeated toast)
                var alreadyLast = alreadyCooldown[uid] || 0;
                if (now - alreadyLast > ALREADY_MARKED_MS) {
                    alreadyCooldown[uid] = now;
                    _showAlert('Attendance Already Marked — ' + r.name, 'warning');
                }
            }
            _updateLastDetected(r.name, r.role);
        });

        // Unknown face alerts — globally throttled
        if (unknownCount > 0) {
            var timeSince = now - (unknownCooldown._last || 0);
            if (timeSince > FEEDBACK_COOLDOWN_MS) {
                unknownCooldown._last = now;
                if (msg === 'multi_unknown') {
                    _showAlert('Multiple unknown faces — please register individually', 'warning');
                } else if (msg === 'mixed') {
                    _showAlert('Unknown face detected in frame', 'warning');
                } else {
                    _showAlert('Unknown face detected', 'error');
                }
            }
        }
    }

    // -----------------------------------------------------------------------
    // Canvas overlay
    // -----------------------------------------------------------------------

    function _drawOverlay() {
        if (!ctx) return;
        ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
        if (!lastResults.length) return;

        var scaleX = canvasEl.width / (videoEl.videoWidth || canvasEl.width);
        var scaleY = canvasEl.height / (videoEl.videoHeight || canvasEl.height);

        lastResults.forEach(function (face) {
            if (!face.bbox) return;
            var x1 = face.bbox[0], y1 = face.bbox[1];
            var x2 = face.bbox[2], y2 = face.bbox[3];
            var rx = x1 * scaleX, ry = y1 * scaleY;
            var rw = (x2 - x1) * scaleX, rh = (y2 - y1) * scaleY;
            if (rw <= 0 || rh <= 0) return;

            ctx.strokeStyle = '#2dc653';
            ctx.lineWidth = 2.5;
            ctx.shadowColor = '#2dc65380';
            ctx.shadowBlur = 8;
            ctx.beginPath();
            ctx.roundRect(rx, ry, rw, rh, 6);
            ctx.stroke();
            ctx.shadowBlur = 0;

            var label = face.name || 'Recognized';
            ctx.font = 'bold 13px Inter, sans-serif';
            var tw = ctx.measureText(label).width;
            var px = 12;
            var lx = rx;
            var ly = ry > 32 ? ry - 30 : ry + rh + 6;

            ctx.fillStyle = 'rgba(45,198,83,0.9)';
            ctx.beginPath();
            ctx.roundRect(lx, ly, tw + px * 2, 24, 5);
            ctx.fill();

            ctx.fillStyle = '#fff';
            ctx.fillText(label, lx + px, ly + 17);
        });
    }

    // -----------------------------------------------------------------------
    // DOM helpers
    // -----------------------------------------------------------------------

    function _updateStatus(state, text) {
        var dot = document.getElementById('statusDot');
        var span = document.getElementById('statusText');
        if (dot) dot.className = 'status-dot ' + (state === 'active' ? '' : 'inactive');
        if (span) span.textContent = text;
    }

    function _updateLastDetected(name, role) {
        var el = document.getElementById('lastDetectedName');
        var et = document.getElementById('lastDetectedTime');
        if (el) el.textContent = name;
        if (et) et.textContent = new Date().toLocaleTimeString('en-IN', {
            hour: '2-digit', minute: '2-digit'
        }) + ' — ' + (role || 'student');
    }

    function _showAlert(message, type) {
        if (!alertEl) return;
        clearTimeout(lastAlert);
        alertEl.textContent = message;
        alertEl.className = 'kiosk-alert ' + (type || 'error');
        alertEl.style.display = 'block';
        lastAlert = setTimeout(function () {
            alertEl.style.display = 'none';
        }, ALERT_DURATION_MS);
    }

    return { start, stop, captureFrame };
})();

// Alias — old code can still use KioskCamera
var KioskCamera = SFAMCamera;


// =========================================================================
// RegCamera — N-frame capture for registration (P3 improved)
// =========================================================================

var RegCamera = (function () {
    var videoEl = null;
    var canvasEl = null;
    var stream = null;
    var rafId = null;
    var capturing = false;

    async function start(videoId, canvasId) {
        videoEl = document.getElementById(videoId);
        canvasEl = document.getElementById(canvasId);
        if (!videoEl || !canvasEl) return false;

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: false,
            });
            videoEl.srcObject = stream;
            videoEl.style.transform = 'scaleX(-1)';   // Mirror for selfie UX
            await videoEl.play();
            _drawLoop();
            return true;
        } catch (err) {
            console.error('RegCamera start error:', err);
            return false;
        }
    }

    function _drawLoop() {
        rafId = requestAnimationFrame(_drawLoop);
        if (canvasEl && videoEl && canvasEl.width !== videoEl.videoWidth) {
            canvasEl.width = videoEl.videoWidth || 640;
            canvasEl.height = videoEl.videoHeight || 480;
        }
    }

    /**
     * Capture `count` frames over `durationMs`.
     * P3: validates each frame is non-trivial, throws if <3 valid frames.
     */
    async function captureFrames(count, durationMs, progressCallback) {
        count = count || 10;
        durationMs = durationMs || 3500;

        if (!videoEl || !videoEl.videoWidth) {
            throw new Error('Camera not ready — video stream not initialized');
        }

        capturing = true;
        var frames = [];
        var interval = durationMs / count;

        for (var i = 0; i < count; i++) {
            if (!capturing) break;

            var tmp = document.createElement('canvas');
            tmp.width = videoEl.videoWidth;
            tmp.height = videoEl.videoHeight;
            var tmpCtx = tmp.getContext('2d');

            // Capture unmirrored (correct orientation for recognition)
            tmpCtx.save();
            tmpCtx.scale(-1, 1);
            tmpCtx.drawImage(videoEl, -tmp.width, 0);
            tmpCtx.restore();

            var b64 = tmp.toDataURL('image/jpeg', 0.85).split(',')[1];
            if (b64 && b64.length > 100) {
                frames.push(b64);
            }

            if (progressCallback) progressCallback(i + 1, count);
            if (i < count - 1) await _sleep(interval);
        }

        capturing = false;

        if (frames.length < 3) {
            throw new Error('Not enough valid frames — ensure your face is clearly visible and well-lit');
        }
        return frames;
    }

    function stop() {
        capturing = false;
        if (rafId) cancelAnimationFrame(rafId);
        if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
        stream = null;
        videoEl = null;
        canvasEl = null;
    }

    function _sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

    return { start, stop, captureFrames };
})();
