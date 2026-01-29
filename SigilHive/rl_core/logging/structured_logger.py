"""
Structured logger for honeypot RL interactions.
Logs interaction data for RL agent training and monitoring.
"""

import os
import json
import time
from typing import Dict, Any, Optional


def log_interaction(
    session_id: str,
    protocol: str,
    input_data: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an interaction event for RL training.
    
    Args:
        session_id: Unique session identifier
        protocol: Protocol type ("ssh", "http", or "database")
        input_data: The raw input/command/request
        metadata: Additional context (intent, suspicious level, etc.)
    """
    try:
        # Create logs directory if needed
        log_dir = f"storage/session_logs/{protocol}"
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log entry
        log_entry = {
            "timestamp": time.time(),
            "input_data": input_data,
            "success": True,
            "metadata": metadata or {},
        }
        
        # Append to session log file
        log_file = f"{log_dir}/{session_id}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
    except Exception as e:
        # Silently fail - don't break honeypot operation for logging issues
        print(f"[StructuredLogger] Error logging interaction: {e}", flush=True)
