from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from at import SMS
from chat_interface import FarmerChatInterface
from video_processor import video_processor
from config import features, is_sms_enabled
from db import (init_db, save_message, get_all_conversations, 
                clear_conversations, delete_conversation)
from datetime import datetime
import logging
import os
import json
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────
# Error Codes
# ────────────────────────────────────────────────────────────

ERROR_CHAT = "CHAT_ERROR"
ERROR_SMS = "SMS_ERROR"
ERROR_VIDEO = "VIDEO_ERROR"
ERROR_ANALYSIS = "ANALYSIS_ERROR"

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"mp4", "avi", "mov", "mkv"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ────────────────────────────────────────────────────────────
# Flask and Middleware
# ────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder="frontend", template_folder="frontend")

# CORS with restricted origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5000").split(",")
CORS(app, origins=[o.strip() for o in allowed_origins])

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log all incoming requests for debugging
@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path}")

# ────────────────────────────────────────────────────────────
# Service Initialization
# ────────────────────────────────────────────────────────────

# Initialize database
init_db()

# SMS is lazy-initialized
sms_sender = SMS()

# AI chat interface
ai_farmer = FarmerChatInterface()

# File paths
SHARED_DATA_FILE = "cow_analysis_data.json"
ANALYSIS_LOG_FILE = "analysis_log.txt"

# Log cache with TTL
_log_cache = {"entries": [], "mtime": 0, "total": 0, "timestamp": 0}
LOG_CACHE_TTL = 30  # 30 seconds

# ─── Serve the React/HTML frontend ───────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    if filename and "." in filename:
        return send_from_directory("frontend", filename)
    return send_from_directory("frontend", "index.html")

# Health check endpoint
@app.route("/api/health", methods=["GET"])
def health():
    """Simple health check to verify the API is running."""
    return jsonify({
        "status": "ok",
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
    }), 200


# ─── API: AI Test / Chat ──────────────────────────────────────────────────────

@app.route("/test", methods=["POST"])
@limiter.limit("20 per minute")
def test_ai():
    """
    Chat with the AI farmer assistant.
    Body: { "message": "How many cows are eating?" }
    Returns: { "input": "...", "response": "...", "status": "success" }
    """
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"error": "Missing 'message' parameter"}), 400

        response = ai_farmer.chat_with_farmer(message)
        
        return jsonify({
            "input": message, 
            "response": response, 
            "status": "success"
        }), 200

    except Exception as e:
        logger.error(f"/test error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_CHAT,
            "status": "error"
        }), 500


# ─── API: Manual SMS Send ─────────────────────────────────────────────────────

@app.route("/send", methods=["POST"])
@limiter.limit("10 per minute")
def send_sms():
    """
    Send an SMS (with optional AI response generation).
    Body: { "message": "...", "recipients": "+254..." | ["+254...", ...], "use_ai": false }
    Returns: { "status": "success", "recipients": [...] }
    """
    if not is_sms_enabled():
        return jsonify({
            "error": "SMS not configured",
            "code": ERROR_SMS
        }), 503
    
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        message = data.get("message", "").strip()
        recipients = data.get("recipients", "")
        use_ai = data.get("use_ai", True)

        if not message or not recipients:
            return jsonify({"error": "Missing 'message' or 'recipients'"}), 400

        recipients_list = (
            [r.strip() for r in recipients.split(",")]
            if isinstance(recipients, str)
            else recipients
        )

        # Optionally pass message through AI before sending
        if use_ai:
            outgoing = ai_farmer.chat_with_farmer(message)
        else:
            outgoing = message

        result = sms_sender.send(recipients_list, outgoing)
        
        if not result.get("success"):
            return jsonify({
                "error": result.get("error", "Failed to send SMS"),
                "code": ERROR_SMS
            }), 500
        
        # Store in database
        for phone in recipients_list:
            save_message(phone, "sent", outgoing)
        
        return jsonify({
            "status": "success",
            "recipients": recipients_list,
        }), 200

    except Exception as e:
        logger.error(f"/send error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_SMS
        }), 500


