# HerdWatch Setup Guide

## 🔧 Project Setup & Installation

### 1. Create Virtual Environment
```bash
python -m venv .venv
```

### 2. Activate Virtual Environment
**Windows (PowerShell):**
```bash
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 🔐 Environment Configuration

### 1. Create `.env` File
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 2. Configure Environment Variables
Edit `.env` with your actual credentials:

```env
# Google Gemini API Key (required)
# Get from: https://aistudio.google.com/app/apikeys
GOOGLE_API_KEY=your_google_api_key_here

# Africa's Talking SMS Configuration (required for SMS functionality)
AFRICAS_TALKING_USERNAME=sandbox
AFRICAS_TALKING_API_KEY=your_africas_talking_api_key_here

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### 3. Get Your API Keys

**Google Gemini API:**
1. Visit [Google AI Studio](https://aistudio.google.com/app/apikeys)
2. Click "Create API Key"
3. Copy the key to your `.env` file as `GOOGLE_API_KEY`

**Africa's Talking API:**
1. Visit [Africa's Talking Dashboard](https://africastalking.com/sms/username/api/keys)
2. Copy your API key to `.env` as `AFRICAS_TALKING_API_KEY`

## ▶️ Running the Application

### Terminal 1: Start Video Analysis
```bash
python video_analyzer.py
```
- Choose between video file or webcam
- Press 'q' to quit

### Terminal 2: Start Flask Backend
```bash
python app.py
```
- Server runs on `http://localhost:5000`

### Terminal 3: Chat Interface (Optional)
```bash
python test.py
```
Or directly:
```bash
python chat_interface.py
```

## 🧪 Testing

### Test Chat Interface Only
```bash
python send.py
```
This will test basic chat responses without starting the full backend.

## 📊 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Dashboard UI |
| POST | `/test` | Chat with AI farmer |
| POST | `/send` | Send SMS with optional AI |
| POST | `/sms/receive` | Receive incoming SMS (Africa's Talking webhook) |
| GET | `/conversations` | Get conversation history |
| POST | `/conversations/clear` | Clear all history |
| GET | `/analysis/status` | Get latest analysis |
| GET | `/analysis/log` | Get frame-by-frame log |

## 📁 Project Structure

```
AT_Agrisolutiion/
├── app.py                    # Flask backend API
├── chat_interface.py         # AI chat interface
├── video_analyzer.py         # Video processing
├── at.py                     # Africa's Talking SMS
├── send.py                   # Chat testing script
├── test.py                   # Chat test entry point
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
├── .env                     # Your credentials (NOT in git)
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── ...
└── templates/
    └── index.html
```

## 🚨 Troubleshooting

### "Missing API Key" Error
- Make sure `.env` file exists in the project root
- Check that `GOOGLE_API_KEY` and `AFRICAS_TALKING_API_KEY` are set
- Restart the Python process after updating `.env`

### "Video file not found"
- Place your video file (`cow.mp4`) in the project root
- Or select webcam option (choice 2) when running video_analyzer.py

### Import Errors
- Make sure virtual environment is activated: `.venv\Scripts\Activate.ps1`
- Reinstall requirements: `pip install -r requirements.txt`

### Port Already in Use
- Change `FLASK_PORT` in `.env` file (default: 5000)

## 📝 Recent Fixes Applied

✅ **Security**: Moved all API keys to environment variables  
✅ **Code Quality**: Fixed undefined variable in send.py  
✅ **Functionality**: Completed save_chat_log() method  
✅ **Formatting**: Fixed spacing issues in prompt text  
✅ **Documentation**: Added error handling for missing credentials  

## 🔄 Git Best Practices

**Never commit `.env` to git!**
```bash
# Make sure .gitignore includes:
.env
.venv/
__pycache__/
*.pyc
```

## 📦 Dependencies

- **Flask** - Web framework
- **flask-cors** - Cross-origin requests
- **python-dotenv** - Environment variable management
- **langchain** - LLM integration
- **langchain-google-genai** - Gemini AI
- **opencv-python** - Video processing
- **africas-talking** - SMS integration

All locked in `requirements.txt` for reproducibility.
