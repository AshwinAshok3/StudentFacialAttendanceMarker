# Student Facial Attendance Marker (SFAM)

A production-grade offline biometric attendance system with GPU-accelerated face recognition.

## Architecture

```
Client (HTML/CSS/JS)  →  HTTP/JSON  →  Flask Server (:5000)
     getUserMedia()                       ├── InsightFace (GPU/CPU)
     fetch() API calls                    ├── SQLite Database
     Canvas charts                        └── REST API
```

## Quick Start

### Windows
```batch
cd windows
setup.bat        # Install dependencies, detect GPU, download models
run.bat          # Start server → opens http://localhost:5000
```

### macOS
```bash
cd macos
chmod +x setup.sh run.sh
./setup.sh       # Install dependencies, detect MPS/CPU, download models
./run.sh         # Start server → opens http://localhost:5000
```

## Default Admin Login
- **Email:** `admin@system.local`
- **Password:** `admin123`

## Project Structure

```
├── windows/                  # Windows platform
│   ├── setup.bat             # Automated setup (venv, GPU, models)
│   ├── run.bat               # Start server
│   ├── requirements.txt      # Python dependencies
│   ├── backend/              # Flask REST API
│   │   ├── app.py            # Entry point
│   │   ├── routes.py         # API endpoints
│   │   ├── recognition.py    # InsightFace integration
│   │   ├── database.py       # SQLite operations
│   │   ├── auth.py           # Authentication
│   │   ├── utils.py          # Helpers
│   │   └── config.py         # Configuration
│   ├── frontend/             # Static HTML/CSS/JS
│   │   ├── index.html        # Login page
│   │   ├── register.html     # Registration + face capture
│   │   ├── dashboard.html    # Student dashboard
│   │   ├── admin.html        # Admin panel
│   │   ├── css/style.css     # Design system
│   │   └── js/               # Modules (api, camera, charts, app)
│   └── models/               # InsightFace models (auto-downloaded)
│
└── macos/                    # macOS platform (same structure)
```

## Features

- **Face Recognition** — InsightFace `buffalo_l` with GPU acceleration
- **Multi-role Auth** — Admin, Staff, Student logins
- **Registration** — 5-second video capture → averaged face embedding
- **Dashboard** — Attendance %, hours, charts, course info
- **Multi-face** — Handles known + unknown faces intelligently
- **Fully Offline** — No CDN, no cloud, all assets local
- **GPU Accelerated** — CUDA (Windows), MPS (macOS), CPU fallback

## GPU Support

| Platform | GPU | Fallback |
|----------|-----|----------|
| Windows | NVIDIA CUDA (RTX/GTX) | CPU |
| macOS (Apple Silicon) | MPS (Metal) | CPU |
| macOS (Intel) | — | CPU |

## Tech Stack

- **Frontend:** HTML5, CSS3, Vanilla JavaScript
- **Backend:** Python 3.10+, Flask
- **Database:** SQLite (local file)
- **ML:** InsightFace, ONNX Runtime, OpenCV
- **GPU:** PyTorch CUDA / MPS, ONNX Runtime GPU
