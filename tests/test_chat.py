"""
Test script for HerdWatch chat interface
Testing AI responses to farming questions
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_interface import FarmerChatInterface
from dotenv import load_dotenv

load_dotenv()

def test_chat_interface():
    """Test the farmer chat interface with various questions"""
    print("=" * 60)
    print("🐄 HerdWatch AI Chat Interface Test")
    print("=" * 60)
    
    ai_farmer = FarmerChatInterface()
    
    # Example questions to test
    test_questions = [
        "How many cows are eating right now?",
        "Should I be concerned about any cow behavior?",
        "What's the current feeding pattern?",
        "Do any cows look unhealthy or stressed?",
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n[Test {i}/{len(test_questions)}]")
        print(f"❓ Question: {question}")
        print("⏳ Processing...")
        
        try:
            response = ai_farmer.chat_with_farmer(question)
            print(f"✅ Response: {response}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed")
    print("=" * 60)

if __name__ == "__main__":
    test_chat_interface()
