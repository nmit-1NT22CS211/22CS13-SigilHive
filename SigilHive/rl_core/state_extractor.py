"""
State extraction module for RL honeypot system.

Converts raw session logs into discrete state representations
that the Q-learning agent can process.
"""

import os
import json
import time
from typing import Tuple, List, Dict
from .config import STATE_BUCKETS, PROTOCOL_SETTINGS


def extract_state(session_id: str, protocol: str) -> Tuple:
    """
    Extract current state for a session.

    Args:
        session_id: Unique session identifier
        protocol: "database", "http", or "ssh"

    Returns:
        State tuple: (commands_per_min, unique_cmds, duration, error_ratio, privesc)
        Each value is discretized to 0 (LOW), 1 (MED), or 2 (HIGH)

    Example:
        >>> extract_state("abc123", "ssh")
        (1, 2, 1, 0, 0)  # MED rate, HIGH diversity, MED duration, LOW errors, no privesc
    """
    # Load session logs
    logs = _load_session_logs(session_id, protocol)

    if not logs:
        # No logs yet - return initial state
        return (0, 0, 0, 0, 0)

    # Extract features
    commands_per_min = _calculate_commands_per_minute(logs)
    unique_commands = _calculate_unique_commands(logs, protocol)
    duration = _calculate_session_duration(logs)
    error_ratio = _calculate_error_ratio(logs, protocol)
    privesc = _detect_privilege_escalation(logs, protocol)

    # Discretize features
    state = (
        _discretize(commands_per_min, STATE_BUCKETS["commands_per_minute"]),
        _discretize(unique_commands, STATE_BUCKETS["unique_commands"]),
        _discretize(duration, STATE_BUCKETS["session_duration"]),
        _discretize(error_ratio, STATE_BUCKETS["error_ratio"]),
        1 if privesc else 0,
    )

    return state


def _load_session_logs(session_id: str, protocol: str) -> List[Dict]:
    """
    Load session logs from storage.

    Args:
        session_id: Session ID
        protocol: Protocol type

    Returns:
        List of log entries (dicts)
    """
    log_dir = f"storage/session_logs/{protocol}"
    log_path = os.path.join(log_dir, f"{session_id}.jsonl")

    if not os.path.exists(log_path):
        return []

    logs = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
    except Exception as e:
        print(f"[StateExtractor] Error loading logs: {e}")
        return []

    return logs


def _calculate_commands_per_minute(logs: List[Dict]) -> float:
    """
    Calculate command/query/request rate.

    Args:
        logs: Session logs

    Returns:
        Commands per minute (float)
    """
    if not logs:
        return 0.0

    # Get time span
    timestamps = [log.get("timestamp", 0) for log in logs]
    if not timestamps:
        return 0.0

    duration_seconds = max(timestamps) - min(timestamps)

    if duration_seconds < 1:
        # Very short session - use count directly
        return float(len(logs))

    # Convert to commands per minute
    commands_per_min = (len(logs) / duration_seconds) * 60.0

    return commands_per_min


def _calculate_unique_commands(logs: List[Dict], protocol: str) -> int:
    """
    Count unique commands/queries/paths.

    Args:
        logs: Session logs
    Returns:
        Number of unique actions
    """
    if not logs:
        return 0

    unique = set()

    for log in logs:
        input_data = log.get("input_data", "")

        if protocol == "ssh":
            # Extract command name (first word)
            cmd = input_data.split()[0] if input_data.split() else ""
            if cmd:
                unique.add(cmd)

        elif protocol == "http":
            # Extract path (ignore query parameters)
            path = input_data.split()[1] if len(input_data.split()) > 1 else ""
            path = path.split("?")[0]  # Remove query string
            if path:
                unique.add(path)

        elif protocol == "database":
            # Extract query type (SELECT, INSERT, etc.)
            query_upper = input_data.upper().strip()
            query_type = query_upper.split()[0] if query_upper.split() else ""
            if query_type:
                unique.add(query_type)

        return len(unique)


def _calculate_session_duration(logs: List[Dict]) -> float:
    """
    Calculate session duration in seconds.
    Args:
        logs: Session logs

    Returns:
        Duration in seconds
    """
    if not logs:
        return 0.0

    timestamps = [log.get("timestamp", 0) for log in logs]

    if not timestamps:
        return 0.0

    return max(timestamps) - min(timestamps)


