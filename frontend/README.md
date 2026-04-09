# HerdWatch — Cow Monitoring System

Full-stack integration of the AI cow monitoring backend with a production-grade dashboard UI.

## Project Structure

```
herdwatch/
├── app.py                   ← Flask backend (updated with all endpoints + static serving)
├── video_analyzer.py        ← Runs separately — writes cow_analysis_data.json
├── chat_interface.py        ← FarmerChatInterface (Gemini AI)
├── at.py                    ← Africa's Talking SMS class
├── cow_analysis_data.json   ← Shared state between analyzer and Flask
├── analysis_log.txt         ← Frame-by-frame log (read by /analysis/log)
├── templates/
│   └── index.html           ← Main dashboard (served by Flask at GET /)
├── static/
│   ├── css/style.css        ← All styles
│   └── js/app.js            ← All API calls + UI logic
└── architecture.html        ← System architecture diagram (open in browser)
```

## API Endpoints

| Method | Endpoint               | Used By           | Purpose                                          |
|--------|------------------------|-------------------|--------------------------------------------------|
| GET    | `/`                    | Browser           | Serve the dashboard HTML                         |
| GET    | `/analysis/status`     | Dashboard (5s)    | Latest analysis from cow_analysis_data.json      |
| GET    | `/analysis/log`        | Analysis view     | Parse analysis_log.txt → structured entries      |
| POST   | `/test`                | AI Chat view      | Send message to FarmerChatInterface → AI reply   |
| POST   | `/send`                | SMS Center        | Send SMS via AT, optionally AI-enhanced first    |
| POST   | `/sms/receive`         | AT Webhook        | Receive farmer SMS → AI reply → auto-send back   |
| POST   | `/sms/delivery`        | AT Webhook        | Delivery status callbacks (logged)               |
| GET    | `/conversations`       | Conversations view| All SMS threads (or ?phone_number= for one)      |
| POST   | `/conversations/clear` | Dashboard quick   | Clear all in-memory conversation history         |

## Setup

### 1. Install dependencies
```bash
pip install flask flask-cors africastalking langchain-google-genai opencv-python
```

### 2. Run the video analyzer (separate terminal)
```bash
python video_analyzer.py
# Choose 1 (cow.mp4) or 2 (webcam)
# This writes cow_analysis_data.json and analysis_log.txt
```

### 3. Run Flask
```bash
python app.py
# → http://localhost:5000
```

### 4. Open the dashboard
Navigate to `http://localhost:5000` in your browser.

### 5. Configure Africa's Talking webhook
In your AT dashboard, set the incoming SMS webhook to:
```
http://your-public-ip:5000/sms/receive
```
Use ngrok for local testing: `ngrok http 5000`

## Frontend Views

| View          | What it does                                                      |
|---------------|-------------------------------------------------------------------|
| Dashboard     | Live status ring, mini herd grid, cow count chart, quick actions  |
| AI Analysis   | Full frame-by-frame log table (filterable, refreshable)           |
| Herd          | Individual cow cards with search, filter, click-to-chat           |
| AI Chat       | Full chat UI wired to POST /test (Gemini with video context)      |
| SMS Center    | Compose + send with optional AI enhancement via POST /send        |
| Conversations | View all incoming farmer SMS threads from AT webhook              |

## Data Flow

```
[cow.mp4 / webcam]
      ↓
[video_analyzer.py]  — every 90 frames —→  [Gemini API]
      ↓                                          ↓
[cow_analysis_data.json]              [analysis_log.txt]
      ↓                                          ↓
[Flask GET /analysis/status]    [Flask GET /analysis/log]
      ↓                                          ↓
[Dashboard — polls 5s]          [Analysis view — polls 15s]

[Farmer → SMS]
      ↓
[AT webhook → POST /sms/receive]
      ↓
[FarmerChatInterface.chat_with_farmer()]
      ↓
[Gemini AI + current_frame.jpg]
      ↓
[AT SMS reply → Farmer phone]

[Dashboard AI Chat]
      ↓
[POST /test → FarmerChatInterface]
      ↓
[Gemini → response displayed in UI]
```
