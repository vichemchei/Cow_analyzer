# 🏗️ Project Structure & Organization

## Overview

HerdWatch is organized with a clean, modular architecture:

```
AT_Agrisolutiion/
├── 🔧 CORE APPLICATION FILES
│   ├── app.py                    ← Flask backend server (main entry point)
│   ├── video_analyzer.py         ← Video processing engine
│   ├── chat_interface.py         ← AI farmer chat system
│   ├── at.py                     ← Africa's Talking SMS integration
│
├── 🌐 FRONTEND
│   └── frontend/
│       ├── index.html            ← Main dashboard UI
│       ├── app.js                ← Frontend logic & API client
│       ├── style.css             ← Styling & responsive layout
│       ├── architecture.html     ← System architecture diagram
│       └── README.md             ← Frontend-specific docs
│
├── ⚙️ CONFIGURATION FILES
│   ├── .env                      ← Environment variables (NOT in git)
│   ├── .env.example              ← Template for .env
│   ├── requirements.txt          ← Python dependencies
│   ├── .gitignore               ← Git ignore rules
│
├── 📚 DOCUMENTATION
│   ├── README.md                 ← Project overview
│   ├── SETUP.md                  ← Installation guide
│   └── docs/
│       ├── ARCHITECTURE.md       ← System design & flow diagrams
│       └── PROJECT_STRUCTURE.md  ← This file
│
├── 📊 DATA & OUTPUT (gitignored)
│   ├── cow_analysis_data.json       ← Current herd state (shared)
│   ├── analysis_log.txt             ← Frame-by-frame analysis log
│   ├── chat_log.txt                 ← Chat interaction history
│   ├── response_cache.json          ← Cached AI responses
│   ├── gemini_responses.txt         ← Raw AI responses (debug)
│   └── current_frame.jpg            ← Latest video frame
│
├── 🧪 TESTING
│   └── tests/
│       └── test_chat.py         ← Chat interface unit tests
│
├── 📹 MEDIA (gitignored)
│   └── cow.mp4                   ← Video source file
│
├── .git/                         ← Git repository
└── .venv/                        ← Python virtual environment
```

---

## 📋 File-by-File Breakdown

### **Core Application**

| File | Purpose | Dependencies |
|------|---------|--------------|
| `app.py` | Flask backend server | Flask, CORS, chat_interface, at |
| `video_analyzer.py` | Real-time video analysis engine | OpenCV, Gemini API, LangChain |
| `chat_interface.py` | AI-powered chat for farmers | Gemini API, LangChain |
| `at.py` | SMS integration | Africa's Talking SDK |

### **Frontend**

| File | Purpose | Type |
|------|---------|------|
| `frontend/index.html` | Main UI dashboard | HTML5 |
| `frontend/app.js` | All client logic | JavaScript (ES6) |
| `frontend/style.css` | Complete styling | CSS3 |
| `frontend/architecture.html` | System diagram | HTML + SVG |
| `frontend/README.md` | Frontend docs | Markdown |

### **Configuration**

| File | Purpose | Committed |
|------|---------|-----------|
| `.env` | API keys, secrets, config | ❌ NO (.gitignore) |
| `.env.example` | Template for .env | ✅ YES |
| `requirements.txt` | Python dependencies | ✅ YES |
| `.gitignore` | Git ignore rules | ✅ YES |

### **Documentation**

| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | Project overview & quick start | Everyone |
| `SETUP.md` | Detailed installation guide | Developers |
| `docs/ARCHITECTURE.md` | System design & internals | Developers |
| `docs/PROJECT_STRUCTURE.md` | File organization | Developers |

### **Data Files (Generated, gitignored)**

| File | Created By | Used By | Format |
|------|-----------|---------|--------|
| `cow_analysis_data.json` | video_analyzer.py | app.py, frontend, chat_interface.py | JSON |
| `analysis_log.txt` | video_analyzer.py | app.py, frontend | Text |
| `chat_log.txt` | chat_interface.py | - | Text |
| `response_cache.json` | chat_interface.py | chat_interface.py | JSON |
| `gemini_responses.txt` | video_analyzer.py | - (debug only) | Text |
| `current_frame.jpg` | video_analyzer.py | - (optional use) | JPEG |

