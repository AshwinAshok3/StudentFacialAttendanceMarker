/**
 * charts.js — Canvas-based chart rendering for Facial Attendance System.
 *
 * Pure canvas drawing, no external libraries.
 * Provides: circular progress, bar chart, line chart.
 */

// ---------------------------------------------------------------------------
// Circular Progress (Donut)
// ---------------------------------------------------------------------------

/**
 * Draw a circular progress ring on a canvas.
 *
 * @param {HTMLCanvasElement} canvas - Target canvas
 * @param {number} percentage - 0–100
 */
function drawCircularProgress(canvas, percentage) {
    if (!canvas) return;

    var ctx = canvas.getContext('2d');
    var size = canvas.width;
    var center = size / 2;
    var radius = center - 12;
    var lineWidth = 10;

    // Clear
    ctx.clearRect(0, 0, size, size);

    // Background ring
    ctx.beginPath();
    ctx.arc(center, center, radius, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = lineWidth;
    ctx.stroke();

    // Progress arc
    var startAngle = -Math.PI / 2;
    var endAngle = startAngle + (Math.PI * 2 * percentage / 100);

    // Gradient for the progress arc
    var gradient = ctx.createLinearGradient(0, 0, size, size);
    gradient.addColorStop(0, '#667eea');
    gradient.addColorStop(1, '#764ba2');

    ctx.beginPath();
    ctx.arc(center, center, radius, startAngle, endAngle);
    ctx.strokeStyle = gradient;
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.stroke();
}

// ---------------------------------------------------------------------------
// Bar Chart
// ---------------------------------------------------------------------------

/**
 * Draw a bar chart showing weekly attendance.
 *
 * @param {HTMLCanvasElement} canvas - Target canvas
 * @param {Array} data - [{date: 'YYYY-MM-DD', count: N}, ...]
 */
function drawBarChart(canvas, data) {
    if (!canvas) return;

    var ctx = canvas.getContext('2d');
    var width = canvas.offsetWidth || 400;
    var height = canvas.offsetHeight || 250;

    // Set actual pixel size
    canvas.width = width * 2;
    canvas.height = height * 2;
    ctx.scale(2, 2); // HiDPI

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Padding
    var padLeft = 40;
    var padRight = 20;
    var padTop = 20;
    var padBottom = 40;
    var chartW = width - padLeft - padRight;
    var chartH = height - padTop - padBottom;

    // Fill last 7 days, even if no data
    var days = [];
    var dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    for (var i = 6; i >= 0; i--) {
        var d = new Date();
        d.setDate(d.getDate() - i);
        var key = d.toISOString().split('T')[0];
        var match = data.find(function (item) { return item.date === key; });
        days.push({
            label: dayNames[d.getDay()],
            value: match ? match.count : 0,
        });
    }

    var maxVal = Math.max.apply(null, days.map(function (d) { return d.value; }));
    if (maxVal === 0) maxVal = 5; // Avoid division by 0

    var barWidth = (chartW / days.length) * 0.6;
    var gap = (chartW / days.length) * 0.4;

    // Y-axis labels
    ctx.fillStyle = '#9898b0';
    ctx.font = '11px Segoe UI, system-ui, sans-serif';
    ctx.textAlign = 'right';

    for (var j = 0; j <= 4; j++) {
        var yVal = Math.round(maxVal * j / 4);
        var yPos = padTop + chartH - (chartH * j / 4);
        ctx.fillText(yVal.toString(), padLeft - 8, yPos + 4);

        // Grid line
        ctx.beginPath();
        ctx.moveTo(padLeft, yPos);
        ctx.lineTo(padLeft + chartW, yPos);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // Bars
    days.forEach(function (day, idx) {
        var x = padLeft + idx * (barWidth + gap) + gap / 2;
        var barH = maxVal > 0 ? (day.value / maxVal) * chartH : 0;
        var y = padTop + chartH - barH;

        // Bar gradient
        var grad = ctx.createLinearGradient(x, y, x, padTop + chartH);
        grad.addColorStop(0, '#667eea');
        grad.addColorStop(1, '#764ba2');

        ctx.fillStyle = grad;
        ctx.beginPath();
        roundRect(ctx, x, y, barWidth, barH, 4);
        ctx.fill();

        // X-axis label
        ctx.fillStyle = '#9898b0';
        ctx.font = '11px Segoe UI, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(day.label, x + barWidth / 2, padTop + chartH + 20);

        // Value on top of bar
        if (day.value > 0) {
            ctx.fillStyle = '#e8e8f0';
            ctx.fillText(day.value.toString(), x + barWidth / 2, y - 6);
        }
    });
}

// ---------------------------------------------------------------------------
// Line Chart
// ---------------------------------------------------------------------------

/**
 * Draw a line chart for attendance trends.
 *
 * @param {HTMLCanvasElement} canvas - Target canvas
 * @param {Array} data - [{label, value}, ...]
 */
function drawLineChart(canvas, data) {
    if (!canvas || !data || data.length === 0) return;

    var ctx = canvas.getContext('2d');
    var width = canvas.offsetWidth || 400;
    var height = canvas.offsetHeight || 250;

    canvas.width = width * 2;
    canvas.height = height * 2;
    ctx.scale(2, 2);

    ctx.clearRect(0, 0, width, height);

    var padLeft = 40;
    var padRight = 20;
    var padTop = 20;
    var padBottom = 40;
    var chartW = width - padLeft - padRight;
    var chartH = height - padTop - padBottom;

    var maxVal = Math.max.apply(null, data.map(function (d) { return d.value; }));
    if (maxVal === 0) maxVal = 5;

    var stepX = chartW / Math.max(data.length - 1, 1);

    // Grid
    for (var j = 0; j <= 4; j++) {
        var yPos = padTop + chartH - (chartH * j / 4);
        ctx.beginPath();
        ctx.moveTo(padLeft, yPos);
        ctx.lineTo(padLeft + chartW, yPos);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // Line
    var gradient = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
    gradient.addColorStop(0, '#667eea');
    gradient.addColorStop(1, '#764ba2');

    ctx.beginPath();
    ctx.strokeStyle = gradient;
    ctx.lineWidth = 2.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    var points = [];
    data.forEach(function (item, idx) {
        var x = padLeft + idx * stepX;
        var y = padTop + chartH - (item.value / maxVal * chartH);
        points.push({ x: x, y: y });

        if (idx === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    ctx.stroke();

    // Area fill
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    points.forEach(function (p) { ctx.lineTo(p.x, p.y); });
    ctx.lineTo(points[points.length - 1].x, padTop + chartH);
    ctx.lineTo(points[0].x, padTop + chartH);
    ctx.closePath();

    var areaGrad = ctx.createLinearGradient(0, padTop, 0, padTop + chartH);
    areaGrad.addColorStop(0, 'rgba(102, 126, 234, 0.2)');
    areaGrad.addColorStop(1, 'rgba(102, 126, 234, 0)');
    ctx.fillStyle = areaGrad;
    ctx.fill();

    // Dots
    points.forEach(function (p) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#667eea';
        ctx.fill();
        ctx.strokeStyle = '#0f0f1a';
        ctx.lineWidth = 2;
        ctx.stroke();
    });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Draw a rounded rectangle path.
 */
function roundRect(ctx, x, y, w, h, r) {
    if (h <= 0) return;
    r = Math.min(r, h / 2, w / 2);
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
}
