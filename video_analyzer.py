import cv2
import base64
import os
import time
import json
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# ✅ Set up Google API Key
os.environ["GOOGLE_API_KEY"] = "AIzaSyDA9-0foCmBqWltPb8r3fOWoyI7iQLIhDc"

# ✅ Initialize the Gemini model
model = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# Shared data file for communication between processes
SHARED_DATA_FILE = "cow_analysis_data.json"
ANALYSIS_LOG_FILE = "analysis_log.txt"

class CowAnalyzer:
    def __init__(self, video_source='cow.mp4'):
        self.video_source = video_source
        self.running = True
        self.latest_analysis = "Starting analysis..."
        self.frame_count = 0
        
    def analyze_image_with_gemini(self, image):
        """Analyze image with Gemini AI"""
        if image is None:
            return "No image to analyze."
        
        try:
            # Convert the captured image to base64
            _, img_buffer = cv2.imencode('.jpg', image)
            image_data = base64.b64encode(img_buffer).decode('utf-8')
            
            # Create the message with the image
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "The agent's task is to detect cows. If there are multiple cows, check for each cow individually and report if they are eating or not.Also if there is cows identify the feed also provide it. Provide only that information."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            )
            
            # Send the message to Gemini and get the response
            response = model.invoke([message])
            return response.content
        except Exception as e:
            return f"Analysis error: {str(e)}"
    
    def save_current_frame(self, frame):
        """Save current frame as image for chat interface to access"""
        cv2.imwrite("current_frame.jpg", frame)
    
    def update_shared_data(self, analysis_result):
        """Update shared data file for chat interface"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis_result,
            "frame_count": self.frame_count,
            "status": "running" if self.running else "stopped"
        }
        
        try:
            with open(SHARED_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error updating shared data: {e}")
    
    def log_analysis(self, analysis_result):
        """Log analysis results to file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(ANALYSIS_LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"{timestamp} - FRAME {self.frame_count}: {analysis_result}\n")
    
    def run_analysis(self):
        """Main analysis loop"""
        print("🔍 Starting video analysis...")
        
        # Check if video file exists (if not using webcam)
        if isinstance(self.video_source, str) and not os.path.exists(self.video_source):
            error_msg = f"❌ Video file '{self.video_source}' not found"
            print(error_msg)
            self.update_shared_data(error_msg)
            return
        
        cap = cv2.VideoCapture(self.video_source)
        if not cap.isOpened():
            error_msg = "❌ Error: Unable to open video source"
            print(error_msg)
            self.update_shared_data(error_msg)
            return
        
        print("✅ Video source opened successfully")
        print("🎥 Starting analysis loop (every 3 seconds)")
        print("⏹  Press Ctrl+C to stop")
        
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    # If video ended, loop back to beginning
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                self.frame_count += 1
                
                # Save current frame for chat interface
                self.save_current_frame(frame)
                
                # Display video (optional)
                display_frame = cv2.resize(frame, (800, 600))
                cv2.putText(display_frame, f"Frame: {self.frame_count}", 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(display_frame, "Analysis running... Press 'q' to quit", 
                           (10, display_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow("🐄 Cow Analysis - Live Feed", display_frame)
                
                # Check for quit key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                # Analyze every 3 seconds
                if self.frame_count % 90 == 0:  # Assuming ~30 FPS
                    print(f"🔍 Analyzing frame {self.frame_count}...")
                    analysis_result = self.analyze_image_with_gemini(frame)
                    
                    self.latest_analysis = analysis_result
                    print(f"📊 Result: {analysis_result}")
                    
                    # Update shared data and log
                    self.update_shared_data(analysis_result)
                    self.log_analysis(analysis_result)
                
                time.sleep(0.033)  # ~30 FPS
                
        except KeyboardInterrupt:
            print("\n🛑 Analysis stopped by user")
        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            print(f"❌ {error_msg}")
            self.update_shared_data(error_msg)
        finally:
            self.running = False
            cap.release()
            cv2.destroyAllWindows()
            
            # Update final status
            self.update_shared_data("Analysis stopped")
            print("🧹 Video analysis cleanup complete")

def main():
    print("🐄 Cow Video Analysis System")
    print("=" * 50)
    
    # Ask user for video source
    choice = input("Choose video source:\n1. Video file (cow.mp4)\n2. Webcam\nEnter choice (1 or 2): ").strip()
    
    if choice == "2":
        video_source = 0  # Webcam
        print("📹 Using webcam...")
    else:
        video_source = "cow.mp4"
        print("📁 Using video file...")
    
    analyzer = CowAnalyzer(video_source)
    
    try:
        analyzer.run_analysis()
    except KeyboardInterrupt:
        print("\n👋 Shutting down analysis system...")
    except Exception as e:
        print(f"❌ System error: {str(e)}")

if __name__== "__main__":
    main()