---

## 🔄 Data Flow Between Files

```
video_analyzer.py
  │
  ├─→ Reads: cow.mp4 (video file)
  ├─→ Calls: Gemini API for analysis
  ├─→ Writes: cow_analysis_data.json (JSON)
  ├─→ Writes: analysis_log.txt (log)
  └─→ Writes: gemini_responses.txt (debug)
       │
       ↓
app.py (Flask Server)
  │
  ├─→ Reads: cow_analysis_data.json
  ├─→ Endpoint GET /analysis/status → returns JSON
  ├─→ Endpoint GET /analysis/log → returns 100 latest lines
  ├─→ Calls: chat_interface.py for /test endpoint
  ├─→ Calls: at.py for /send endpoint
  └─→ Writes: chat_log.txt (via chat_interface)
       │
       ├─→ (Serves frontend files)
       │
       ↓
frontend/app.js
  │
  ├─→ Polls GET /analysis/status every 5 seconds
  ├─→ Polls GET /analysis/log periodically
  ├─→ POST /test (chat) →  chat_interface.py
  │     ├─→ Reads: cow_analysis_data.json
  │     ├─→ Checks: response_cache.json
  │     ├─→ Calls: Gemini API
  │     └─→ Writes: response_cache.json
  │
  └─→ POST /send (SMS) → at.py

chat_interface.py
  ├─→ Reads: cow_analysis_data.json (for context)
  ├─→ Reads: response_cache.json (for caching)
  ├─→ Calls: Gemini API
  └─→ Writes: chat_log.txt (via Flask)
```

---

## 🚀 Running the Application

### Development Setup
```bash
# Terminal 1: Video Analyzer (analysis engine)
python video_analyzer.py

# Terminal 2: Flask Backend (API server)
python app.py

# Terminal 3: Browser
open http://localhost:5000
```

### Testing
```bash
# Run chat interface tests
python tests/test_chat.py
```

---

## 📂 Directory Rationale

### Why This Structure?

✅ **Separation of Concerns**
- Core app logic separated from frontend
- Each service has a single responsibility
- Easy to test and maintain

✅ **Clear Organization**
- `docs/` for documentation
- `tests/` for automated tests
- `frontend/` for UI code
- Root for core application

✅ **Git-Friendly**
- `.gitignore` excludes generated files
- `.env` never committed (secrets stay safe)
- Only source code in repository

✅ **Scalability**
- Easy to add new modules
- Clear dependency structure
- Can extract services independently

---

## 🔐 Security Notes

### Gitignored Files (Never Commit!)
- `.env` — Contains API keys, secrets
- `response_cache.json` — May contain private farming data
- `chat_log.txt` — Farmer conversations
- `cow_analysis_data.json` — Current herd state
- `*.mp4` — Video files (large)

### Always Committed
- Source code (`.py` files)
- Configuration templates (`.env.example`)
- Documentation (`.md` files)
- Frontend code (no secrets)

---

## 📈 Future Expansion

### Adding New Features

**New AI Service?**
```
service_name.py  ← Add to root
  → Called by app.py
  → Reads shared data
```

**New API Endpoint?**
```
app.py → Add @app.route()
frontend/app.js → Add API call
```

**New Frontend View?**
```
frontend/index.html → Add <div class="view">
frontend/app.js → Add setView() handler
```

---

## 🧹 Cleanup Performed

### Removed (Redundant)
- ❌ `send.py` — Duplicate test file
- ❌ `test.py` — Moved to `tests/test_chat.py`

### Organized
- ✅ Created `docs/` for documentation
- ✅ Created `tests/` for test files
- ✅ Added comprehensive `.gitignore`
- ✅ Consolidated test files

---

## 📝 Quick Reference

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Set Up Environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### Start Application
```bash
# Terminal 1
python video_analyzer.py

# Terminal 2
python app.py
```

### View System Docs
```bash
# Architecture & design
open docs/ARCHITECTURE.md

# Setup guide
open SETUP.md

# Project structure
open docs/PROJECT_STRUCTURE.md
```

---

**Last Updated:** 2026-04-07  
**Status:** Reorganized & Optimized  
**Version:** 1.0
