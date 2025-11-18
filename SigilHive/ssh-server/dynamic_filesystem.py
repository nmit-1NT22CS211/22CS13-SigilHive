# dynamic_filesystem.py
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List


class DynamicFileSystem:
    """File system that evolves based on attacker activity"""

    def __init__(self, base_structure: Dict):
        self.structure = self._deep_copy(base_structure)
        self.file_metadata = {}  # path -> metadata
        self.file_contents_cache = {}  # path -> content
        self.last_update = datetime.now()
        self.activity_log = []

    def _deep_copy(self, d: Dict) -> Dict:
        """Deep copy dictionary"""
        import copy

        return copy.deepcopy(d)

    def evolve_filesystem(self, session_id: str, commands: List[str]):
        """Modify filesystem based on attacker actions"""

        # Track activity
        self.activity_log.extend(commands[-10:])  # Keep last 10 commands

        # Add log entries when attacker is active
        if len(commands) > 10:
            self._update_logs(session_id, commands[-5:])

        # Add time-based changes
        if (datetime.now() - self.last_update).seconds > 300:  # Every 5 minutes
            self._add_time_based_changes()

        # Add reactive elements
        self._add_reactive_elements(commands)

        # Clean up old temporary files
        self._cleanup_old_temp_files()

    def _update_logs(self, session_id: str, recent_commands: List[str]):
        """Add log entries that reflect attacker activity"""

        timestamp = datetime.now()

        # Update access.log
        access_log_path = "~/shophub/logs/access.log"
        if access_log_path not in self.file_contents_cache:
            self.file_contents_cache[access_log_path] = ""

        for cmd in recent_commands:
            if "cat" in cmd:
                filename = cmd.replace("cat", "").strip()
                log_entry = f"{timestamp.strftime('%d/%b/%Y:%H:%M:%S +0000')} - File accessed: {filename} (session: {session_id})\n"
                self.file_contents_cache[access_log_path] += log_entry

        # Update audit.log
        audit_log_path = "~/shophub/logs/audit.log"
        if audit_log_path not in self.file_contents_cache:
            self.file_contents_cache[audit_log_path] = ""

        for cmd in recent_commands:
            if any(sus in cmd.lower() for sus in ["sudo", "passwd", "shadow"]):
                audit_entry = f"[{timestamp.isoformat()}] SECURITY: Suspicious command detected: {cmd} (session: {session_id})\n"
                self.file_contents_cache[audit_log_path] += audit_entry

    def _add_time_based_changes(self):
        """Add files/changes based on passage of time"""

        now = datetime.now()

        # Simulate cron jobs running
        if now.hour == 2 and now.minute < 5:  # 2 AM backup window
            backup_dir = "~/shophub/database/backup"
            if backup_dir in self.structure:
                backup_file = f"backup-{now.strftime('%Y-%m-%d')}.tar.gz"
                if backup_file not in self.structure[backup_dir].get("contents", []):
                    self.structure[backup_dir]["contents"].append(backup_file)
                    self.file_metadata[f"{backup_dir}/{backup_file}"] = {
                        "size": random.randint(50000, 150000),
                        "created": now,
                        "description": "Automated database backup",
                    }

        # Rotate logs every hour
        if now.minute == 0:
            self._rotate_logs()

        # Add temp files
        if random.random() < 0.1:  # 10% chance
            self._add_temp_files()

        self.last_update = now

    def _add_reactive_elements(self, commands: List[str]):
        """System reacts to attacker behavior"""

        recent_commands = commands[-10:] if len(commands) > 10 else commands

        # If attacker tries to create files
        for cmd in recent_commands:
            if any(c in cmd for c in ["touch", "echo >", "vim", "nano"]):
                # Next 'ls' will show they don't have permissions
                self.file_metadata["last_write_attempt"] = {
                    "command": cmd,
                    "result": "Permission denied",
                    "timestamp": datetime.now(),
                }

            # If attacker downloads tools
            if "wget" in cmd or "curl" in cmd:
                # Show in process list next time
                self.file_metadata["active_downloads"] = {
                    "command": cmd,
                    "timestamp": datetime.now(),
                    "show_in_ps": True,
                }

            # If attacker searches for passwords
            if "grep" in cmd and "password" in cmd.lower():
                # Add decoy password file
                self._add_decoy_password_file()

    def _rotate_logs(self):
        """Simulate log rotation"""

        log_dir = "~/shophub/logs"
        log_files = ["access.log", "error.log", "payment.log", "audit.log"]

        for log in log_files:
            archive_name = f"{log}.{datetime.now().strftime('%Y%m%d')}"
            archive_path = f"{log_dir}/{archive_name}"

            if log_dir in self.structure:
                if archive_name not in self.structure[log_dir].get("contents", []):
                    self.structure[log_dir]["contents"].append(archive_name)
                    self.file_metadata[archive_path] = {
                        "size": random.randint(1000, 50000),
                        "created": datetime.now(),
                        "compressed": False,
                    }

    def _add_temp_files(self):
        """Add temporary files that might interest attackers"""

        temp_files = [
            {
                "name": f".npm-debug-{random.randint(1000, 9999)}.log",
                "dir": "~",
                "content": "npm ERR! code ELIFECYCLE\nnpm ERR! errno 1\n",
            },
            {
                "name": f"core.{random.randint(10000, 99999)}",
                "dir": "~",
                "content": "[Core dump file]",
            },
            {
                "name": ".bash_history.backup",
                "dir": "~",
                "content": "ls\ncd shophub\ncat .env\n",
            },
        ]

        temp_file = random.choice(temp_files)
        dir_path = temp_file["dir"]

        if dir_path in self.structure:
            if temp_file["name"] not in self.structure[dir_path].get("contents", []):
                self.structure[dir_path]["contents"].append(temp_file["name"])
                file_path = f"{dir_path}/{temp_file['name']}"
                self.file_contents_cache[file_path] = temp_file["content"]

    def _add_decoy_password_file(self):
        """Add a decoy password file"""

        decoy_file = ".passwords_old.txt"
        home_dir = "~"

        if home_dir in self.structure:
            if decoy_file not in self.structure[home_dir].get("contents", []):
                self.structure[home_dir]["contents"].append(decoy_file)

                decoy_content = """# Old passwords - DEPRECATED
# Migrated to new auth system 2024-10

admin:OldPass123!
backup_user:BackupP@ss2023
deploy:D3pl0y2023!

# Note: These are no longer valid
# New system uses OAuth2
"""
                self.file_contents_cache[f"{home_dir}/{decoy_file}"] = decoy_content

    def _cleanup_old_temp_files(self):
        """Remove old temporary files to maintain realism"""

        # Remove temp files older than 1 hour (simulated)
        cutoff = datetime.now() - timedelta(hours=1)

        to_remove = []
        for path, metadata in self.file_metadata.items():
            if metadata.get("temporary", False):
                if metadata.get("created", datetime.now()) < cutoff:
                    to_remove.append(path)

        for path in to_remove:
            del self.file_metadata[path]
            if path in self.file_contents_cache:
                del self.file_contents_cache[path]

    def get_file_content(self, path: str) -> str:
        """Get dynamically generated or cached file content"""
        return self.file_contents_cache.get(path)

    def get_file_metadata(self, path: str) -> Dict[str, Any]:
        """Get file metadata"""
        return self.file_metadata.get(path, {})

    def get_structure(self) -> Dict:
        """Get current filesystem structure"""
        return self.structure
