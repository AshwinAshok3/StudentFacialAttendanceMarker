# StudentFacialAttendanceMarker — README

## Overview

A **fully offline** facial recognition attendance management system built with Python 3.10.5, InsightFace, OpenCV, Streamlit, and SQLite.  
Students are marked present automatically when their face is detected. Staff and Admin have role-based access to manage data.

---

## Folder Structure

```
StudentsFacialAttendanceMarker/
│
├── app/
│   ├── attendance_engine.py    # Core: detect → match → mark
│   ├── camera_feed.py          # Live Streamlit camera page
│   └── pages/
│       ├── landing.py          # Role selector
│       ├── student_view.py     # Student attendance history
│       ├── staff_view.py       # Staff login + management
│       ├── admin_view.py       # Admin full dashboard
│       └── register.py         # Multi-angle registration
│
├── auth/
│   └── auth_manager.py         # PBKDF2-SHA256 password hashing
│
├── database/
│   ├── db_manager.py           # SQLite ORM (main.db + admin.db)
│   ├── main.db                 # (auto-created on first run)
│   └── admin.db                # (auto-created on first run)
│
├── utils/
│   ├── face_utils.py           # InsightFace pipeline
│   ├── excel_utils.py          # Daily Excel file management
│   ├── camera.py               # Background camera thread
│   └── logger.py               # Rotating file + DB logger
│
├── attendance_records/
│   ├── YYYY-MM-DD.xlsx         # Daily attendance files (auto-generated)
│   └── photos/                 # Face snapshots at attendance time
│
├── models/
│   └── insightface/            # buffalo_l model files (auto-downloaded)
│
├── embeddings/                 # Reserved for future embedding exports
├── logs/
│   └── app.log                 # Rotating log file
├── static/css/                 # Custom CSS assets
│
├── main.py                     # Entry point
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Prerequisites
- Python 3.10.5
- Windows 10/11 or Ubuntu 20.04+
- A USB or built-in webcam

### 2. Create Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note on InsightFace model**: On first launch, insightface will automatically download the `buffalo_l` model (~360 MB) from the internet. After download, the system is fully offline. To pre-download manually:
> ```python
> from insightface.app import FaceAnalysis
> app = FaceAnalysis(name="buffalo_l", root="models/insightface")
> app.prepare(ctx_id=-1, det_size=(640, 640))
> ```

### 4. Run the Application
```bash
streamlit run main.py
```

The app opens at `http://localhost:8501` in your browser.

---

## Default Admin Credentials

| Field | Value |
|-------|-------|
| Username | `root` |
| Password | `passwd` |

> **You will be forced to change the password on first login.**

---

## Facial Recognition Pipeline

```
Camera Frame
    │
    ▼
CLAHE Lighting Normalisation
    │
    ▼
InsightFace Detection (buffalo_l, det_score > 0.85)
    │
    ▼
Quality Gate (min 60×60px face, embedding present)
    │
    ▼
512-dim L2-normalised Embedding Extraction
    │
    ▼
Cosine Similarity vs. All Stored Embeddings
    │
    ├─ Score ≥ 0.45 → Match Found
    │       ├─ Already marked today? → Yellow box "Already Marked"
    │       └─ Not marked? → Green box + Save to SQLite + Excel
    │
    └─ Score < 0.45 → Unknown
                    → Red box → [Register as Student / Staff]
```

### Threshold Tuning
- **0.45** — default (good balance for office lighting)
- **0.50** — stricter, fewer false positives, more missed detections
- **0.40** — lenient, useful for poor lighting conditions
- Edit `SIMILARITY_THRESHOLD` in `utils/face_utils.py`

---

## Role Permissions

| Feature | Student | Staff | Admin |
|---------|---------|-------|-------|
| View own attendance | ✅ | — | — |
| View student attendance | ❌ | ✅ | ✅ |
| Mark student as Late | ❌ | ✅ | ✅ |
| View student photos | ❌ | ✅ | ✅ |
| Full CRUD on records | ❌ | ❌ | ✅ |
| Manage users | ❌ | ❌ | ✅ |
| View system logs | ❌ | ❌ | ✅ |
| Export reports | ❌ | ❌ | ✅ |
| View analytics | ❌ | ❌ | ✅ |
| Reset passwords | ❌ | ❌ | ✅ |

---

## Security Design

- **Passwords**: PBKDF2-SHA256 with 260,000 iterations + 256-bit random salt
- **Timing attack prevention**: `secrets.compare_digest()` for hash comparison
- **Admin isolation**: Credentials stored in a **separate** `admin.db` file
- **No plaintext passwords** stored anywhere
- **SQL injection**: SQLite parameterised queries used throughout
- **Privilege separation**: Staff cannot access admin.db or admin routes

---

## Attendance Excel Files

Location: `attendance_records/YYYY-MM-DD.xlsx`  
Each file has 3 colour-coded sheets:

| Sheet | Colour | Contents |
|-------|--------|----------|
| Students | Blue | All student records |
| Staff | Green | All staff records |
| Admin | Brown | All admin records |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Camera not detected | Check device manager; try changing `camera_index=` in `utils/camera.py` |
| InsightFace import error | Run `pip install insightface onnxruntime` |
| Model download fails | Pre-download manually (see Quick Start step 3) |
| Low recognition accuracy | Register more angles; improve lighting; lower threshold to 0.40 |
| `main.db` locked | Restart app; ensure no other process is accessing the DB |

---

## Performance Notes

- **CPU only** — no GPU required; detection takes ~80–200ms per frame on modern CPU
- **Embedding cache** — refreshed once per day; eliminates DB reads per frame
- **In-memory duplicate guard** — `set()` of today's marked IDs prevents redundant DB queries
- **Camera buffer = 1** — minimal latency between capture and display
- **WAL mode** — SQLite Write-Ahead Logging enables concurrent reads