def _calculate_error_ratio(logs: List[Dict], protocol: str) -> float:
    """
    Calculate ratio of failed/error responses.
    Args:
        logs: Session logs
        protocol: Protocol type

    Returns:
        Error ratio (0.0 to 1.0)
    """
    if not logs:
        return 0.0

    total = len(logs)
    errors = 0

    for log in logs:
        metadata = log.get("metadata", {})

        if protocol == "ssh":
            # Check for command not found, permission denied, etc.
            if not log.get("success", True):
                errors += 1

        elif protocol == "http":
            # Check for 4xx/5xx status codes
            status_code = metadata.get("status_code", 200)
            if status_code >= 400:
                errors += 1

        elif protocol == "database":
            # Check for SQL errors
            if not log.get("success", True) or "ERROR" in str(
                log.get("input_data", "")
            ):
                errors += 1

    return errors / total if total > 0 else 0.0


def _detect_privilege_escalation(logs: List[Dict], protocol: str) -> bool:
    """
    Detect privilege escalation attempts.
    Args:
        logs: Session logs
        protocol: Protocol type

    Returns:
        True if privilege escalation detected
    """
    if not logs:
        return False

    settings = PROTOCOL_SETTINGS.get(protocol, {})

    for log in logs:
        input_data = log.get("input_data", "").lower()
        metadata = log.get("metadata", {})

        if protocol == "ssh":
            # Check for sudo, su, /etc/shadow, etc.
            privesc_commands = settings.get("privesc_commands", [])
            sensitive_files = settings.get("sensitive_files", [])

            for cmd in privesc_commands:
                if cmd.lower() in input_data:
                    return True

            for file in sensitive_files:
                if file.lower() in input_data:
                    return True

        elif protocol == "http":
            # Check for admin paths
            admin_paths = settings.get("admin_paths", [])

            for path in admin_paths:
                if path.lower() in input_data:
                    return True

        elif protocol == "database":
            # Check for mysql.user, GRANT, etc.
            injection_keywords = settings.get("injection_keywords", [])

            if "mysql.user" in input_data or "grant" in input_data:
                return True

            for keyword in injection_keywords:
                if keyword.lower() in input_data:
                    return True

    return False


def _discretize(value: float, thresholds: List[float]) -> int:
    """
    Discretize continuous value into LOW/MED/HIGH bucket.
    Args:
        value: Continuous value
        thresholds: [low_threshold, high_threshold]

    Returns:
        0 (LOW), 1 (MED), or 2 (HIGH)
    """
    if value < thresholds[0]:
        return 0  # LOW
    elif value < thresholds[1]:
        return 1  # MED
    else:
        return 2  # HIGH


"""
==============================================================================
TESTING
==============================================================================
"""
if __name__ == "__main__":
    # Test state extraction
    print("Testing state extraction...")
    # Create test logs directory
    os.makedirs("storage/session_logs/ssh", exist_ok=True)

    # Create test session logs
    test_session_id = "test_session_001"
    test_logs = [
        {
            "timestamp": time.time(),
            "input_data": "ls -la",
            "success": True,
            "metadata": {},
        },
        {
            "timestamp": time.time() + 1,
            "input_data": "cat /etc/passwd",
            "success": True,
            "metadata": {},
        },
        {
            "timestamp": time.time() + 2,
            "input_data": "sudo su",
            "success": False,
            "metadata": {},
        },
        {
            "timestamp": time.time() + 3,
            "input_data": "whoami",
            "success": True,
            "metadata": {},
        },
    ]

    # Save test logs
    log_path = f"storage/session_logs/ssh/{test_session_id}.jsonl"
    with open(log_path, "w") as f:
        for log in test_logs:
            f.write(json.dumps(log) + "\n")

    # Extract state
    state = extract_state(test_session_id, "ssh")
    print(f"Extracted state: {state}")
    print(f"  Commands/min: {state[0]} (0=LOW, 1=MED, 2=HIGH)")
    print(f"  Unique cmds:  {state[1]}")
    print(f"  Duration:     {state[2]}")
    print(f"  Error ratio:  {state[3]}")
    print(f"  Privesc:      {state[4]} (0=No, 1=Yes)")
