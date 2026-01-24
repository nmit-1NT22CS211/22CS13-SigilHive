"""
Configuration file for RL-based adaptive honeypot system.

Contains all hyperparameters, thresholds, and settings.
No hardcoded values should exist elsewhere.
"""

import os

# ==============================================================================
# Q-LEARNING HYPERPARAMETERS
# ==============================================================================

RL_CONFIG = {
    # Learning parameters
    "learning_rate": 0.1,  # α - How much to update Q-values (0.0 to 1.0)
    "discount_factor": 0.95,  # γ - Importance of future rewards (0.0 to 1.0)
    # Exploration parameters
    "epsilon_start": 1.0,  # Initial exploration rate (100% random)
    "epsilon_min": 0.01,  # Minimum exploration rate (1% random)
    "epsilon_decay": 0.9995,  # Decay rate per action
    # Persistence
    "q_table_path": "storage/q_table.pkl",
    "save_interval": 100,  # Save Q-table every N updates
    # Default Q-value for unseen states
    "default_q_value": 0.0,
}


# ==============================================================================
# REWARD FUNCTION WEIGHTS
# ==============================================================================

REWARD_CONFIG = {
    # Positive rewards (encourage engagement)
    "alpha": 1.0,  # Weight for session duration increase
    "beta": 2.0,  # Weight for unique commands/queries
    # Negative rewards (penalize mistakes)
    "gamma1": 5.0,  # Penalty for honeypot detection
    "gamma2": 3.0,  # Penalty for early termination
    # Protocol-specific bonuses
    "ssh_file_access_bonus": 2.0,
    "ssh_privesc_bonus": 3.0,
    "ssh_persistence_bonus": 4.0,
    "http_path_diversity_bonus": 1.5,
    "http_admin_access_bonus": 2.5,
    "http_honeytoken_bonus": 5.0,
    "db_table_enum_bonus": 2.0,
    "db_injection_attempt_bonus": 1.5,
    "db_honeytoken_bonus": 5.0,
}


# ==============================================================================
# STATE DISCRETIZATION BUCKETS
# ==============================================================================

STATE_BUCKETS = {
    # Format: [low_threshold, high_threshold]
    # Values: LOW (0): < low_threshold
    #         MED (1): low_threshold to high_threshold
    #         HIGH (2): > high_threshold
    "commands_per_minute": [0.5, 2.0],  # Commands/queries/requests per minute
    "unique_commands": [3, 10],  # Number of unique actions
    "session_duration": [60, 300],  # Seconds (1 min, 5 min)
    "error_ratio": [0.3, 0.7],  # Ratio of failed operations
}


# ==============================================================================
# PROTOCOL-SPECIFIC SETTINGS
# ==============================================================================

PROTOCOL_SETTINGS = {
    "database": {
        "suspicious_patterns_weight": 1.5,
        "table_enumeration_threshold": 3,  # Number of SHOW TABLES queries
        "injection_keywords": [
            "UNION SELECT",
            "OR 1=1",
            "'; DROP",
            "--",
            "LOAD_FILE",
            "INTO OUTFILE",
            "BENCHMARK",
        ],
    },
    "http": {
        "path_diversity_threshold": 5,  # Unique paths to count as diverse
        "admin_paths": ["/admin", "/.git", "/.env", "/config", "/backup"],
        "scanner_user_agents": ["nikto", "sqlmap", "nmap", "metasploit"],
    },
    "ssh": {
        "sensitive_files": [
            "/etc/passwd",
            "/etc/shadow",
            ".ssh/id_rsa",
            ".env",
            "config",
            "credentials",
        ],
        "privesc_commands": ["sudo", "su", "chmod 777", "usermod"],
        "persistence_indicators": ["crontab", "systemd", ".bashrc", ".profile"],
    },
}


# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING_CONFIG = {
    "session_log_dir": "storage/session_logs",
    "log_format": "jsonl",  # JSON Lines format
    "max_session_logs": 1000,  # Keep last N sessions per protocol
    "log_rotation_size_mb": 100,  # Rotate logs at this size
}


# ==============================================================================
# BASELINE CONTROLLER THRESHOLDS (for comparison)
# ==============================================================================

BASELINE_CONFIG = {
    # Simple rule-based thresholds
    "high_activity_threshold": 5,  # Commands per minute
    "suspicious_error_threshold": 0.5,  # Error ratio
    "quick_disconnect_threshold": 30,  # Seconds
    # Action selection rules
    "use_deceptive_resource_on_privesc": True,
    "delay_on_high_activity": True,
    "terminate_on_scanner_detected": False,
}


# ==============================================================================
# ENVIRONMENT VARIABLE OVERRIDES
# ==============================================================================

# Allow runtime configuration via environment variables
if os.getenv("RL_LEARNING_RATE"):
    RL_CONFIG["learning_rate"] = float(os.getenv("RL_LEARNING_RATE"))

if os.getenv("RL_EPSILON_START"):
    RL_CONFIG["epsilon_start"] = float(os.getenv("RL_EPSILON_START"))

if os.getenv("REWARD_DURATION_WEIGHT"):
    REWARD_CONFIG["alpha"] = float(os.getenv("REWARD_DURATION_WEIGHT"))

if os.getenv("REWARD_COMMANDS_WEIGHT"):
    REWARD_CONFIG["beta"] = float(os.getenv("REWARD_COMMANDS_WEIGHT"))


# ==============================================================================
# VALIDATION
# ==============================================================================


def validate_config():
    """Validate configuration values are in valid ranges"""
    assert 0.0 <= RL_CONFIG["learning_rate"] <= 1.0, "Learning rate must be in [0, 1]"
    assert 0.0 <= RL_CONFIG["discount_factor"] <= 1.0, (
        "Discount factor must be in [0, 1]"
    )
    assert 0.0 <= RL_CONFIG["epsilon_start"] <= 1.0, "Epsilon start must be in [0, 1]"
    assert 0.0 <= RL_CONFIG["epsilon_min"] <= 1.0, "Epsilon min must be in [0, 1]"
    assert RL_CONFIG["epsilon_min"] <= RL_CONFIG["epsilon_start"], (
        "Epsilon min must be <= epsilon start"
    )

    # Validate state buckets
    for key, thresholds in STATE_BUCKETS.items():
        assert len(thresholds) == 2, f"{key} must have exactly 2 thresholds"
        assert thresholds[0] < thresholds[1], f"{key} thresholds must be ascending"

    print("[Config] ✅ Configuration validated successfully")


# Run validation on import
validate_config()