@app.route("/sms/receive", methods=["POST"])
def receive_sms():
    """
    Africa's Talking webhook for incoming SMS.
    AT posts: from, text, id, to, date
    Auto-replies with AI-generated response.
    """
    if not is_sms_enabled():
        return jsonify({"error": "SMS not configured"}), 503
    
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Verify the request is from Africa's Talking
        at_username = data.get("to", "")
        expected = os.getenv("AFRICAS_TALKING_USERNAME", "sandbox")
        
        if at_username and at_username != expected:
            logger.warning(f"Rejected SMS webhook from unexpected sender: {at_username}")
            return jsonify({"error": "Unauthorized"}), 401

        phone_number = data.get("from", "")
        message_text = data.get("text", "")
        message_id = data.get("id", "")

        logger.info(f"Incoming SMS from {phone_number}: {message_text}")

        # Normalize Kenyan numbers
        if phone_number and not phone_number.startswith("+"):
            phone_number = "+254" + phone_number.lstrip("0")

        # Store in database
        save_message(phone_number, "received", message_text)

        # Generate AI response
        ai_response = ai_farmer.chat_with_farmer(message_text)
        _send_reply(phone_number, ai_response)
        
        # Store AI response in database
        save_message(phone_number, "sent", ai_response)

        return jsonify({"status": "success", "message": "SMS processed"}), 200

    except Exception as e:
        logger.error(f"/sms/receive error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_SMS
        }), 500


# ─── API: SMS Delivery Reports ────────────────────────────────────────────────

@app.route("/sms/delivery", methods=["POST"])
def delivery_report():
    """Handles Africa's Talking delivery status callbacks."""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        logger.info(f"Delivery report: {data}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"/sms/delivery error: {e}")
        return jsonify({"status": "error"}), 500


# ─── API: Conversation History ────────────────────────────────────────────────

@app.route("/conversations", methods=["GET"])
def get_conversations():
    """
    GET /conversations              → all conversations
    GET /conversations?phone=+254…  → single thread
    """
    phone_number = request.args.get("phone_number") or request.args.get("phone")
    
    try:
        if phone_number:
            from db import get_conversation
            messages = get_conversation(phone_number)
            return jsonify({
                "phone_number": phone_number,
                "messages": messages,
            })
        else:
            all_convs = get_all_conversations()
            return jsonify({
                "total_conversations": len(all_convs),
                "conversations": all_convs,
            })
    except Exception as e:
        logger.error(f"/conversations error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_SMS
        }), 500


@app.route("/conversations/clear", methods=["POST"])
def clear_conversations_route():
    """Wipe all conversation history from database."""
    if not is_sms_enabled():
        return jsonify({"error": "SMS not configured"}), 503
    
    try:
        clear_conversations()
        return jsonify({"status": "success", "message": "Conversation history cleared"})
    except Exception as e:
        logger.error(f"/conversations/clear error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_SMS
        }), 500


# ─── API: Live Analysis Status ────────────────────────────────────────────────

@app.route("/analysis/status", methods=["GET"])
def analysis_status():
    """
    Returns the latest analysis status.
    Merges live video_processor in-memory state (real-time) with the
    persisted cow_analysis_data.json so the dashboard stays live during processing.
    """
    try:
        # Start with persisted data (last completed analysis)
        disk_data = {}
        if os.path.exists(SHARED_DATA_FILE):
            try:
                with open(SHARED_DATA_FILE, "r") as f:
                    disk_data = json.load(f)
            except Exception:
                pass

        # Override with live in-memory state if processor is active
        proc_status = video_processor.get_status()
        if proc_status["is_processing"] or proc_status["status"] in ("processing", "completed"):
            return jsonify({
                "timestamp": proc_status["timestamp"],
                "analysis": proc_status["latest_analysis"],
                "frame_count": proc_status["frame_count"],
                "status": "running" if proc_status["is_processing"] else proc_status["status"],
            }), 200

        # Fall back to disk data
        if disk_data:
            return jsonify(disk_data), 200

        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "analysis": "No analysis data yet. Upload a video and click Process.",
            "frame_count": 0,
            "status": "idle",
        }), 200
    except Exception as e:
        logger.error(f"/analysis/status error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/analysis/log", methods=["GET"])
