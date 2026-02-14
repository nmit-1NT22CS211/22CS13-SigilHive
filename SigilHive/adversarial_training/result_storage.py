"""
Persistent Result Storage for Attack Data
Stores attack results in SQLite for querying and Grafana metrics export.
"""

import json
import logging
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class AttackResultStorage:
    """SQLite-based persistent storage for attack results."""

    def __init__(self, db_path: str = "attack_results.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Attack results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attack_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    attack_type TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    data_extracted INTEGER NOT NULL,
                    suspicion_level REAL NOT NULL,
                    duration REAL NOT NULL,
                    commands_executed TEXT,
                    responses TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_protocol (protocol),
                    INDEX idx_session (session_id)
                )
            """)
            
            # Evolution history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evolution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    reward_delta REAL NOT NULL,
                    changes_count INTEGER NOT NULL,
                    changes_made TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_strategy (strategy)
                )
            """)
            
            # Training metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS training_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    episode INTEGER NOT NULL,
                    step INTEGER NOT NULL,
                    epsilon REAL NOT NULL,
                    average_reward REAL NOT NULL,
                    buffer_size INTEGER NOT NULL,
                    evolutions_applied INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_episode (episode)
                )
            """)
            
            # Campaign statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    total_attacks INTEGER,
                    success_count INTEGER,
                    total_data_extracted INTEGER,
                    average_suspicion REAL,
                    protocols_used TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_session (session_id)
                )
            """)
            
            conn.commit()

    def store_attack_result(
        self,
        session_id: str,
        protocol: str,
        attack_type: str,
        success: bool,
        data_extracted: int,
        suspicion_level: float,
        duration: float,
        commands_executed: Optional[List[str]] = None,
        responses: Optional[List[str]] = None,
    ) -> int:
        """Store a single attack result."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attack_results (
                    timestamp, session_id, protocol, attack_type,
                    success, data_extracted, suspicion_level, duration,
                    commands_executed, responses
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().timestamp(),
                session_id,
                protocol,
                attack_type,
                success,
                data_extracted,
                suspicion_level,
                duration,
                json.dumps(commands_executed or []),
                json.dumps(responses or []),
            ))
            conn.commit()
            return cursor.lastrowid

    def store_evolution(
        self,
        session_id: str,
        strategy: str,
        reward_delta: float,
        changes_made: List[str],
    ) -> int:
        """Store an evolution event."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evolution_history (
                    timestamp, session_id, strategy, reward_delta,
                    changes_count, changes_made
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().timestamp(),
                session_id,
                strategy,
                reward_delta,
                len(changes_made),
                json.dumps(changes_made),
            ))
            conn.commit()
            return cursor.lastrowid

    def store_training_metrics(
        self,
        session_id: str,
        episode: int,
        step: int,
        epsilon: float,
        average_reward: float,
        buffer_size: int,
        evolutions_applied: int,
    ) -> int:
        """Store training metrics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO training_metrics (
                    timestamp, session_id, episode, step,
                    epsilon, average_reward, buffer_size, evolutions_applied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().timestamp(),
                session_id,
                episode,
                step,
                epsilon,
                average_reward,
                buffer_size,
                evolutions_applied,
            ))
            conn.commit()
            return cursor.lastrowid

    def get_attack_results(
        self,
        session_id: Optional[str] = None,
        protocol: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[dict]:
        """Query attack results."""
        query = "SELECT * FROM attack_results WHERE 1=1"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        if protocol:
            query += " AND protocol = ?"
            params.append(protocol)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_attack_statistics(self, session_id: Optional[str] = None) -> dict:
        """Get aggregate statistics about attacks."""
        where = ""
        params = []
        
        if session_id:
            where = " WHERE session_id = ?"
            params = [session_id]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total attacks
            cursor.execute(f"SELECT COUNT(*) FROM attack_results {where}", params)
            total_attacks = cursor.fetchone()[0]
            
            # Success rate
            cursor.execute(
                f"SELECT COUNT(*) FROM attack_results WHERE success = 1 {where}",
                params
            )
            successful = cursor.fetchone()[0]
            
            # Data extracted
            cursor.execute(
                f"SELECT SUM(data_extracted) FROM attack_results {where}",
                params
            )
            total_data = cursor.fetchone()[0] or 0
            
            # By protocol
            cursor.execute(
                f"SELECT protocol, COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END) "
                f"FROM attack_results {where} GROUP BY protocol",
                params
            )
            by_protocol = {
                row[0]: {"count": row[1], "success": row[2]}
                for row in cursor.fetchall()
            }
            
            # Average suspicion
            cursor.execute(
                f"SELECT AVG(suspicion_level) FROM attack_results {where}",
                params
            )
            avg_suspicion = cursor.fetchone()[0] or 0.0
            
        return {
            "total_attacks": total_attacks,
            "successful_attacks": successful,
            "success_rate": successful / total_attacks if total_attacks > 0 else 0.0,
            "total_data_extracted": total_data,
            "average_suspicion": avg_suspicion,
            "by_protocol": by_protocol,
        }

    def get_metrics_for_grafana(self, session_id: Optional[str] = None) -> List[dict]:
        """Export metrics in Prometheus format for Grafana."""
        metrics = []
        
        # Get attack results
        attacks = self.get_attack_results(session_id=session_id, limit=10000)
        
        for attack in attacks:
            timestamp_ms = int(attack["timestamp"] * 1000)
            
            metrics.append({
                "metric": "sigilhive_attack_success",
                "value": [timestamp_ms, 1 if attack["success"] else 0],
                "labels": {
                    "protocol": attack["protocol"],
                    "attack_type": attack["attack_type"],
                    "session_id": attack["session_id"],
                },
            })
            
            metrics.append({
                "metric": "sigilhive_data_extracted",
                "value": [timestamp_ms, attack["data_extracted"]],
                "labels": {
                    "protocol": attack["protocol"],
                    "session_id": attack["session_id"],
                },
            })
            
            metrics.append({
                "metric": "sigilhive_suspicion_level",
                "value": [timestamp_ms, attack["suspicion_level"]],
                "labels": {
                    "protocol": attack["protocol"],
                    "session_id": attack["session_id"],
                },
            })
            
            metrics.append({
                "metric": "sigilhive_attack_duration",
                "value": [timestamp_ms, attack["duration"]],
                "labels": {
                    "protocol": attack["protocol"],
                    "attack_type": attack["attack_type"],
                },
            })
        
        return metrics

    def export_metrics_prometheus(self, session_id: Optional[str] = None) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        attacks = self.get_attack_results(session_id=session_id, limit=10000)
        
        for attack in attacks:
            labels = f'protocol="{attack["protocol"]}", attack_type="{attack["attack_type"]}", session_id="{attack["session_id"]}"'
            timestamp = int(attack["timestamp"] * 1000)
            
            lines.append(f'sigilhive_attack_success{{{labels}}} {1 if attack["success"] else 0} {timestamp}')
            lines.append(f'sigilhive_data_extracted{{{labels}}} {attack["data_extracted"]} {timestamp}')
            lines.append(f'sigilhive_suspicion_level{{{labels}}} {attack["suspicion_level"]} {timestamp}')
            lines.append(f'sigilhive_attack_duration{{{labels}}} {attack["duration"]} {timestamp}')
        
        return "\n".join(lines)

    def clear_old_data(self, days: int = 30) -> None:
        """Clean up results older than specified days."""
        import time
        cutoff_timestamp = time.time() - (days * 86400)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attack_results WHERE timestamp < ?", (cutoff_timestamp,))
            cursor.execute("DELETE FROM evolution_history WHERE timestamp < ?", (cutoff_timestamp,))
            cursor.execute("DELETE FROM training_metrics WHERE timestamp < ?", (cutoff_timestamp,))
            conn.commit()
            logger.info(f"Cleaned up data older than {days} days")
