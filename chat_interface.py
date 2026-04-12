# chat_interface.py
import os
import json
import time
import cv2
import base64
import hashlib
from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# ✅ Set up Azure OpenAI Configuration
api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

if not api_key or not endpoint or not chat_deployment:
    raise ValueError("Azure OpenAI credentials missing. Please set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_CHAT_DEPLOYMENT_NAME in .env file.")

# ✅ Initialize the Azure OpenAI model
model = AzureChatOpenAI(
    openai_api_version="2024-02-15-preview",
    azure_endpoint=endpoint,
    openai_api_key=api_key,
    deployment_name=chat_deployment,
    temperature=0.7
)

# Shared data files
SHARED_DATA_FILE = "cow_analysis_data.json"
CHAT_LOG_FILE = "chat_log.txt"
CURRENT_FRAME_FILE = "current_frame.jpg"
RESPONSE_CACHE_FILE = "response_cache.json"

# Response cache to avoid quota issues
CACHE_TTL = 600  # 10 minutes

class FarmerChatInterface:
    def __init__(self):
        self.chat_history = []
        self.response_cache = self._load_cache()
        self.last_api_call = 0
        self.min_api_interval = 2  # Minimum 2 seconds between API calls
        
    def _load_cache(self):
        """Load cached responses from file"""
        try:
            if os.path.exists(RESPONSE_CACHE_FILE):
                with open(RESPONSE_CACHE_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save_cache(self):
        """Save response cache to file with size management"""
        try:
            # Evict expired entries first
            now = datetime.now()
            self.response_cache = {
                k: v for k, v in self.response_cache.items()
                if datetime.fromisoformat(v['timestamp']) > now - timedelta(seconds=CACHE_TTL)
            }
            
            # If cache is too large, remove oldest entries
            MAX_CACHE_ENTRIES = 500
            if len(self.response_cache) > MAX_CACHE_ENTRIES:
                sorted_keys = sorted(
                    self.response_cache.keys(),
                    key=lambda k: self.response_cache[k]['timestamp']
                )
                entries_to_remove = len(sorted_keys) - MAX_CACHE_ENTRIES
                for key in sorted_keys[:entries_to_remove]:
                    del self.response_cache[key]
            
            with open(RESPONSE_CACHE_FILE, 'w') as f:
                json.dump(self.response_cache, f)
        except Exception as e:
            print(f"Error saving cache: {e}")
        
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
        """Handle farmer's chat with current analysis context and caching"""
        current_data = self.get_current_analysis()
        
        # Create a cache key from the question
        cache_key = hashlib.md5(farmer_question.lower().encode()).hexdigest()
        
        # Check cache first
        if cache_key in self.response_cache:
            cached = self.response_cache[cache_key]
            if datetime.fromisoformat(cached['timestamp']) > datetime.now() - timedelta(seconds=CACHE_TTL):
                print(f"[CACHE HIT] Using cached response for: {farmer_question[:50]}...")
                return cached['response']
        
        # Rate limit API calls
        time_since_last_call = time.time() - self.last_api_call
        if time_since_last_call < self.min_api_interval:
            wait_time = self.min_api_interval - time_since_last_call
            print(f"[RATE LIMIT] Waiting {wait_time:.1f}s before next API call...")
            time.sleep(wait_time)
        
        # Create context-aware message
        context_message = f"""
        You are an AI assistant helping a farmer monitor their cows through a video analysis system.
        
        Current Analysis Status: {current_data.get('status', 'unknown')}
        Latest Analysis (at {current_data.get('timestamp', 'unknown')}): {current_data.get('analysis', 'No data')}
        Frame Count: {current_data.get('frame_count', 'unknown')}
        
        Farmer's Question: {farmer_question}
        
        Please provide helpful, practical farming advice based on the current cow monitoring situation and the farmer's question.
        If the analysis shows any concerning patterns, mention them. Be concise but informative. Keep response under 150 words.
        """
        
        try:
            message = HumanMessage(content=[{"type": "text", "text": context_message}])
            self.last_api_call = time.time()
            response = model.invoke([message])
            response_text = response.content
            
            # Cache the response
            self.response_cache[cache_key] = {
                'response': response_text,
                'timestamp': datetime.now().isoformat(),
                'question': farmer_question
            }
            self._save_cache()
            
            return response_text
            
        except Exception as e:
            error_str = str(e)
            
            # Handle Azure OpenAI specific errors
            if any(code in error_str for code in ["RateLimitError", "429", "insufficient_quota", "DeploymentNotFound"]):
                fallback = (
                    "Azure OpenAI is temporarily unavailable. "
                    f"Latest analysis data: {current_data.get('analysis', 'No data available')}. "
                    "Please try again shortly."
                )
                print(f"[AZURE ERROR] {error_str[:100]}")
                return fallback
            
            # Handle other errors
            print(f"[API ERROR] {error_str[:100]}")
            return (
                "I couldn't process your question right now. "
                f"Latest data available: {current_data.get('analysis', 'No data')}. Please try again."
            )
    
    def save_chat_log(self, farmer_input, ai_response):
        """Save chat interaction to log file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(CHAT_LOG_FILE, "a", encoding="utf-8") as file:
                file.write(f"{timestamp} - FARMER: {farmer_input}\n")
                file.write(f"{timestamp} - AI: {ai_response}\n\n")
        except Exception as e:
            print(f"Error saving chat log: {e}")
    
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


