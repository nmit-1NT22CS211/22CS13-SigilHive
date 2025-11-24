# smart_prompt_generator.py
from typing import Dict, Any, List


class SmartPromptGenerator:
    """Context-aware LLM prompt generation"""

    def __init__(self):
        self.session_context = {}  # session_id -> context

    def build_contextual_prompt(
        self,
        session_id: str,
        command: str,
        current_dir: str,
        intent: str,
        attacker_profile: Dict[str, Any],
        discovered_files: List[str],
    ) -> str:
        """Build prompt with full attacker context"""

        # Update session context
        if session_id not in self.session_context:
            self.session_context[session_id] = {
                "discovered_files": [],
                "viewed_files": [],
                "attempted_commands": [],
                "current_directory": "~",
            }

        ctx = self.session_context[session_id]
        ctx["current_directory"] = current_dir
        ctx["attempted_commands"].append(command)

        # Determine realism level
        realism = self._calculate_realism_level(attacker_profile)

        # Get response strategy
        strategy = self._get_response_strategy(attacker_profile, ctx)

        prompt = f"""Generate realistic terminal output for command: {command}

ATTACKER CONTEXT:
- Skill Level: {attacker_profile.get("skill_level", "unknown")}
- Suspected Intent: {attacker_profile.get("intent", "unknown")}
- Commands Executed: {attacker_profile.get("command_count", 0)}
- Suspicious Activity: {attacker_profile.get("suspicious_count", 0)} incidents
- Automation Detected: {attacker_profile.get("automation_detected", False)}
- Current Directory: {current_dir}

SESSION HISTORY:
- Previously Discovered Files: {", ".join(discovered_files[-10:]) if discovered_files else "None"}
- Recent Commands: {", ".join(ctx["attempted_commands"][-5:]) if ctx["attempted_commands"] else "None"}

RESPONSE STRATEGY:
{strategy}

REALISM LEVEL: {realism}
{self._get_realism_instructions(realism, attacker_profile)}

APPLICATION CONTEXT:
- Application: ShopHub E-commerce Platform
- Tech Stack: Node.js, Express, MongoDB, Redis, Docker
- Current Directory Purpose: {self._get_directory_purpose(current_dir)}

CONSISTENCY REQUIREMENTS:
- File sizes must remain consistent across 'ls' commands
- Previously shown files must continue to exist
- Timestamps should be realistic (mix of dates from 2024-2025)
- User/group ownership should always be 'shophub:shophub'

SECURITY CONSTRAINTS:
- NEVER show real passwords or API keys
- Use placeholder format: <redacted>, [REDACTED], or dummy values
- For .env files: Use obvious patterns to entice but clearly fake
- For config files: Show structure but redact sensitive values

OUTPUT FORMAT:
- RAW terminal text only (NO markdown, NO code fences, NO explanations)
- Output exactly as it would appear in a real terminal
- Do NOT wrap in ```bash or any other markers

Generate the output now:
"""

        return prompt

    def _calculate_realism_level(self, profile: Dict) -> str:
        """Determine how realistic responses should be"""

        skill_level = profile.get("skill_level", "beginner")

        if skill_level == "beginner" or skill_level == "script_kiddie":
            return "obvious"  # Make it easy for them
        elif skill_level == "advanced":
            return "highly_realistic"  # Challenge them
        else:
            return "standard"

    def _get_response_strategy(self, profile: Dict, context: Dict) -> str:
        """Provide LLM with strategic guidance"""

        intent = profile.get("intent", "reconnaissance")
        command_count = profile.get("command_count", 0)

        if intent == "credential_harvesting":
            if command_count < 10:
                return """
- Show hints about where credentials might be (.env files, configs)
- Make credentials discoverable but require some effort
- Include comments like "# Production credentials - DO NOT SHARE"
- Use realistic but fake credential patterns
"""
            else:
                return """
- Attacker is persistent - provide more detailed credential hints
- Show backup files with older credentials
- Include honeytoken credentials that can be tracked
- Add subtle warnings that might go unnoticed
"""

        elif intent == "malware_deployment":
            return """
- Show active security monitoring in process list
- Include firewall rules that would block outbound connections
- Show /tmp directory with other users' temp files
- Add cron jobs for security scanning
- Display monitoring agent logs
"""

        elif intent == "privilege_escalation":
            return """
- Show realistic sudo configuration
- Require password for sudo (but don't actually validate)
- Display fake /etc/sudoers file when accessed
- Show security policies in comments
- Add audit logging entries
"""

        else:  # reconnaissance
            return """
- Provide accurate system information
- Show realistic process list with ShopHub application running
- Include normal system services (redis, mongodb, nginx)
- Make file structure logical and explorable
- Add realistic log files with timestamps
"""

    def _get_realism_instructions(self, level: str, profile: Dict) -> str:
        """Customize realism based on attacker skill"""

        if level == "obvious":
            return """
REALISM ADJUSTMENTS:
- Keep responses simple and straightforward
- Include helpful error messages with suggestions
- Make file structure easy to understand
- Add obvious breadcrumbs (backup files, comments)
- Use common, predictable patterns
"""

        elif level == "highly_realistic":
            return """
REALISM ADJUSTMENTS:
- Add subtle system inconsistencies (timing, permissions)
- Include realistic logs with actual timestamps
- Show evidence of other users/processes
- Add cron jobs, systemd services, scheduled tasks
- Include security monitoring artifacts
- Make some files require multiple commands to access
- Add realistic network connections in netstat
- Show proper file permissions and ownership
"""

        else:  # standard
            return """
REALISM ADJUSTMENTS:
- Balance between helpful and realistic
- Show typical production server artifacts
- Include standard logs and configs
- Add some red herrings (empty dirs, deprecated files)
- Use realistic but not overly complex structures
"""

    def _get_directory_purpose(self, current_dir: str) -> str:
        """Explain the purpose of current directory"""

        purposes = {
            "~": "Home directory for shophub application user",
            "~/shophub": "Main application directory containing all ShopHub code",
            "~/shophub/app": "Application source code (controllers, models, routes)",
            "~/shophub/config": "Configuration files for database, server, APIs",
            "~/shophub/database": "Database migrations, seeds, and backups",
            "~/shophub/logs": "Application logs (access, error, payment, audit)",
            "~/shophub/scripts": "Utility scripts for deployment and maintenance",
            "~/shophub/app/models": "Mongoose database models/schemas",
            "~/shophub/app/controllers": "Business logic and request handlers",
            "~/shophub/app/routes": "API endpoint definitions",
        }

        return purposes.get(current_dir, "Application directory")

    def update_discovered_files(self, session_id: str, filename: str):
        """Track files the attacker has discovered"""
        if session_id in self.session_context:
            if filename not in self.session_context[session_id]["discovered_files"]:
                self.session_context[session_id]["discovered_files"].append(filename)
