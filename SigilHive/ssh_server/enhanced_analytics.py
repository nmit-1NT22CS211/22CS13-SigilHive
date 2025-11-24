# enhanced_analytics.py
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class CommandEvent:
    session_id: str
    timestamp: datetime
    command: str
    intent: str
    current_dir: str
    response_preview: str
    delay: float
    success: bool


@dataclass
class SessionSummary:
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_commands: int
    unique_commands: int
    directories_visited: List[str]
    files_accessed: List[str]
    skill_level: str
    intent: str
    suspicious_count: int
    success_rate: float


class EnhancedAnalytics:
    """Advanced analytics and logging system"""

    def __init__(self, db_path: str = "honeypot_analytics.db"):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_database()

        # In-memory tracking
        self.active_sessions = {}  # session_id -> SessionSummary
        self.command_buffer = []  # Buffer for batch inserts
        self.buffer_size = 10

    def _init_database(self):
        """Initialize analytics database schema"""

        # Sessions table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                total_commands INTEGER,
                unique_commands INTEGER,
                skill_level TEXT,
                intent TEXT,
                suspicious_count INTEGER,
                success_rate REAL,
                ip_address TEXT,
                username TEXT
            )
        """)

        # Commands table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TIMESTAMP,
                command TEXT,
                intent TEXT,
                current_dir TEXT,
                response_preview TEXT,
                delay REAL,
                success BOOLEAN,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # Directories table (track navigation)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS directory_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                directory TEXT,
                visit_count INTEGER,
                first_visit TIMESTAMP,
                last_visit TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # Files accessed
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS file_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                filepath TEXT,
                access_type TEXT,
                timestamp TIMESTAMP,
                success BOOLEAN,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # Attack patterns
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS attack_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                pattern_type TEXT,
                pattern_data TEXT,
                severity TEXT,
                timestamp TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)

        # Create indexes for better query performance
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_id)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_commands_timestamp ON commands(timestamp)"
        )
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)"
        )

        self.db.commit()

    def log_command(self, event: CommandEvent):
        """Log a command event"""

        # Add to buffer
        self.command_buffer.append(event)

        # Update active session
        if event.session_id not in self.active_sessions:
            self.active_sessions[event.session_id] = SessionSummary(
                session_id=event.session_id,
                start_time=event.timestamp,
                end_time=None,
                total_commands=0,
                unique_commands=0,
                directories_visited=[],
                files_accessed=[],
                skill_level="unknown",
                intent="reconnaissance",
                suspicious_count=0,
                success_rate=0.0,
            )

        session = self.active_sessions[event.session_id]
        session.total_commands += 1
        session.end_time = event.timestamp

        # Track directory visits
        if event.current_dir not in session.directories_visited:
            session.directories_visited.append(event.current_dir)

        # Track file access
        if event.intent == "read_file":
            filename = self._extract_filename(event.command)
            if filename and filename not in session.files_accessed:
                session.files_accessed.append(filename)

        # Detect suspicious patterns
        if self._is_suspicious_command(event.command):
            session.suspicious_count += 1

        # Flush buffer if full
        if len(self.command_buffer) >= self.buffer_size:
            self._flush_command_buffer()

    def _flush_command_buffer(self):
        """Batch insert commands to database"""

        if not self.command_buffer:
            return

        try:
            self.db.executemany(
                """
                INSERT INTO commands 
                (session_id, timestamp, command, intent, current_dir, 
                 response_preview, delay, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        event.session_id,
                        event.timestamp,
                        event.command,
                        event.intent,
                        event.current_dir,
                        event.response_preview[:500],  # Limit size
                        event.delay,
                        event.success,
                    )
                    for event in self.command_buffer
                ],
            )

            self.db.commit()
            self.command_buffer.clear()

        except Exception as e:
            print(f"[Analytics] Error flushing buffer: {e}")

    def end_session(self, session_id: str, profile: Dict[str, Any]):
        """Mark session as ended and save summary"""

        if session_id not in self.active_sessions:
            return

        # Flush any pending commands
        self._flush_command_buffer()

        session = self.active_sessions[session_id]
        session.skill_level = profile.get("skill_level", "unknown")
        session.intent = profile.get("intent", "reconnaissance")

        # Calculate success rate
        cursor = self.db.execute(
            """
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM commands
            WHERE session_id = ?
        """,
            (session_id,),
        )

        result = cursor.fetchone()
        if result and result[0] > 0:
            session.success_rate = (result[1] / result[0]) * 100

        # Count unique commands
        cursor = self.db.execute(
            """
            SELECT COUNT(DISTINCT command) FROM commands WHERE session_id = ?
        """,
            (session_id,),
        )
        session.unique_commands = cursor.fetchone()[0]

        # Save session summary
        self.db.execute(
            """
            INSERT OR REPLACE INTO sessions
            (session_id, start_time, end_time, total_commands, unique_commands,
             skill_level, intent, suspicious_count, success_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                session.session_id,
                session.start_time,
                session.end_time,
                session.total_commands,
                session.unique_commands,
                session.skill_level,
                session.intent,
                session.suspicious_count,
                session.success_rate,
            ),
        )

        self.db.commit()

        # Clean up
        del self.active_sessions[session_id]

    def generate_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate comprehensive analytics report"""

        cutoff = datetime.now() - timedelta(hours=hours)

        # Session statistics
        cursor = self.db.execute(
            """
            SELECT 
                COUNT(*) as total_sessions,
                AVG(total_commands) as avg_commands,
                AVG(success_rate) as avg_success_rate,
                SUM(suspicious_count) as total_suspicious
            FROM sessions
            WHERE start_time > ?
        """,
            (cutoff,),
        )

        stats = cursor.fetchone()

        # Top commands
        cursor = self.db.execute(
            """
            SELECT command, COUNT(*) as count
            FROM commands
            WHERE timestamp > ?
            GROUP BY command
            ORDER BY count DESC
            LIMIT 20
        """,
            (cutoff,),
        )

        top_commands = dict(cursor.fetchall())

        # Intent distribution
        cursor = self.db.execute(
            """
            SELECT intent, COUNT(*) as count
            FROM sessions
            WHERE start_time > ?
            GROUP BY intent
        """,
            (cutoff,),
        )

        intent_dist = dict(cursor.fetchall())

        # Skill level distribution
        cursor = self.db.execute(
            """
            SELECT skill_level, COUNT(*) as count
            FROM sessions
            WHERE start_time > ?
            GROUP BY skill_level
        """,
            (cutoff,),
        )

        skill_dist = dict(cursor.fetchall())

        # Most accessed directories
        cursor = self.db.execute(
            """
            SELECT current_dir, COUNT(*) as visits
            FROM commands
            WHERE timestamp > ?
            GROUP BY current_dir
            ORDER BY visits DESC
            LIMIT 10
        """,
            (cutoff,),
        )

        top_dirs = dict(cursor.fetchall())

        # Command intent breakdown
        cursor = self.db.execute(
            """
            SELECT intent, COUNT(*) as count
            FROM commands
            WHERE timestamp > ?
            GROUP BY intent
            ORDER BY count DESC
        """,
            (cutoff,),
        )

        intent_breakdown = dict(cursor.fetchall())

        # Hourly activity
        hourly_activity = self._get_hourly_activity(cutoff)

        # Attack patterns
        attack_patterns = self._detect_attack_patterns(cutoff)

        report = {
            "period": f"Last {hours} hours",
            "generated_at": datetime.now().isoformat(),
            "statistics": {
                "total_sessions": stats[0] if stats else 0,
                "avg_commands_per_session": round(stats[1], 2)
                if stats and stats[1]
                else 0,
                "avg_success_rate": round(stats[2], 2) if stats and stats[2] else 0,
                "total_suspicious_activities": stats[3] if stats and stats[3] else 0,
            },
            "top_commands": top_commands,
            "intent_distribution": intent_dist,
            "skill_level_distribution": skill_dist,
            "top_directories": top_dirs,
            "command_intent_breakdown": intent_breakdown,
            "hourly_activity": hourly_activity,
            "attack_patterns": attack_patterns,
            "recommendations": self._generate_recommendations(
                intent_dist, attack_patterns
            ),
        }

        return report

    def _get_hourly_activity(self, since: datetime) -> List[Dict[str, Any]]:
        """Get hourly command activity"""

        cursor = self.db.execute(
            """
            SELECT 
                strftime('%Y-%m-%d %H:00', timestamp) as hour,
                COUNT(*) as command_count,
                COUNT(DISTINCT session_id) as session_count
            FROM commands
            WHERE timestamp > ?
            GROUP BY hour
            ORDER BY hour
        """,
            (since,),
        )

        return [
            {"hour": row[0], "commands": row[1], "sessions": row[2]}
            for row in cursor.fetchall()
        ]

    def _detect_attack_patterns(self, since: datetime) -> List[Dict[str, Any]]:
        """Detect common attack patterns"""

        patterns = []

        # SQL injection attempts
        cursor = self.db.execute(
            """
            SELECT session_id, COUNT(*) as count
            FROM commands
            WHERE timestamp > ?
            AND (command LIKE '%union%select%' OR command LIKE '%or%1=1%')
            GROUP BY session_id
        """,
            (since,),
        )

        for row in cursor.fetchall():
            patterns.append(
                {
                    "type": "sql_injection",
                    "session_id": row[0],
                    "count": row[1],
                    "severity": "high",
                }
            )

        # Privilege escalation attempts
        cursor = self.db.execute(
            """
            SELECT session_id, COUNT(*) as count
            FROM commands
            WHERE timestamp > ?
            AND command LIKE '%sudo%'
            GROUP BY session_id
            HAVING count > 3
        """,
            (since,),
        )

        for row in cursor.fetchall():
            patterns.append(
                {
                    "type": "privilege_escalation",
                    "session_id": row[0],
                    "count": row[1],
                    "severity": "high",
                }
            )

        # Credential harvesting
        cursor = self.db.execute(
            """
            SELECT session_id, COUNT(*) as count
            FROM commands
            WHERE timestamp > ?
            AND (command LIKE '%passwd%' OR command LIKE '%shadow%' 
                 OR command LIKE '%.env%' OR command LIKE '%config%')
            GROUP BY session_id
            HAVING count > 5
        """,
            (since,),
        )

        for row in cursor.fetchall():
            patterns.append(
                {
                    "type": "credential_harvesting",
                    "session_id": row[0],
                    "count": row[1],
                    "severity": "medium",
                }
            )

        return patterns

    def _generate_recommendations(
        self, intent_dist: Dict, patterns: List[Dict]
    ) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Check for high credential harvesting
        if intent_dist.get("credential_harvesting", 0) > 5:
            recommendations.append(
                "High credential harvesting activity detected. "
                "Consider rotating credentials and reviewing access logs."
            )

        # Check for privilege escalation patterns
        priv_esc_count = sum(1 for p in patterns if p["type"] == "privilege_escalation")
        if priv_esc_count > 3:
            recommendations.append(
                f"{priv_esc_count} privilege escalation attempts detected. "
                "Review sudo configurations and access controls."
            )

        # Check for SQL injection
        sql_inj_count = sum(1 for p in patterns if p["type"] == "sql_injection")
        if sql_inj_count > 0:
            recommendations.append(
                f"{sql_inj_count} SQL injection attempts detected. "
                "Ensure WAF rules are up to date."
            )

        # Default recommendation
        if not recommendations:
            recommendations.append("No critical issues detected. Continue monitoring.")

        return recommendations

    def _extract_filename(self, command: str) -> Optional[str]:
        """Extract filename from command"""
        parts = command.split()
        if len(parts) > 1:
            return parts[1]
        return None

    def _is_suspicious_command(self, command: str) -> bool:
        """Check if command is suspicious"""
        suspicious_patterns = [
            "rm -rf",
            "chmod 777",
            "wget http",
            "curl http",
            "nc -e",
            "bash -i",
            "/etc/passwd",
            "/etc/shadow",
            "base64",
            "eval",
            "exec",
        ]

        return any(pattern in command.lower() for pattern in suspicious_patterns)

    def get_session_timeline(self, session_id: str) -> List[Dict[str, Any]]:
        """Get complete timeline for a session"""

        cursor = self.db.execute(
            """
            SELECT timestamp, command, intent, current_dir, success
            FROM commands
            WHERE session_id = ?
            ORDER BY timestamp
        """,
            (session_id,),
        )

        return [
            {
                "timestamp": row[0],
                "command": row[1],
                "intent": row[2],
                "directory": row[3],
                "success": bool(row[4]),
            }
            for row in cursor.fetchall()
        ]

    def export_to_json(self, hours: int = 24) -> str:
        """Export analytics to JSON format"""
        report = self.generate_report(hours)
        return json.dumps(report, indent=2, default=str)

    def close(self):
        """Close database connection"""
        self._flush_command_buffer()
        self.db.close()
