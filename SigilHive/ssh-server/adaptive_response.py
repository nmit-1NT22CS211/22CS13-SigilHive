# adaptive_response.py
import random
from typing import Dict, Any, List


class AdaptiveResponseSystem:
    """Adapts honeypot behavior based on attacker actions"""

    def __init__(self):
        self.personas = {
            "beginner_sysadmin": {
                "response_delay": (0.5, 2.0),
                "error_rate": 0.1,
                "typo_rate": 0.05,
                "help_verbosity": "high",
            },
            "experienced_sysadmin": {
                "response_delay": (0.1, 0.5),
                "error_rate": 0.02,
                "typo_rate": 0.01,
                "help_verbosity": "medium",
            },
            "automated_system": {
                "response_delay": (0.01, 0.1),
                "error_rate": 0.0,
                "typo_rate": 0.0,
                "help_verbosity": "low",
            },
        }

        self.attacker_profiles = {}  # session_id -> profile

    def analyze_attacker_behavior(
        self, session_id: str, commands: List[str]
    ) -> Dict[str, Any]:
        """Analyze attacker behavior and build profile"""

        profile = {
            "skill_level": "beginner",
            "automation_detected": False,
            "intent": "reconnaissance",
            "command_count": len(commands),
            "suspicious_count": 0,
        }

        if not commands:
            return profile

        # Check for automation indicators
        if len(commands) > 20:
            # Check command frequency
            if len(set(commands[-10:])) < 3:  # Repetitive commands
                profile["automation_detected"] = True

        # Analyze typing speed (commands per minute)
        if len(commands) > 5:
            # If too fast, likely automated
            profile["automation_detected"] = True

        # Analyze skill level
        advanced_commands = ["strace", "ltrace", "gdb", "tcpdump", "nc", "socat"]
        script_kiddie_tools = ["sqlmap", "nmap -A", "nikto", "metasploit"]

        commands_str = " ".join(commands).lower()

        if any(tool in commands_str for tool in script_kiddie_tools):
            profile["skill_level"] = "script_kiddie"
        elif any(cmd in commands_str for cmd in advanced_commands):
            profile["skill_level"] = "advanced"
        elif len(commands) > 20 and "cat" in commands_str:
            profile["skill_level"] = "intermediate"

        # Infer intent
        if ".env" in commands_str or "password" in commands_str:
            profile["intent"] = "credential_harvesting"
        elif "curl" in commands_str or "wget" in commands_str:
            profile["intent"] = "malware_deployment"
        elif "sudo" in commands_str:
            profile["intent"] = "privilege_escalation"

        # Count suspicious patterns
        suspicious_patterns = ["rm -rf", "../", "passwd", "/etc/shadow", "chmod 777"]
        profile["suspicious_count"] = sum(
            1
            for cmd in commands
            if any(pattern in cmd.lower() for pattern in suspicious_patterns)
        )

        return profile

    def get_adaptive_response(
        self,
        session_id: str,
        command: str,
        base_response: str,
        commands_history: List[str],
    ) -> Dict[str, Any]:
        """Modify response based on attacker profile"""

        # Analyze behavior
        profile = self.analyze_attacker_behavior(session_id, commands_history)
        self.attacker_profiles[session_id] = profile

        # Choose persona
        if profile["automation_detected"]:
            persona = self.personas["automated_system"]
        elif profile["skill_level"] == "script_kiddie":
            persona = self.personas["beginner_sysadmin"]
        elif profile["skill_level"] == "advanced":
            persona = self.personas["experienced_sysadmin"]
        else:
            persona = self.personas["beginner_sysadmin"]

        # Add realistic delays
        delay = random.uniform(*persona["response_delay"])

        # Introduce occasional errors
        response = base_response
        if random.random() < persona["error_rate"]:
            response = self._inject_realistic_error(command, base_response)

        # Add typos for human-like behavior
        if random.random() < persona["typo_rate"]:
            response = self._add_typo(response)

        # Add breadcrumbs for persistent attackers
        if profile["command_count"] > 50:
            response = self._add_breadcrumb(response, profile)

        # Add system messages occasionally
        if random.random() < 0.05:
            response = self._add_system_message(response)

        return {
            "response": response,
            "delay": delay,
            "profile": profile,
            "persona": persona,
        }

    def _inject_realistic_error(self, command: str, response: str) -> str:
        """Inject believable system errors"""
        errors = [
            "bash: warning: setlocale: LC_ALL: cannot change locale (en_US.UTF-8)\n",
            "mesg: ttyname failed: Inappropriate ioctl for device\n",
            "-bash: /home/shophub/.bash_profile: Permission temporarily denied\n",
            "bash: cannot set terminal process group: Inappropriate ioctl\n",
        ]

        # Add error before response
        if random.random() < 0.5:
            return random.choice(errors) + response
        return response

    def _add_typo(self, response: str) -> str:
        """Add realistic typos"""
        # Only add typos to first line
        lines = response.split("\n")
        if lines and len(lines[0]) > 10:
            # Randomly duplicate a character
            pos = random.randint(0, min(len(lines[0]) - 1, 50))
            lines[0] = lines[0][:pos] + lines[0][pos] + lines[0][pos:]

        return "\n".join(lines)

    def _add_breadcrumb(self, response: str, profile: Dict) -> str:
        """Add hints for persistent attackers"""

        breadcrumbs = {
            "credential_harvesting": [
                "\n# Note: Check backup directory for old configs",
                "\n# Hint: .env.backup might contain useful info",
            ],
            "malware_deployment": [
                "\n# Note: /tmp directory monitored by security team",
                "\n# Hint: Outbound connections require approval",
            ],
            "privilege_escalation": [
                "\n# Note: sudo password required for all elevated commands",
                "\n# Hint: Check /etc/sudoers.d/ for custom rules",
            ],
        }

        intent = profile.get("intent", "reconnaissance")
        if intent in breadcrumbs:
            response += random.choice(breadcrumbs[intent])

        return response

    def _add_system_message(self, response: str) -> str:
        """Add occasional system messages"""
        messages = [
            "\n[System] Backup process running in background (PID 3421)",
            "\n[System] Log rotation scheduled for 02:00 UTC",
            "\n[System] Monitoring agent: All checks passed",
            "\n[System] Disk usage: 67% (within normal limits)",
        ]

        return response + random.choice(messages)

    def get_attacker_profile(self, session_id: str) -> Dict[str, Any]:
        """Get stored attacker profile"""
        return self.attacker_profiles.get(session_id, {})
