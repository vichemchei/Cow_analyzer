"""
Video processing module for Flask backend
Handles video analysis with Azure OpenAI for both uploaded files and webcam streams
"""

import cv2
import base64
import os
import json
import threading
import time
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Azure OpenAI Configuration
api_key = os.getenv("AZURE_OPENAI_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
chat_deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")

if not api_key or not endpoint or not chat_deployment:
    raise ValueError("Azure OpenAI credentials missing.")

# Initialize the Azure OpenAI model
model = AzureChatOpenAI(
    openai_api_version="2024-02-15-preview",
    azure_endpoint=endpoint,
    openai_api_key=api_key,
    deployment_name=chat_deployment,
    temperature=0.7
)

SHARED_DATA_FILE = "cow_analysis_data.json"
ANALYSIS_LOG_FILE = "analysis_log.txt"
UPLOADS_DIR = "uploads"

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)


class VideoProcessor:
    """Process video files or webcam stream with Azure OpenAI analysis"""
    
    def __init__(self):
        self.is_processing = False
        self.current_status = "idle"
        self.frame_count = 0
        self.latest_analysis = "Ready for analysis"
        self.processing_thread = None
        
    def analyze_frame(self, frame):
        """Analyze a single frame with Azure OpenAI"""
        if frame is None:
            return "No frame to analyze"
        
        try:
            # Convert frame to base64
            _, img_buffer = cv2.imencode('.jpg', frame)
            image_data = base64.b64encode(img_buffer).decode('utf-8')
            
            # Create message with image
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": "Detect cows in this image. For each cow, report: 1) If it's eating or standing, 2) The feed type if eating. Keep response concise. Format: 'Cow 1: [status]. Cow 2: [status].' If no cows, say 'No cows detected.'"
                    },
                    {
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                    }
                ]
            )
            
            # Get response from Azure OpenAI
            response = model.invoke([message])
            return response.content
            
        except Exception as e:
            return f"Analysis error: {str(e)[:100]}"
    
    def process_video_file(self, video_path, frame_interval=30):
        """Process a video file frame by frame"""
        self.is_processing = True
        self.current_status = "processing"
        self.frame_count = 0
        self.latest_analysis = "Starting video analysis..."
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.current_status = "error"
                self.latest_analysis = "Error: Could not open video file"
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_skip = max(1, int(fps * frame_interval / 1000)) if frame_interval else 1
            
            while cap.isOpened() and self.is_processing:
                ret, frame = cap.read()
                if not ret:
                    break
                
                self.frame_count += 1
                
                # Process every nth frame
                if self.frame_count % frame_skip == 0:
                    # Resize frame for faster processing
                    resized = cv2.resize(frame, (640, 480))
                    analysis = self.analyze_frame(resized)
                    
                    # Save frame
                    cv2.imwrite("current_frame.jpg", frame)
                    
                    # Update shared data
                    self.latest_analysis = analysis
                    self._update_shared_data(analysis)
                    
                    # Log analysis
                    self._log_analysis(analysis)
                    
                    time.sleep(2)  # Rate limiting
            
            cap.release()
            self.current_status = "completed"
            self.latest_analysis = f"Video analysis completed. Processed {self.frame_count} frames."
            
        except Exception as e:
            self.current_status = "error"
            self.latest_analysis = f"Error: {str(e)[:100]}"
        finally:
            self.is_processing = False
    
    def process_webcam(self, duration_seconds=60):
        """Process webcam stream for specified duration"""
        self.is_processing = True
        self.current_status = "processing"
        self.frame_count = 0
        self.latest_analysis = "Starting webcam analysis..."
        
        try:
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.current_status = "error"
                self.latest_analysis = "Error: Could not access webcam"
                return
            
            start_time = time.time()
            frame_skip = 30  # Process every 30th frame
            
            while self.is_processing and (time.time() - start_time) < duration_seconds:
                ret, frame = cap.read()
                if not ret:
                    break
                
                self.frame_count += 1
                
                if self.frame_count % frame_skip == 0:
                    # Resize frame
                    resized = cv2.resize(frame, (640, 480))
                    analysis = self.analyze_frame(resized)
                    
                    # Save frame
                    cv2.imwrite("current_frame.jpg", frame)
                    
                    # Update shared data
                    self.latest_analysis = analysis
                    self._update_shared_data(analysis)
                    
                    # Log analysis
                    self._log_analysis(analysis)
                    
                    time.sleep(2)  # Rate limiting
            
            cap.release()
            self.current_status = "completed"
            self.latest_analysis = f"Webcam analysis completed. Processed {self.frame_count} frames."
            
        except Exception as e:
            self.current_status = "error"
            self.latest_analysis = f"Error: {str(e)[:100]}"
        finally:
            self.is_processing = False
    
    def _update_shared_data(self, analysis):
        """Update shared data file"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "frame_count": self.frame_count,
            "status": "running" if self.is_processing else self.current_status
        }
        try:
            with open(SHARED_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error updating shared data: {e}")
    
    def _log_analysis(self, analysis):
        """Log analysis to file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(ANALYSIS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} - FRAME {self.frame_count}: {analysis}\n")
        except Exception as e:
            print(f"Error logging analysis: {e}")
    
    def start_video_processing(self, video_path):
        """Start video processing in a background thread"""
        if self.is_processing:
            return False
        
        self.processing_thread = threading.Thread(
            target=self.process_video_file,
            args=(video_path, 90),  # 90ms frame interval
            daemon=True
        )
        self.processing_thread.start()
        return True
    
    def start_webcam_processing(self, duration=60):
        """Start webcam processing in a background thread"""
        if self.is_processing:
            return False
        
        self.processing_thread = threading.Thread(
            target=self.process_webcam,
            args=(duration,),
            daemon=True
        )
        self.processing_thread.start()
        return True
    
    def stop_processing(self):
        """Stop ongoing video processing"""
        self.is_processing = False
        self.current_status = "stopped"
        return True
    
    def get_status(self):
        """Get current processing status"""
        return {
            "is_processing": self.is_processing,
            "status": self.current_status,
            "frame_count": self.frame_count,
            "latest_analysis": self.latest_analysis,
            "timestamp": datetime.now().isoformat()
        }


# Global processor instance
video_processor = VideoProcessor()
