# smart_cache.py
import hashlib
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import OrderedDict


class SmartCache:
    """Intelligent multi-tier caching system with prefetching"""

    def __init__(self, max_memory_cache_size: int = 100):
        self.memory_cache = OrderedDict()  # L1 cache (LRU)
        self.max_memory_size = max_memory_cache_size
        self.disk_cache = {}  # L2 cache (simulated)
        self.cache_stats = {"hits": 0, "misses": 0, "prefetch_hits": 0}
        self.prefetch_queue = asyncio.Queue()
        self.command_patterns = {}  # Track common command sequences

    async def get(self, key: str) -> Optional[str]:
        """Get from cache with automatic promotion"""

        # L1: Memory cache (fastest)
        if key in self.memory_cache:
            # Move to end (most recently used)
            self.memory_cache.move_to_end(key)
            self.cache_stats["hits"] += 1
            return self.memory_cache[key]["value"]

        # L2: Disk cache (slower)
        if key in self.disk_cache:
            value = self.disk_cache[key]["value"]
            # Promote to L1
            await self.set(key, value, promote=True)
            self.cache_stats["hits"] += 1
            return value

        self.cache_stats["misses"] += 1
        return None

    async def set(self, key: str, value: str, ttl: int = 3600, promote: bool = False):
        """Set in cache with TTL"""

        cache_entry = {
            "value": value,
            "timestamp": datetime.now(),
            "ttl": ttl,
            "access_count": 1
            if not promote
            else self.memory_cache.get(key, {}).get("access_count", 0) + 1,
        }

        # L1: Memory cache with LRU eviction
        if len(self.memory_cache) >= self.max_memory_size:
            # Remove least recently used
            oldest_key = next(iter(self.memory_cache))
            evicted = self.memory_cache.pop(oldest_key)
            # Move to L2
            self.disk_cache[oldest_key] = evicted

        self.memory_cache[key] = cache_entry
        self.memory_cache.move_to_end(key)

    async def prefetch(
        self,
        session_id: str,
        current_command: str,
        current_dir: str,
        likely_next_commands: List[str],
    ):
        """Prefetch likely next commands"""

        # Update command patterns
        self._update_command_patterns(session_id, current_command)

        # Get predicted commands
        predicted = self._predict_next_commands(session_id, current_command)

        # Combine with provided likely commands
        all_likely = list(set(predicted + likely_next_commands))

        # Add to prefetch queue with priority
        for cmd in all_likely[:5]:  # Top 5 most likely
            cache_key = self._generate_cache_key(session_id, cmd, current_dir)

            # Check if already cached
            if not await self.get(cache_key):
                priority = self._calculate_priority(cmd, current_command)
                await self.prefetch_queue.put(
                    {
                        "session_id": session_id,
                        "command": cmd,
                        "current_dir": current_dir,
                        "priority": priority,
                        "cache_key": cache_key,
                    }
                )

    def _update_command_patterns(self, session_id: str, command: str):
        """Track command sequences for prediction"""

        if session_id not in self.command_patterns:
            self.command_patterns[session_id] = {
                "history": [],
                "sequences": {},  # "cmd1->cmd2" -> count
            }

        history = self.command_patterns[session_id]["history"]
        history.append(command)

        # Keep last 50 commands
        if len(history) > 50:
            history.pop(0)

        # Update sequences (bigrams)
        if len(history) >= 2:
            sequence = f"{history[-2]}->{history[-1]}"
            sequences = self.command_patterns[session_id]["sequences"]
            sequences[sequence] = sequences.get(sequence, 0) + 1

    def _predict_next_commands(
        self, session_id: str, current_command: str
    ) -> List[str]:
        """Predict next commands based on patterns"""

        if session_id not in self.command_patterns:
            return self._get_default_predictions(current_command)

        sequences = self.command_patterns[session_id]["sequences"]

        # Find sequences starting with current command
        predictions = []
        for sequence, count in sequences.items():
            if sequence.startswith(current_command + "->"):
                next_cmd = sequence.split("->")[1]
                predictions.append((next_cmd, count))

        # Sort by frequency
        predictions.sort(key=lambda x: x[1], reverse=True)

        # Return top predictions
        predicted_cmds = [cmd for cmd, _ in predictions[:3]]

        # Add default predictions if not enough
        if len(predicted_cmds) < 3:
            predicted_cmds.extend(self._get_default_predictions(current_command))

        return predicted_cmds[:5]

    def _get_default_predictions(self, current_command: str) -> List[str]:
        """Default command predictions based on common patterns"""

        patterns = {
            "ls": ["cat", "cd", "ls -la", "pwd"],
            "cd": ["ls", "pwd", "cat"],
            "cat .env": ["cat config.js", "cat database.js", "ls", "grep password"],
            "cat": ["ls", "pwd", "cat"],
            "whoami": ["id", "sudo -l", "cat /etc/passwd", "groups"],
            "ps": ["netstat", "top", "ls /proc", "kill"],
            "pwd": ["ls", "cd ..", "ls -la"],
            "find": ["cat", "grep", "ls"],
            "grep": ["cat", "less", "vi"],
        }

        # Extract base command
        base_cmd = current_command.split()[0] if current_command else ""

        # Check for full command match first
        if current_command in patterns:
            return patterns[current_command]

        # Then check base command
        if base_cmd in patterns:
            return patterns[base_cmd]

        # Default fallback
        return ["ls", "pwd", "cat"]

    def _calculate_priority(self, command: str, current_command: str) -> int:
        """Calculate prefetch priority (higher = more important)"""

        # Common commands get higher priority
        common_commands = ["ls", "pwd", "whoami", "cat", "ps", "netstat"]

        priority = 0

        # Boost priority for common commands
        base_cmd = command.split()[0] if command else ""
        if base_cmd in common_commands:
            priority += 10 - common_commands.index(base_cmd)

        # Boost if it's a natural follow-up
        follow_ups = {
            "ls": ["cat", "cd"],
            "cat": ["ls", "pwd"],
            "cd": ["ls", "pwd"],
            "pwd": ["ls"],
        }

        current_base = current_command.split()[0] if current_command else ""
        if current_base in follow_ups:
            if base_cmd in follow_ups[current_base]:
                priority += 5

        return priority

    def _generate_cache_key(
        self, session_id: str, command: str, current_dir: str
    ) -> str:
        """Generate consistent cache key"""
        key_string = f"{session_id}:{command}:{current_dir}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total * 100) if total > 0 else 0

        return {
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "hit_rate": f"{hit_rate:.2f}%",
            "prefetch_hits": self.cache_stats["prefetch_hits"],
            "memory_cache_size": len(self.memory_cache),
            "disk_cache_size": len(self.disk_cache),
        }

    def cleanup_expired(self):
        """Remove expired cache entries"""

        now = datetime.now()

        # Clean memory cache
        expired_keys = []
        for key, entry in self.memory_cache.items():
            if now - entry["timestamp"] > timedelta(seconds=entry["ttl"]):
                expired_keys.append(key)

        for key in expired_keys:
            del self.memory_cache[key]

        # Clean disk cache
        expired_keys = []
        for key, entry in self.disk_cache.items():
            if now - entry["timestamp"] > timedelta(seconds=entry["ttl"]):
                expired_keys.append(key)

        for key in expired_keys:
            del self.disk_cache[key]
