"""
Attack Scheduler for SigilHive Adversarial Training System
Manages configurable periodic attacks, campaign bursts, and multi-protocol coordination.
"""

import logging
import random
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from .adversarial_agent import AdversarialAgent, AttackResult, Protocol

logger = logging.getLogger(__name__)


@dataclass
class AttackConfig:
    """Configuration for scheduled attack parameters."""
    # Attacks per hour per protocol (randomized within range)
    min_attacks_per_hour: int = 2
    max_attacks_per_hour: int = 3

    # Probability of multi-protocol coordinated attack per cycle
    multi_protocol_probability: float = 0.15

    # Campaign settings: burst attacks every N hours at multiplied intensity
    campaign_interval_hours: float = 6.0
    campaign_intensity_multiplier: int = 3

    # Protocol weights (relative probability of each being targeted)
    protocol_weights: dict[str, float] = field(default_factory=lambda: {
        "ssh": 0.40,
        "http": 0.40,
        "database": 0.20,
    })

    # Safety: max suspicion before forcing cooldown
    max_suspicion_before_cooldown: float = 0.75
    cooldown_duration_seconds: float = 300.0


@dataclass
class AttackStats:
    total_attacks: int = 0
    successful_attacks: int = 0
    aborted_attacks: int = 0
    total_campaigns: int = 0
    multi_protocol_attacks: int = 0
    protocol_breakdown: dict[str, int] = field(default_factory=lambda: {
        "ssh": 0, "http": 0, "database": 0
    })
    total_reward: float = 0.0
    session_start: float = field(default_factory=time.time)

    def success_rate(self) -> float:
        if self.total_attacks == 0:
            return 0.0
        return self.successful_attacks / self.total_attacks

    def to_dict(self) -> dict:
        elapsed = time.time() - self.session_start
        return {
            "total_attacks": self.total_attacks,
            "successful_attacks": self.successful_attacks,
            "aborted_attacks": self.aborted_attacks,
            "success_rate": f"{self.success_rate():.1%}",
            "total_campaigns": self.total_campaigns,
            "multi_protocol_attacks": self.multi_protocol_attacks,
            "protocol_breakdown": self.protocol_breakdown,
            "total_reward": round(self.total_reward, 2),
            "elapsed_minutes": round(elapsed / 60, 1),
            "attacks_per_minute": round(self.total_attacks / max(elapsed / 60, 1), 2),
        }


