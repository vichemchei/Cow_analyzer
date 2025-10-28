from flask import Flask, request, jsonify
from at import SMS  # Your custom SMS class
from chat_interface import farmer_chat_interface, FarmerChatInterface
from datetime import datetime
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize your classes
sms_sender = SMS()
ai_farmer = FarmerChatInterface()

# Store conversation history (use database in production)
conversation_history = {}

@app.route("/")
def home():
    return {"status": "AI Farmer SMS Service is running", "endpoints": ["/send", "/sms/receive"]}

@app.route("/send", methods=['POST'])
def send_sms():
    """Manual SMS sending endpoint (your existing code with improvements)"""
    try:
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            message = data.get('message')
            recipients = data.get('recipients')
        else:
            message = request.form.get('message')
            recipients = request.form.get('recipients')

        if not message or not recipients:
            return {"error": "Missing 'message' or 'recipients'"}, 400

        # Handle recipients as list or comma-separated string
        if isinstance(recipients, str):
            recipients_list = [r.strip() for r in recipients.split(",")]
        else:
            recipients_list = recipients

        # Get AI response
        response = ai_farmer.chat_with_farmer(message)
        logger.info(f"AI Response: {response}")
        
        # Send SMS
        result = sms_sender.send(recipients_list, response)
        
        return {
            "status": "success", 
            "result": result,
            "response": response,
            "recipients": recipients_list
        }, 200
        
    except Exception as e:
        logger.error(f"Error in send_sms: {str(e)}")
        return {"error": "Failed to send SMS", "details": str(e)}, 500

@app.route("/sms/receive", methods=['POST'])
def receive_sms():
    """
    Webhook endpoint to receive incoming SMS from AfricasTalking
    This is the key addition for two-way SMS functionality
    """
    try:
        # AfricasTalking sends data as form-encoded or JSON
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        # Extract SMS details
        phone_number = data.get('from', '')
        message_text = data.get('text', '')
        message_id = data.get('id', '')
        shortcode = data.get('to', '')
        date_received = data.get('date', datetime.now().isoformat())
        
        logger.info(f"Received SMS from {phone_number}: {message_text}")
        
        # Clean phone number format (ensure it starts with +)
        if not phone_number.startswith('+'):
            # Assume Kenyan number if no country code
            phone_number = '+254' + phone_number.lstrip('0')
        
        # Store conversation context
        if phone_number not in conversation_history:
            conversation_history[phone_number] = []
        
        conversation_history[phone_number].append({
            'type': 'received',
            'message': message_text,
            'timestamp': datetime.now().isoformat()
        })
        
        # Process message with AI farmer
        try:
            # You might want to pass conversation history for context
            ai_response = ai_farmer.chat_with_farmer(message_text)
            
            # Send reply
            if ai_response:
                send_reply(phone_number, ai_response)
                
                # Store sent message in history
                conversation_history[phone_number].append({
                    'type': 'sent',
                    'message': ai_response,
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error processing AI response: {str(e)}")
            # Send fallback message
            fallback_msg = "Sorry, I'm having trouble processing your request right now. Please try again later."
            send_reply(phone_number, fallback_msg)
        
        return jsonify({"status": "success", "message": "SMS processed"}), 200
        
    except Exception as e:
        logger.error(f"Error in receive_sms: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

def send_reply(phone_number, message):
    """Send SMS reply to a single recipient"""
    try:
        result = sms_sender.send([phone_number], message)
        logger.info(f"Sent reply to {phone_number}: {message}")
        return result
    except Exception as e:
        logger.error(f"Error sending reply to {phone_number}: {str(e)}")
        return None

@app.route("/sms/delivery", methods=['POST'])
def delivery_report():
    """Handle SMS delivery reports from AfricasTalking"""
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            
        logger.info(f"Delivery report: {data}")
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Error processing delivery report: {str(e)}")
        return jsonify({"status": "error"}), 500

@app.route("/conversations", methods=['GET'])
def get_conversations():
    """Get conversation history (for debugging/monitoring)"""
    phone_number = request.args.get('phone_number')
    
    if phone_number:
        return jsonify({
            "phone_number": phone_number,
            "conversation": conversation_history.get(phone_number, [])
        })
    else:
        return jsonify({
            "total_conversations": len(conversation_history),
            "conversations": conversation_history
        })

@app.route("/conversations/clear", methods=['POST'])
def clear_conversations():
    """Clear conversation history"""
    global conversation_history
    conversation_history = {}
    return jsonify({"status": "success", "message": "Conversation history cleared"})

@app.route("/test", methods=['POST'])
def test_ai():
    """Test the AI farmer interface directly"""
    try:
        if request.is_json:
            data = request.get_json()
            message = data.get('message')
        else:
            message = request.form.get('message')
            
        if not message:
            return {"error": "Missing 'message' parameter"}, 400
            
        response = ai_farmer.chat_with_farmer(message)
        return {
            "input": message,
            "response": response,
            "status": "success"
        }, 200
        
    except Exception as e:
        return {"error": "Failed to process message", "details": str(e)}, 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    logger.info("Starting AI Farmer SMS Service...")
    logger.info("Available endpoints:")
    logger.info("  POST /send - Send SMS manually")
    logger.info("  POST /sms/receive - Webhook for incoming SMS")
    logger.info("  POST /sms/delivery - Delivery reports")
    logger.info("  GET /conversations - View conversation history")
    logger.info("  POST /test - Test AI farmer directly")
    logger.info("")
    logger.info("Configure webhook URL in AfricasTalking: http://your-domain.com/sms/receive")
    
    app.run(debug=True, port=5000, host='0.0.0.0')