def analysis_log():
    """
    Returns last N lines from analysis_log.txt with caching.
    Query param: ?lines=50 (default 30)
    Cache TTL: 30 seconds
    """
    global _log_cache
    
    try:
        n = int(request.args.get("lines", 30))
        
        # Check cache validity
        now = datetime.now().timestamp()
        if _log_cache["timestamp"] > 0 and (now - _log_cache["timestamp"]) < LOG_CACHE_TTL:
            # Return cached entries
            entries = _log_cache["entries"][-n:] if _log_cache["entries"] else []
            return jsonify({"entries": entries, "total": _log_cache["total"]}), 200
        
        if not os.path.exists(ANALYSIS_LOG_FILE):
            return jsonify({"entries": [], "total": 0}), 200

        # Check if file has been modified
        mtime = os.path.getmtime(ANALYSIS_LOG_FILE)
        if mtime <= _log_cache["mtime"] and _log_cache["timestamp"] > 0:
            # Use cached data
            entries = _log_cache["entries"][-n:] if _log_cache["entries"] else []
            return jsonify({"entries": entries, "total": _log_cache["total"]}), 200

        # Read and parse file
        with open(ANALYSIS_LOG_FILE, "r", encoding="utf-8") as f:
            raw = [l.strip() for l in f.readlines() if l.strip()]

        entries = []
        for line in raw:
            # Format: "2025-07-31 16:27:20 - FRAME 90: Four cows are eating hay."
            try:
                ts_part, rest = line.split(" - FRAME ", 1)
                frame_num, analysis = rest.split(": ", 1)
                entries.append({
                    "timestamp": ts_part.strip(),
                    "frame": int(frame_num.strip()),
                    "analysis": analysis.strip(),
                    "is_error": analysis.strip().startswith("Analysis error"),
                })
            except Exception:
                entries.append({
                    "timestamp": "",
                    "frame": 0,
                    "analysis": line,
                    "is_error": False,
                })

        # Update cache
        _log_cache = {
            "entries": entries,
            "mtime": mtime,
            "total": len(raw),
            "timestamp": now
        }

        # Return requested slice
        return jsonify({"entries": entries[-n:], "total": len(raw)}), 200

    except Exception as e:
        logger.error(f"/analysis/log error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_ANALYSIS
        }), 500


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _send_reply(phone_number, message):
    try:
        result = sms_sender.send([phone_number], message)
        logger.info(f"Reply sent to {phone_number}")
        return result
    except Exception as e:
        logger.error(f"Reply failed to {phone_number}: {e}")
        return None


# ─── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_): return jsonify({"error": "Endpoint not found"}), 404
# ─── API: Video Upload and Processing ───────────────────────────────────────

def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/video/upload", methods=["POST"])
def upload_video():
    """Upload a video file for analysis"""
    try:
        # Check if file is in request
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        # Check file extension
        if not allowed_file(file.filename):
            return jsonify({
                "error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                "error": f"File too large. Max size: {MAX_FILE_SIZE // 1024 // 1024}MB"
            }), 400
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        logger.info(f"Video uploaded: {filename}")
        
        return jsonify({
            "status": "success",
            "filename": filename,
            "filepath": filepath,
            "size": file_size,
            "message": "Video uploaded successfully. Ready to process."
        }), 200
        
    except Exception as e:
        logger.error(f"/video/upload error: {e}")
        return jsonify({"error": str(e)[:100]}), 500


@app.route("/video/process", methods=["POST"])
@limiter.limit("5 per minute")
def process_video():
    """Start video processing with AI analysis"""
    try:
        data = request.get_json() if request.is_json else {}
        source = data.get("source", "").lower()  # "file" or "webcam"
        filename = data.get("filename", "")
        duration = data.get("duration", 60)  # seconds for webcam
        
        if source not in ["file", "webcam"]:
            return jsonify({"error": "source must be 'file' or 'webcam'"}), 400
        
        if video_processor.is_processing:
            return jsonify({
                "status": "already_processing",
                "message": "Video is already being processed"
            }), 400
        
        if source == "file":
            if not filename:
                return jsonify({"error": "filename required for file source"}), 400
            
            filepath = os.path.join(UPLOAD_FOLDER, secure_filename(filename))
            if not os.path.exists(filepath):
                return jsonify({"error": f"File not found: {filename}"}), 404
            
            # Start processing in background
            success = video_processor.start_video_processing(filepath)
            if not success:
                return jsonify({"error": "Could not start processing"}), 400
            
            return jsonify({
                "status": "processing_started",
                "source": "file",
                "filename": filename,
                "message": "Video processing started"
            }), 200
        
        elif source == "webcam":
            # Start webcam processing in background
            success = video_processor.start_webcam_processing(duration)
            if not success:
                return jsonify({"error": "Could not start processing"}), 400
            
            return jsonify({
                "status": "processing_started",
                "source": "webcam",
                "duration": duration,
                "message": f"Webcam processing started for {duration} seconds"
            }), 200
        
    except Exception as e:
        logger.error(f"/video/process error: {e}")
        return jsonify({
            "error": "An internal error occurred",
            "code": ERROR_VIDEO
        }), 500


@app.route("/video/status", methods=["GET"])
def video_status():
    """Get current video processing status"""
    try:
        status = video_processor.get_status()
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"/video/status error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/video/stop", methods=["POST"])
def stop_video():
    """Stop ongoing video processing"""
    try:
        success = video_processor.stop_processing()
        return jsonify({
            "status": "success" if success else "error",
            "message": "Video processing stopped" if success else "No processing to stop"
        }), 200
    except Exception as e:
        logger.error(f"/video/stop error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/video/current-frame", methods=["GET"])
