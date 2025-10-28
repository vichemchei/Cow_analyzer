# test.py
from chat_interface import farmer_chat_interface

def main():
    print("🐄 Starting Cow Monitoring System with Farmer Chat...")
    try:
        farmer_chat_interface()
    except KeyboardInterrupt:
        print("\n👋 Exiting Cow Monitoring System...")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    main()