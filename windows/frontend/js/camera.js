/**
 * camera.js — getUserMedia camera module for Facial Attendance System.
 *
 * Handles camera start/stop, frame capture to base64, and recording.
 * No external dependencies.
 */

var _currentStream = null;
var _currentVideo = null;
var _captureCanvas = null;
var _captureCtx = null;

// ---------------------------------------------------------------------------
// Camera Start / Stop
// ---------------------------------------------------------------------------

/**
 * Start the camera and attach the stream to a <video> element.
 * Prefers front-facing camera. Returns a Promise.
 */
function startCamera(videoElement) {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error('[Camera] getUserMedia not supported');
        if (typeof showToast === 'function') {
            showToast('Camera not supported in this browser', 'error');
        }
        return Promise.reject(new Error('getUserMedia not supported'));
    }

    var constraints = {
        video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 480 },
        },
        audio: false,
    };

    return navigator.mediaDevices.getUserMedia(constraints)
        .then(function (stream) {
            _currentStream = stream;
            _currentVideo = videoElement;
            videoElement.srcObject = stream;
            videoElement.play();
            console.log('[Camera] Started successfully');
        })
        .catch(function (err) {
            console.error('[Camera] Start failed:', err);
            if (typeof showToast === 'function') {
                showToast('Camera access denied. Please allow camera permissions.', 'error');
            }
            throw err;
        });
}

/**
 * Stop the camera and release all tracks.
 */
function stopCamera() {
    if (_currentStream) {
        _currentStream.getTracks().forEach(function (track) {
            track.stop();
        });
        _currentStream = null;
    }

    if (_currentVideo) {
        _currentVideo.srcObject = null;
        _currentVideo = null;
    }

    console.log('[Camera] Stopped');
}

// ---------------------------------------------------------------------------
// Frame Capture
// ---------------------------------------------------------------------------

/**
 * Capture a single frame from a <video> element as a base64 JPEG string.
 * Returns base64 string or null on failure.
 */
function captureFrame(videoElement) {
    if (!videoElement || videoElement.readyState < 2) {
        console.warn('[Camera] Video not ready for capture');
        return null;
    }

    // Create/reuse offscreen canvas
    if (!_captureCanvas) {
        _captureCanvas = document.createElement('canvas');
        _captureCtx = _captureCanvas.getContext('2d');
    }

    _captureCanvas.width = videoElement.videoWidth;
    _captureCanvas.height = videoElement.videoHeight;

    // Draw current video frame
    _captureCtx.drawImage(videoElement, 0, 0);

    // Encode as JPEG base64
    try {
        var dataUrl = _captureCanvas.toDataURL('image/jpeg', 0.85);
        return dataUrl;
    } catch (err) {
        console.error('[Camera] Capture failed:', err);
        return null;
    }
}

/**
 * Capture multiple frames over a duration.
 * Returns a Promise that resolves to an array of base64 strings.
 *
 * @param {HTMLVideoElement} videoElement - The video element to capture from
 * @param {number} durationMs - Total recording duration in milliseconds
 * @param {number} fps - Frames per second to capture (default: 3)
 */
function captureFrames(videoElement, durationMs, fps) {
    fps = fps || 3;
    var interval = Math.floor(1000 / fps);
    var frames = [];
    var elapsed = 0;

    return new Promise(function (resolve) {
        var timer = setInterval(function () {
            var frame = captureFrame(videoElement);
            if (frame) {
                frames.push(frame);
            }
            elapsed += interval;

            if (elapsed >= durationMs) {
                clearInterval(timer);
                resolve(frames);
            }
        }, interval);
    });
}

/**
 * Check if camera is currently active.
 */
function isCameraActive() {
    return _currentStream !== null &&
        _currentStream.getTracks().some(function (t) { return t.readyState === 'live'; });
}