class AttackScheduler:
    """
    Manages the timing and coordination of adversarial attacks.

    Features:
    - Configurable attack frequency (2-3/hour per protocol by default)
    - 15% multi-protocol attack probability
    - Campaign bursts every 6 hours at 3x intensity
    - Automatic cooldown when suspicion is too high
    - Thread-safe operation for background scheduling
    """

    def __init__(
        self,
        agent: AdversarialAgent,
        config: Optional[AttackConfig] = None,
        result_callback: Optional[Callable[[list[AttackResult]], None]] = None,
    ):
        self.agent = agent
        self.config = config or AttackConfig()
        self.result_callback = result_callback
        self.stats = AttackStats()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_campaign_time = time.time()
        self._cooldown_until: float = 0.0

        logger.info(
            f"AttackScheduler initialized | "
            f"{self.config.min_attacks_per_hour}-{self.config.max_attacks_per_hour} attacks/hr per protocol"
        )

    # ------------------------------------------------------------------ #
    #  Scheduling core                                                     #
    # ------------------------------------------------------------------ #

    def _select_protocol(self) -> Protocol:
        """Weighted random protocol selection."""
        protocols = list(self.config.protocol_weights.keys())
        weights = list(self.config.protocol_weights.values())
        chosen = random.choices(protocols, weights=weights, k=1)[0]
        return Protocol(chosen)

    def _seconds_until_next_attack(self) -> float:
        """Calculate sleep time based on configured attack frequency."""
        attacks_per_hour = random.uniform(
            self.config.min_attacks_per_hour,
            self.config.max_attacks_per_hour,
        )
        base_interval = 3600.0 / attacks_per_hour
        # Add jitter ±20% to avoid predictable timing
        jitter = base_interval * 0.2 * random.uniform(-1, 1)
        return max(30.0, base_interval + jitter)

    def _should_run_campaign(self) -> bool:
        elapsed = time.time() - self._last_campaign_time
        return elapsed >= (self.config.campaign_interval_hours * 3600)

    def _run_campaign(self) -> None:
        """Execute an attack campaign (burst at 3x intensity)."""
        logger.info("=== ATTACK CAMPAIGN STARTING ===")
        self.stats.total_campaigns += 1
        num_attacks = self.config.campaign_intensity_multiplier * random.randint(2, 4)

        for i in range(num_attacks):
            if self.agent.suspicion_level >= self.config.max_suspicion_before_cooldown:
                logger.warning("Campaign paused: suspicion too high, cooling down")
                self._initiate_cooldown()
                break
            protocol = self._select_protocol()
            self._execute_single_attack(protocol)
            time.sleep(random.uniform(5, 15))  # Brief pause between campaign attacks

        self._last_campaign_time = time.time()
        logger.info(f"=== CAMPAIGN COMPLETE | {num_attacks} attacks ===")

    def _execute_single_attack(self, protocol: Protocol) -> list[AttackResult]:
        """Execute one attack and update statistics."""
        logger.info(f"Executing {protocol.value} attack | suspicion={self.agent.suspicion_level:.2f}")

        try:
            results = self.agent.run_attack(protocol=protocol)
        except Exception as exc:
            logger.error(f"Attack execution failed: {exc}")
            self.stats.aborted_attacks += 1
            return []

        self.stats.total_attacks += 1
        self.stats.protocol_breakdown[protocol.value] = (
            self.stats.protocol_breakdown.get(protocol.value, 0) + 1
        )

        if results:
            last = results[-1]
            if last.success:
                self.stats.successful_attacks += 1
            else:
                self.stats.aborted_attacks += 1
            self.stats.total_reward += last.reward_signal

        if self.result_callback and results:
            try:
                self.result_callback(results)
            except Exception as exc:
                logger.warning(f"Result callback failed: {exc}")

        return results

    def _execute_multi_protocol_attack(self) -> None:
        """Coordinated simultaneous attack across multiple protocols."""
        logger.info("Executing multi-protocol coordinated attack")
        self.stats.multi_protocol_attacks += 1
        protocols = random.sample(list(Protocol), k=random.randint(2, 3))
        threads = []
        for protocol in protocols:
            t = threading.Thread(
                target=self._execute_single_attack,
                args=(protocol,),
                daemon=True,
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=60)

    def _initiate_cooldown(self) -> None:
        """Pause attacks and reset agent suspicion."""
        self._cooldown_until = time.time() + self.config.cooldown_duration_seconds
        logger.info(
            f"Cooldown initiated for {self.config.cooldown_duration_seconds}s | "
            f"suspicion={self.agent.suspicion_level:.2f}"
        )
        self.agent.reset_session()

    def _in_cooldown(self) -> bool:
        return time.time() < self._cooldown_until

    # ------------------------------------------------------------------ #
    #  Scheduler loop                                                      #
    # ------------------------------------------------------------------ #

    def _scheduler_loop(self) -> None:
        logger.info("Attack scheduler loop started")
        while self._running:
            try:
                if self._in_cooldown():
                    time.sleep(10)
                    continue

                # Campaign check (every 6 hours)
                if self._should_run_campaign():
                    self._run_campaign()
                    continue

                # Multi-protocol attack (15% chance)
                if random.random() < self.config.multi_protocol_probability:
                    self._execute_multi_protocol_attack()
                else:
                    protocol = self._select_protocol()
                    self._execute_single_attack(protocol)

                # High suspicion → cooldown
                if self.agent.suspicion_level >= self.config.max_suspicion_before_cooldown:
                    self._initiate_cooldown()
                    continue

                sleep_time = self._seconds_until_next_attack()
                logger.debug(f"Next attack in {sleep_time:.0f}s")
                # Sleep in 5-second chunks so we can be interrupted cleanly
                chunks = int(sleep_time / 5)
                for _ in range(chunks):
                    if not self._running:
                        break
                    time.sleep(5)

            except Exception as exc:
                logger.error(f"Scheduler loop error: {exc}", exc_info=True)
                time.sleep(30)

        logger.info("Attack scheduler loop stopped")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the background attack scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._scheduler_loop, name="AttackScheduler", daemon=True
        )
        self._thread.start()
        logger.info("AttackScheduler started")

    def stop(self) -> None:
        """Stop the background attack scheduler gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=30)
        logger.info("AttackScheduler stopped")

    def run_manual_attack(self, protocol: Optional[str] = None) -> list[AttackResult]:
        """Trigger a single attack manually (for testing)."""
        chosen = Protocol(protocol) if protocol else self._select_protocol()
        return self._execute_single_attack(chosen)

    def get_stats(self) -> dict:
        return self.stats.to_dict()

    def print_stats(self) -> None:
        stats = self.stats.to_dict()
        print("\n" + "=" * 50)
        print("  ATTACK SCHEDULER STATISTICS")
        print("=" * 50)
        for k, v in stats.items():
            print(f"  {k:<30} {v}")
        print("=" * 50 + "\n")