def get_current_frame():
    """Get the current frame from video processing"""
    try:
        if os.path.exists("current_frame.jpg"):
            return send_from_directory(".", "current_frame.jpg")
        return jsonify({"error": "No frame available"}), 404
    except Exception as e:
        logger.error(f"/video/current-frame error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/video/list-uploads", methods=["GET"])
def list_uploads():
    """List all uploaded video files"""
    try:
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({"files": []}), 200
        
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                files.append({
                    "filename": filename,
                    "size": os.path.getsize(filepath),
                    "uploaded": datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
                })
        
        return jsonify({"files": files}), 200
    except Exception as e:
        logger.error(f"/video/list-uploads error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/video/delete/<filename>", methods=["DELETE"])
def delete_video(filename):
    """Delete an uploaded video file"""
    try:
        # Sanitize filename to prevent directory traversal
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        filepath = os.path.join(UPLOAD_FOLDER, safe_filename)
        
        # Verify file exists and is in uploads folder
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        if not os.path.isfile(filepath):
            return jsonify({"error": "Not a file"}), 400
        
        # Delete the file
        os.remove(filepath)
        logger.info(f"Video deleted: {filename}")
        
        return jsonify({
            "status": "success",
            "message": f"Video '{filename}' deleted successfully"
        }), 200
        
    except Exception as e:
        logger.error(f"/video/delete error: {e}")
        return jsonify({
            "error": "Failed to delete video",
            "code": ERROR_VIDEO
        }), 500


@app.route("/api/herd", methods=["GET"])
def get_herd_data():
    """Get herd data with current status from analysis"""
    try:
        # Try to load analysis data which contains real herd status
        if os.path.exists(SHARED_DATA_FILE):
            with open(SHARED_DATA_FILE, "r") as f:
                analysis_data = json.load(f)
        else:
            analysis_data = {}
        
        # Extract herd information - can be expanded based on analysis structure
        # For now, return a structured herd list that frontend can use
        herd_data = {
            "herd": [
                {
                    "id": "COW-001",
                    "name": "Lewis",
                    "status": analysis_data.get("cow_001_status", "eating"),
                    "detail": analysis_data.get("cow_001_detail", "Eating hay consistently"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-002",
                    "name": "Cow 2",
                    "status": analysis_data.get("cow_002_status", "eating"),
                    "detail": analysis_data.get("cow_002_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-003",
                    "name": "Cow 3",
                    "status": analysis_data.get("cow_003_status", "eating"),
                    "detail": analysis_data.get("cow_003_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-004",
                    "name": "Cow 4",
                    "status": analysis_data.get("cow_004_status", "eating"),
                    "detail": analysis_data.get("cow_004_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-005",
                    "name": "Cow 5",
                    "status": analysis_data.get("cow_005_status", "eating"),
                    "detail": analysis_data.get("cow_005_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-006",
                    "name": "Cow 6",
                    "status": analysis_data.get("cow_006_status", "eating"),
                    "detail": analysis_data.get("cow_006_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-007",
                    "name": "Cow 7",
                    "status": analysis_data.get("cow_007_status", "eating"),
                    "detail": analysis_data.get("cow_007_detail", "Eating hay"),
                    "tag": None,
                    "last_update": analysis_data.get("timestamp", "")
                },
                {
                    "id": "COW-600",
                    "name": "Cow #600",
                    "status": analysis_data.get("cow_600_status", "eating"),
                    "detail": analysis_data.get("cow_600_detail", "Tag 600 · Black & white"),
                    "tag": "600",
                    "last_update": analysis_data.get("timestamp", "")
                }
            ],
            "timestamp": analysis_data.get("timestamp", datetime.now().isoformat()),
            "analysis_available": os.path.exists(SHARED_DATA_FILE)
        }
        
        return jsonify(herd_data), 200
    
    except Exception as e:
        logger.error(f"/api/herd error: {e}")
        return jsonify({
            "error": "Failed to fetch herd data",
            "code": "HERD_ERROR"
        }), 500

@app.errorhandler(500)
def server_error(_): return jsonify({"error": "Internal server error"}), 500


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("HerdWatch API starting on http://0.0.0.0:5000")
    logger.info("Endpoints:")
    logger.info("  GET  /                   → Dashboard UI")
    logger.info("  POST /test               → AI chat")
    logger.info("  POST /send               → Send SMS (+ optional AI)")
    logger.info("  POST /sms/receive        → AT incoming webhook")
    logger.info("  POST /sms/delivery       → AT delivery reports")
    logger.info("  GET  /conversations      → Conversation history")
    logger.info("  POST /conversations/clear→ Clear history")
    logger.info("  GET  /analysis/status    → Latest video analysis")
    logger.info("  GET  /analysis/log       → Frame-by-frame log")
    app.run(debug=True, port=5000, host="0.0.0.0")
