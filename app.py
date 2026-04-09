from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from at import SMS
from chat_interface import FarmerChatInterface
from datetime import datetime
import logging
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="frontend", template_folder="frontend")
CORS(app)  # Allow frontend dev server during development

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log all incoming requests for debugging
@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path}")

sms_sender = SMS()
ai_farmer = FarmerChatInterface()

conversation_history = {}

SHARED_DATA_FILE = "cow_analysis_data.json"
ANALYSIS_LOG_FILE = "analysis_log.txt"

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
        
        # Check if response indicates quota issue
        if "quota exceeded" in response.lower() or "429" in response:
            return jsonify({
                "input": message, 
                "response": response, 
                "status": "quota_limited"
            }), 200
        
        return jsonify({
            "input": message, 
            "response": response, 
            "status": "success"
        }), 200

    except Exception as e:
        logger.error(f"/test error: {e}")
        return jsonify({
            "error": "Failed to process message",
            "details": str(e)[:100],
            "status": "error"
        }), 500


# ─── API: Manual SMS Send ─────────────────────────────────────────────────────

@app.route("/send", methods=["POST"])
def send_sms():
    """
    Send an SMS (with optional AI response generation).
    Body: { "message": "...", "recipients": "+254..." | ["+254...", ...], "use_ai": false }
    Returns: { "status": "success", "result": {...}, "response": "...", "recipients": [...] }
    """
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
        return jsonify({
            "status": "success",
            "result": result,
            "response": outgoing,
            "recipients": recipients_list,
        }), 200

    except Exception as e:
        logger.error(f"/send error: {e}")
        return jsonify({"error": "Failed to send SMS", "details": str(e)}), 500


# ─── API: Incoming SMS Webhook ────────────────────────────────────────────────

@app.route("/sms/receive", methods=["POST"])
def receive_sms():
    """
    Africa's Talking webhook for incoming SMS.
    AT posts: from, text, id, to, date
    Auto-replies with AI-generated response.
    """
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()

        phone_number = data.get("from", "")
        message_text = data.get("text", "")
        message_id   = data.get("id", "")

        logger.info(f"Incoming SMS from {phone_number}: {message_text}")

        # Normalise Kenyan numbers
        if phone_number and not phone_number.startswith("+"):
            phone_number = "+254" + phone_number.lstrip("0")

        if phone_number not in conversation_history:
            conversation_history[phone_number] = []

        conversation_history[phone_number].append({
            "type": "received",
            "message": message_text,
            "timestamp": datetime.now().isoformat(),
        })

        ai_response = ai_farmer.chat_with_farmer(message_text)
        _send_reply(phone_number, ai_response)

        conversation_history[phone_number].append({
            "type": "sent",
            "message": ai_response,
            "timestamp": datetime.now().isoformat(),
        })

        return jsonify({"status": "success", "message": "SMS processed"}), 200

    except Exception as e:
        logger.error(f"/sms/receive error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


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
    if phone_number:
        return jsonify({
            "phone_number": phone_number,
            "conversation": conversation_history.get(phone_number, []),
        })
    return jsonify({
        "total_conversations": len(conversation_history),
        "conversations": conversation_history,
    })


@app.route("/conversations/clear", methods=["POST"])
def clear_conversations():
    """Wipe all in-memory conversation history."""
    global conversation_history
    conversation_history = {}
    return jsonify({"status": "success", "message": "Conversation history cleared"})


# ─── API: Live Analysis Status ────────────────────────────────────────────────

@app.route("/analysis/status", methods=["GET"])
def analysis_status():
    """
    Returns latest data from cow_analysis_data.json written by video_analyzer.py.
    Frontend polls this every few seconds.
    """
    try:
        if os.path.exists(SHARED_DATA_FILE):
            with open(SHARED_DATA_FILE, "r") as f:
                data = json.load(f)
            return jsonify(data), 200
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "analysis": "No analysis data yet. Start video_analyzer.py.",
            "frame_count": 0,
            "status": "disconnected",
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/analysis/log", methods=["GET"])
def analysis_log():
    """
    Returns last N lines from analysis_log.txt.
    Query param: ?lines=50 (default 30)
    """
    try:
        n = int(request.args.get("lines", 30))
        if not os.path.exists(ANALYSIS_LOG_FILE):
            return jsonify({"entries": [], "total": 0}), 200

        with open(ANALYSIS_LOG_FILE, "r", encoding="utf-8") as f:
            raw = [l.strip() for l in f.readlines() if l.strip()]

        entries = []
        for line in raw[-n:]:
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

        return jsonify({"entries": entries, "total": len(raw)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
