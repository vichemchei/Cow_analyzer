"""
Environment configuration and feature flag validation for HerdWatch
Validates required credentials on startup
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────
# Required Environment Variables
# ────────────────────────────────────────────────────────────

REQUIRED_FOR_AI = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"
]

REQUIRED_FOR_SMS = [
    "AFRICAS_TALKING_API_KEY",
    "AFRICAS_TALKING_USERNAME"
]

REQUIRED_FOR_RAG = [
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"
]

# ────────────────────────────────────────────────────────────
# Validation Function
# ────────────────────────────────────────────────────────────

def validate_config():
    """
    Validate environment configuration and return feature flags
    
    Returns:
        dict: Feature flags indicating which features are enabled
        
    Exits:
        sys.exit(1) if critical AI credentials are missing
    """
    
    missing_ai = [k for k in REQUIRED_FOR_AI if not os.getenv(k)]
    missing_sms = [k for k in REQUIRED_FOR_SMS if not os.getenv(k)]
    missing_rag = [k for k in REQUIRED_FOR_RAG if not os.getenv(k)]
    
    # AI is critical — system cannot function without it
    if missing_ai:
        print("=" * 70)
        print("🔴 FATAL ERROR: Missing AI Credentials")
        print("=" * 70)
        for var in missing_ai:
            print(f"  ❌ {var}")
        print("\nAI chat and video analysis will not work without these.")
        print("Please check your .env file and restart.")
        print("=" * 70)
        sys.exit(1)
    
    # SMS is optional — warn but continue
    if missing_sms:
        print("=" * 70)
        print("⚠️  WARNING: SMS Features Disabled")
        print("=" * 70)
        for var in missing_sms:
            print(f"  ⚠️  {var}")
        print("\nSMS functionality will not be available.")
        print("=" * 70)
    
    # RAG is optional — warn but continue
    if missing_rag:
        print("=" * 70)
        print("⚠️  WARNING: RAG Features Disabled")
        print("=" * 70)
        for var in missing_rag:
            print(f"  ⚠️  {var}")
        print("\nHistorical search will not be available.")
        print("=" * 70)
    
    return {
        "ai_enabled": len(missing_ai) == 0,
        "sms_enabled": len(missing_sms) == 0,
        "rag_enabled": len(missing_rag) == 0
    }


# Global feature flags
features = validate_config()

# Convenience accessors
def is_sms_enabled():
    return features.get("sms_enabled", False)

def is_rag_enabled():
    return features.get("rag_enabled", False)

def is_ai_enabled():
    return features.get("ai_enabled", False)
