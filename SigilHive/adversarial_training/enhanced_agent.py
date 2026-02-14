"""
Integration wrapper for real attacks and result storage.
Patches the AdversarialAgent to use real attacks instead of simulations.
"""

import logging
from typing import Optional

from .adversarial_agent import AdversarialAgent, Protocol, AttackPhase
from .real_attacks import SSHAttacker, HTTPAttacker, DatabaseAttacker
from .result_storage import AttackResultStorage

logger = logging.getLogger(__name__)


class EnhancedAdversarialAgent(AdversarialAgent):
    """Extended AdversarialAgent with real attacks and result persistence."""

    def __init__(
        self,
        gemini_api_key: str,
        model_name: str = "gemini-1.5-flash",
        target_host: str = "localhost",
        ssh_port: int = 5555,
        http_port: int = 8080,
        db_port: int = 2225,
        storage: Optional[AttackResultStorage] = None,
    ):
        super().__init__(
            gemini_api_key=gemini_api_key,
            model_name=model_name,
            target_host=target_host,
            ssh_port=ssh_port,
            http_port=http_port,
            db_port=db_port,
        )
        
        # Initialize result storage
        self.storage = storage or AttackResultStorage()
        
        # Initialize real attackers
        self.ssh_attacker = SSHAttacker(target_host, ssh_port)
        self.http_attacker = HTTPAttacker(target_host, http_port)
        self.db_attacker = DatabaseAttacker(target_host, db_port)
        
        logger.info(f"Enhanced agent ready with real attacks | session={self.session_id}")

    def _execute_real_attack(self, protocol: str, attack_type: str):
        """Execute real attacks against honeypot services."""
        try:
            if protocol == Protocol.SSH or protocol == "ssh":
                if attack_type == "recon":
                    return self.ssh_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.ssh_attacker.attack_exploit()
            
            elif protocol == Protocol.HTTP or protocol == "http":
                if attack_type == "recon":
                    return self.http_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.http_attacker.attack_exploit()
            
            elif protocol == Protocol.DATABASE or protocol == "database":
                if attack_type == "recon":
                    return self.db_attacker.attack_recon()
                elif attack_type == "exploit":
                    return self.db_attacker.attack_exploit()
        
        except Exception as e:
            logger.warning(f"Real attack failed: {e}")
            return False, [], []
        
        return False, [], []

    def _recon_node(self, state):
        """Reconnaissance node - execute real SSH/HTTP/DB recon."""
        proto_str = state.get("protocol", "ssh")
        if hasattr(proto_str, "value"):
            proto_str = proto_str.value
        
        success, responses, metrics = self._execute_real_attack(proto_str, "recon")
        
        # Store results
        if metrics:
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
                logger.info(
                    f"[{self.session_id}] Recon: {metric.protocol} | "
                    f"Success={metric.success} | Data={metric.data_extracted} bytes"
                )
        
        state["honeypot_responses"].extend(responses)
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.03)
        )
        
        return state

    def _exploit_node(self, state):
        """Exploitation node - execute real attacks."""
        proto_str = state.get("protocol", "ssh")
        if hasattr(proto_str, "value"):
            proto_str = proto_str.value
        
        success, responses, metrics = self._execute_real_attack(proto_str, "exploit")
        
        # Store results
        if metrics:
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
                logger.info(
                    f"[{self.session_id}] Exploit: {metric.protocol} | "
                    f"Success={metric.success} | Data={metric.data_extracted} bytes"
                )
        
        state["honeypot_responses"].extend(responses)
        if success:
            state["extracted_data"]["exploit_data"] = responses
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.12)
        )
        
        return state

    def _persist_node(self, state):
        """Persistence node - real attempts to maintain access."""
        proto_str = state.get("protocol", "ssh")
        if hasattr(proto_str, "value"):
            proto_str = proto_str.value
        
        # For persistence, we mostly just probe; real persistence would be dangerous
        success, responses, metrics = self._execute_real_attack(proto_str, "recon")
        
        if metrics:
            for metric in metrics:
                self.storage.store_attack_result(
                    session_id=self.session_id,
                    protocol=metric.protocol,
                    attack_type="persist_attempt",
                    success=metric.success,
                    data_extracted=metric.data_extracted,
                    suspicion_level=0.25,  # Persistence is highly suspicious
                    duration=metric.duration,
                    responses=responses,
                )
                logger.info(f"[{self.session_id}] Persistence probe: {metric.protocol}")
        
        state["honeypot_responses"].extend(responses)
        state["suspicion_level"] = min(1.0, state["suspicion_level"] + 0.20)
        
        return state

    def _exfil_node(self, state):
        """Exfiltration node - attempt to extract sensitive data."""
        proto_str = state.get("protocol", "ssh")
        if hasattr(proto_str, "value"):
            proto_str = proto_str.value
        
        success, responses, metrics = self._execute_real_attack(proto_str, "exploit")
        
        if metrics:
            for metric in metrics:
                self.storage.store_attack_result(
                    session_id=self.session_id,
                    protocol=metric.protocol,
                    attack_type="exfiltration",
                    success=metric.success,
                    data_extracted=metric.data_extracted,
                    suspicion_level=metric.suspicion_level,
                    duration=metric.duration,
                    responses=responses,
                )
                logger.info(
                    f"[{self.session_id}] Exfil: {metric.protocol} | "
                    f"Extracted={metric.data_extracted} bytes"
                )
        
        if success:
            state["extracted_data"]["exfil"] = responses
        state["suspicion_level"] = min(
            1.0, state["suspicion_level"] + (metrics[0].suspicion_level if metrics else 0.18)
        )
        
        return state
