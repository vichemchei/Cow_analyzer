# chat_interface.py
import os
import json
import time
import cv2
import base64
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# ✅ Set up Google API Key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDA9-0foCmBqWltPb8r3fOWoyI7iQLIhDc"

# ✅ Initialize the Gemini model
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# Shared data files
SHARED_DATA_FILE = "cow_analysis_data.json"
CHAT_LOG_FILE = "chat_log.txt"
CURRENT_FRAME_FILE = "current_frame.jpg"

class FarmerChatInterface:
    def __init__(self):
        self.chat_history = []
        
    def get_current_analysis(self):
        """Get the latest analysis from the video analyzer"""
        try:
            if os.path.exists(SHARED_DATA_FILE):
                with open(SHARED_DATA_FILE, 'r') as f:
                    data = json.load(f)
                return data
            else:
                return {
                    "analysis": "No analysis data available. Make sure video analyzer is running.",
                    "timestamp": datetime.now().isoformat(),
                    "status": "disconnected"
                }
        except Exception as e:
            return {
                "analysis": f"Error reading analysis data: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "status": "error"
            }
    
    def get_current_frame(self):
        """Get the current frame from video analyzer"""
        try:
            if os.path.exists(CURRENT_FRAME_FILE):
                return cv2.imread(CURRENT_FRAME_FILE)
            return None
        except Exception as e:
            print(f"Error reading current frame: {e}")
            return None
    
    def chat_with_farmer(self, farmer_question):
        """Handle farmer's chat with current analysis context"""
        current_data = self.get_current_analysis()
        current_frame = self.get_current_frame()
        
        # Create context-aware message
        context_message = f"""
        You are an AI assistant helping a farmer monitor their cows through a video analysis system.
        
        Current Analysis Status: {current_data.get('status', 'unknown')}
        Latest Analysis (at {current_data.get('timestamp', 'unknown')}): {current_data.get('analysis', 'No data')}
        Frame Count: {current_data.get('frame_count', 'unknown')}
        
        Farmer's Question: {farmer_question}
        
        Please provide helpful, practical farming advice based on the current cow monitoring situation and the farmer's question.
        If the analysis shows any concerning patterns, mention them. Be concise but informative.Make sure this response is short and precise.
        """
        
        try:
            # If there's a current frame, include it for visual context
            if current_frame is not None:
                _, img_buffer = cv2.imencode('.jpg', current_frame)
                image_data = base64.b64encode(img_buffer).decode('utf-8')
                
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": context_message},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]
                )
            else:
                message = HumanMessage(content=[{"type": "text", "text": context_message}])
            
            response = model.invoke([message])
            return response.content
            
        except Exception as e:
            return f"Sorry, I couldn't process your question right now. Error: {str(e)}"
    
    def save_chat_log(self, farmer_input, ai_response):
        """Save chat interaction to log file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(CHAT_LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"{timestamp} - FARMER: {farmer_input}\n")
            file.write(f"{timestamp} - AI: {ai_response}\n\n")
    
    def display_status(self):
        """Display current system status"""
        current_data = self.get_current_analysis()
        status = current_data.get('status', 'unknown')
        analysis = current_data.get('analysis', 'No analysis available')
        timestamp = current_data.get('timestamp', 'unknown')
        
        status_color = "🟢" if status == "running" else "🔴" if status == "error" else "🟡"
        
        print(f"\n{status_color} Analysis Status: {status}")
        print(f"⏰ Last Update: {timestamp}")
        print(f"📊 Current Analysis: {analysis[:100]}{'...' if len(analysis) > 100 else ''}")
        
        return status == "running"

def farmer_chat_interface():
    """Main chat interface function"""
    chat = FarmerChatInterface()
    
    print("\n" + "="*70)
    print("🌾 FARMER CHAT INTERFACE - STANDALONE MODE")
    print("="*70)
    print("💬 Ask questions about your cows while video analysis runs separately!")
    print("📝 Example questions:")
    print("   • 'How many cows are eating right now?'")
    print("   • 'Should I be concerned about any cow behavior?'")
    print("   • 'What's the current feeding pattern?'")
    print("   • 'Give me a summary of recent activity'")
    print("   • 'status' - Check connection to video analyzer")
    print("🚪 Type 'quit' to exit")
    print("="*70)
    
    while True:
        try:
            # Show current status
            is_connected = chat.display_status()
            
            if not is_connected:
                print("⚠  Video analyzer not running. Start 'python3 video_analyzer.py' in another terminal.")
            
            farmer_input = input("\n🌾 Farmer: ").strip()
            
            if farmer_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Ending chat session...")
                break
            
            if not farmer_input:
                continue
            
            if farmer_input.lower() == 'status':
                continue  # Status already displayed above
                
            print("🤖 AI is analyzing...")
            
            # Get AI response
            ai_response = chat.chat_with_farmer(farmer_input)
            print(f"\n🤖 Farm Assistant: {ai_response}")
            
            # Save to chat history and log
            chat.chat_history.append({"farmer": farmer_input, "ai": ai_response})
            chat.save_chat_log(farmer_input, ai_response)
            
        except KeyboardInterrupt:
            print("\n👋 Chat interrupted by user...")
            break
        except Exception as e:
            print(f"❌ Chat error: {str(e)}")
            time.sleep(1)
    
    # Session summary
    print(f"\n📋 CHAT SESSION SUMMARY:")
    print(f"   💬 Total interactions: {len(chat.chat_history)}")
    print(f"   📁 Chat log saved to: {CHAT_LOG_FILE}")
    print("   🐄 Thank you for using the Cow Monitoring Chat System!")

def main():
    """Main function for standalone chat"""
    print("🐄 Starting Farmer Chat Interface...")
    
    try:
        farmer_chat_interface()
    except KeyboardInterrupt:
        print("\n👋 Exiting Cow Monitoring Chat...")
    except Exception as e:
        print(f"❌😂😂😂 Error: {str(e)}")


if __name__ == "__main__":
    main()


