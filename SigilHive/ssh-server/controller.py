# controller.py
import json
import asyncio
import numpy as np
import time
from typing import Dict, Any
import llm_gen


# small in-memory session store
class Controller:
    def __init__(self, persona: str = "ubuntu-server"):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.persona = persona

    def _update_meta(self, session_id: str, event: Dict[str, Any]):
        meta = self.sessions.setdefault(
            session_id, {"cmd_count": 0, "elapsed": 0.0, "last_cmd": ""}
        )
        meta["cmd_count"] = event.get("cmd_count", meta["cmd_count"])
        meta["elapsed"] = event.get("elapsed", meta["elapsed"])
        if "command" in event:
            meta["last_cmd"] = event.get("command", meta["last_cmd"])
        meta["last_ts"] = time.time()
        self.sessions[session_id] = meta
        return meta

    def classify_command(self, cmd: str) -> str:
        # simple classification for prompt guidance (keeps LLM focused)
        cmd = (cmd or "").strip()
        if cmd == "":
            return "noop"
        if cmd.startswith("cat ") or cmd.startswith("less ") or cmd.startswith("more "):
            return "read_file"
        if cmd.split()[0] in ("ls", "dir"):
            return "list_dir"
        if cmd.split()[0] in ("whoami", "id"):
            return "identity"
        if cmd.split()[0] in ("uname", "hostname"):
            return "system_info"
        if cmd.split()[0] in ("ps", "top"):
            return "process_list"
        if cmd.split()[0] in ("netstat", "ss"):
            return "netstat"
        if cmd.split()[0] == "ping":
            return "network_probe"
        if cmd.split()[0] in ("curl", "wget"):
            return "http_fetch"
        if cmd.startswith("sudo "):
            return "privilege_escalation"
        if cmd.startswith("ssh "):
            return "remote_ssh"
        return "unknown"

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Asynchronous interface to request the next response for a command.
        Returns a dict: {"response": "<string>", "delay": <float>}
        This function ALWAYS uses the LLM to generate the response.
        """
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        intent = self.classify_command(cmd)

        # Provide filename hint if read_file intent
        filename_hint = None
        if intent == "read_file":
            parts = cmd.split(maxsplit=1)
            filename_hint = parts[1].strip() if len(parts) > 1 else "README.txt"

        # Build a concise command hint for the LLM: keep LLM focused on output generation
        # We ask the LLM to generate only the simulated output. Also pass persona for style.
        command_hint = cmd
        # Use llm_gen to generate the output asynchronously (cached)
        try:
            response_text = await llm_gen.generate_response_for_command_async(
                command=command_hint, filename_hint=filename_hint, persona=self.persona
            )
        except Exception as e:
            response_text = f"[LLM error: {e}]"

        # Optional: Add small randomized delay to avoid perfect determinism
        base_delay = 0.05
        delay = base_delay + float(np.random.rand()) * 0.2

        # Record structured log for future training (non-blocking)
        asyncio.create_task(
            self._log_event_async(session_id, cmd, intent, response_text)
        )

        return {"response": response_text, "delay": delay}

    async def _log_event_async(
        self, session_id: str, command: str, intent: str, response: str
    ):
        """
        Non-blocking append to a JSONL file for training/analysis.
        """
        try:
            log_line = {
                "ts": time.time(),
                "session_id": session_id,
                "command": command,
                "intent": intent,
                "response_preview": response[:400],
            }
            # append to file without locking (acceptable for PoC). For concurrent writes in heavy load, use a queue or DB.
            with open("session_logs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_line) + "\n")
        except Exception as e:
            # swallow logging errors in PoC
            print("[controller] logging error:", e)
