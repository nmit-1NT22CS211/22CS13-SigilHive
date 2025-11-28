# config.py
from typing import Dict, Any


class HoneypotConfig:
    """Configuration for honeypot enhancements"""

    # Cache settings
    CACHE_MEMORY_SIZE = 100
    CACHE_TTL = 3600  # 1 hour
    CACHE_CLEANUP_INTERVAL = 300  # 5 minutes

    # Analytics settings
    ANALYTICS_DB_PATH = "honeypot_analytics.db"
    ANALYTICS_BUFFER_SIZE = 10
    ANALYTICS_REPORT_HOURS = 24

    # Adaptive response settings
    ADAPTIVE_RESPONSE_ENABLED = True
    ADAPTIVE_ERROR_RATE = {"beginner": 0.1, "intermediate": 0.05, "advanced": 0.02}

    # Filesystem evolution settings
    FS_EVOLUTION_INTERVAL = 600  # 10 minutes
    FS_LOG_RETENTION_HOURS = 24
    FS_TEMP_FILE_CLEANUP_HOURS = 1

    # Prompt generation settings
    PROMPT_REALISM_LEVELS = {
        "obvious": "Make it easy for beginners",
        "standard": "Balanced realism",
        "highly_realistic": "Maximum realism for advanced attackers",
    }

    # Prefetch settings
    PREFETCH_ENABLED = True
    PREFETCH_QUEUE_SIZE = 50
    PREFETCH_TOP_N_COMMANDS = 5

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get all config as dictionary"""
        return {
            "cache": {
                "memory_size": cls.CACHE_MEMORY_SIZE,
                "ttl": cls.CACHE_TTL,
                "cleanup_interval": cls.CACHE_CLEANUP_INTERVAL,
            },
            "analytics": {
                "db_path": cls.ANALYTICS_DB_PATH,
                "buffer_size": cls.ANALYTICS_BUFFER_SIZE,
                "report_hours": cls.ANALYTICS_REPORT_HOURS,
            },
            "adaptive_response": {
                "enabled": cls.ADAPTIVE_RESPONSE_ENABLED,
                "error_rates": cls.ADAPTIVE_ERROR_RATE,
            },
            "filesystem": {
                "evolution_interval": cls.FS_EVOLUTION_INTERVAL,
                "log_retention_hours": cls.FS_LOG_RETENTION_HOURS,
                "temp_cleanup_hours": cls.FS_TEMP_FILE_CLEANUP_HOURS,
            },
            "prefetch": {
                "enabled": cls.PREFETCH_ENABLED,
                "queue_size": cls.PREFETCH_QUEUE_SIZE,
                "top_n": cls.PREFETCH_TOP_N_COMMANDS,
            },
        }
