"""
Database persistence layer for HerdWatch
Uses SQLite for conversation and alert storage
"""

import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

# ────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", "herdwatch.db")

# ────────────────────────────────────────────────────────────
# Database Context Manager
# ────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ────────────────────────────────────────────────────────────
# Database Initialization
# ────────────────────────────────────────────────────────────

def init_db():
    """Initialize database schema"""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT NOT NULL,
                message_type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                resolved INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
    
    print(f"✓ Initialized database: {DB_PATH}")

# ────────────────────────────────────────────────────────────
# Conversation Functions
# ────────────────────────────────────────────────────────────

def save_message(phone, msg_type, message):
    """
    Save SMS message to conversation history
    
    Args:
        phone: Phone number
        msg_type: "received" or "sent"
        message: Message text
    """
    with get_db() as conn:
        conn.execute(
            """INSERT INTO conversations 
               (phone, message_type, message, timestamp)
               VALUES (?, ?, ?, ?)""",
            (phone, msg_type, message, datetime.now().isoformat())
        )
        conn.commit()

def get_conversation(phone):
    """
    Get all messages with a specific phone number
    
    Args:
        phone: Phone number
        
    Returns:
        list: Message dictionaries
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM conversations 
               WHERE phone = ? 
               ORDER BY timestamp ASC""",
            (phone,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_all_conversations():
    """
    Get all conversations grouped by phone number
    
    Returns:
        dict: {phone: [messages...]}
    """
    with get_db() as conn:
        phones = conn.execute(
            "SELECT DISTINCT phone FROM conversations ORDER BY phone"
        ).fetchall()
        
        result = {}
        for row in phones:
            phone = row["phone"]
            result[phone] = get_conversation(phone)
        
        return result

def clear_conversations():
    """Delete all conversation history"""
    with get_db() as conn:
        conn.execute("DELETE FROM conversations")
        conn.commit()
    print("✓ Cleared conversation history")

def delete_conversation(phone):
    """Delete messages from specific phone number"""
    with get_db() as conn:
        conn.execute("DELETE FROM conversations WHERE phone = ?", (phone,))
        conn.commit()

# ────────────────────────────────────────────────────────────
# Alert Functions
# ────────────────────────────────────────────────────────────

def save_alert(alert_type, message):
    """
    Save alert to database
    
    Args:
        alert_type: Type of alert (critical, warning, info)
        message: Alert message
    """
    with get_db() as conn:
        conn.execute(
            """INSERT INTO alerts 
               (alert_type, message, timestamp)
               VALUES (?, ?, ?)""",
            (alert_type, message, datetime.now().isoformat())
        )
        conn.commit()

def get_alerts(limit=100):
    """
    Get recent alerts
    
    Args:
        limit: Maximum number to return
        
    Returns:
        list: Alert dictionaries
    """
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM alerts 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def get_unresolved_alerts():
    """Get all unresolved alerts"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE resolved = 0 ORDER BY timestamp DESC"
        ).fetchall()
        return [dict(r) for r in rows]

def resolve_alert(alert_id):
    """Mark alert as resolved"""
    with get_db() as conn:
        conn.execute(
            "UPDATE alerts SET resolved = 1 WHERE id = ?",
            (alert_id,)
        )
        conn.commit()

def clear_alerts():
    """Delete all alerts"""
    with get_db() as conn:
        conn.execute("DELETE FROM alerts")
        conn.commit()
    print("✓ Cleared alerts")

# ────────────────────────────────────────────────────────────
# Statistics
# ────────────────────────────────────────────────────────────

def get_stats():
    """Get database statistics"""
    with get_db() as conn:
        conv_count = conn.execute(
            "SELECT COUNT(*) as count FROM conversations"
        ).fetchone()["count"]
        
        alert_count = conn.execute(
            "SELECT COUNT(*) as count FROM alerts WHERE resolved = 0"
        ).fetchone()["count"]
        
        phone_count = conn.execute(
            "SELECT COUNT(DISTINCT phone) as count FROM conversations"
        ).fetchone()["count"]
        
        return {
            "total_messages": conv_count,
            "active_phones": phone_count,
            "unresolved_alerts": alert_count
        }

# Initialize database on import
if not os.path.exists(DB_PATH):
    init_db()
