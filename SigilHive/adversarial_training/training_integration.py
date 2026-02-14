"""
Training Integration for SigilHive Adversarial System
Bridges adversarial attacks, RL Q-learning agents, and file structure evolution.

Implements:
- Double Q-Learning with Prioritized Experience Replay
- N-Step Returns (n=3) for improved credit assignment
- Adaptive learning rate based on state complexity
- Automatic checkpointing
- Real-time state extraction from attack results
- Reward calculation with multi-factor scoring
"""

import json
import logging
import math
import os
import pickle
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .adversarial_agent import AdversarialAgent, AttackResult, AttackPhase, Protocol

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  State & Experience types                                            #
# ------------------------------------------------------------------ #

@dataclass
class HoneypotState:
    """Extracted state vector for RL agent."""
    # Attack features
    suspicion_level: float = 0.0
    attack_phase_encoded: int = 0  # 0-4 for phases
    commands_per_session: int = 0
    data_exfiltrated_fields: int = 0
    multi_protocol_active: bool = False

    # Honeypot features
    probed_table_ratio: float = 0.0  # probed/total tables
    evolution_count: int = 0
    honeytoken_triggered: bool = False
    decoy_table_accessed: bool = False

    # Temporal features
    time_since_last_attack: float = 0.0
    attack_frequency: float = 0.0  # attacks/hour

    def to_vector(self) -> list[float]:
        return [
            self.suspicion_level,
            self.attack_phase_encoded / 4.0,
            min(self.commands_per_session / 20.0, 1.0),
            min(self.data_exfiltrated_fields / 10.0, 1.0),
            float(self.multi_protocol_active),
            self.probed_table_ratio,
            min(self.evolution_count / 50.0, 1.0),
            float(self.honeytoken_triggered),
            float(self.decoy_table_accessed),
            min(self.time_since_last_attack / 3600.0, 1.0),
            min(self.attack_frequency / 10.0, 1.0),
        ]

    def to_key(self) -> str:
        """Discretized state key for Q-table."""
        vec = self.to_vector()
        buckets = [int(v * 5) for v in vec]  # 5 buckets per dimension
        return "_".join(map(str, buckets))


@dataclass
class Experience:
    """Single experience tuple for replay buffer."""
    state: HoneypotState
    action: str  # evolution strategy
    reward: float
    next_state: HoneypotState
    done: bool
    priority: float = 1.0

    def to_n_step(self, gamma: float = 0.99, n: int = 3) -> "Experience":
        """Placeholder for N-step return conversion (handled in buffer)."""
        return self


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay with N-step returns.
    Capacity: 10,000 experiences
    """

    def __init__(self, capacity: int = 10_000, alpha: float = 0.6, beta: float = 0.4):
        self.capacity = capacity
        self.alpha = alpha  # Priority exponent
        self.beta = beta    # Importance sampling exponent
        self.buffer: deque[Experience] = deque(maxlen=capacity)
        self.priorities: deque[float] = deque(maxlen=capacity)
        self._max_priority = 1.0

    def push(self, experience: Experience) -> None:
        experience.priority = self._max_priority
        self.buffer.append(experience)
        self.priorities.append(self._max_priority)

    def sample(self, batch_size: int) -> list[Experience]:
        if len(self.buffer) < batch_size:
            return list(self.buffer)

        priorities = list(self.priorities)
        total = sum(p ** self.alpha for p in priorities)
        probs = [(p ** self.alpha) / total for p in priorities]

        indices = random.choices(range(len(self.buffer)), weights=probs, k=batch_size)
        return [list(self.buffer)[i] for i in indices]

    def update_priority(self, idx: int, priority: float) -> None:
        if 0 <= idx < len(self.priorities):
            self.priorities[idx] = priority
            self._max_priority = max(self._max_priority, priority)

    def __len__(self) -> int:
        return len(self.buffer)


class NStepBuffer:
    """Accumulates N-step returns before pushing to replay buffer."""

    def __init__(self, n: int = 3, gamma: float = 0.99):
        self.n = n
        self.gamma = gamma
        self.buffer: list[tuple] = []

    def push(
        self,
        state: HoneypotState,
        action: str,
        reward: float,
        next_state: HoneypotState,
        done: bool,
    ) -> Optional[Experience]:
        self.buffer.append((state, action, reward, next_state, done))

        if len(self.buffer) >= self.n or done:
            # Compute N-step return
            n_step_reward = sum(
                (self.gamma ** i) * self.buffer[i][2]
                for i in range(len(self.buffer))
            )
            first_state = self.buffer[0][0]
            first_action = self.buffer[0][1]
            last_next_state = self.buffer[-1][3]
            is_done = any(b[4] for b in self.buffer)

            exp = Experience(
                state=first_state,
                action=first_action,
                reward=n_step_reward,
                next_state=last_next_state,
                done=is_done,
            )
            self.buffer = []
            return exp

        return None

    def flush(self) -> list[Experience]:
        """Flush remaining experiences at end of episode."""
        results = []
        while self.buffer:
            n_step_reward = sum(
                (self.gamma ** i) * self.buffer[i][2]
                for i in range(len(self.buffer))
            )
            exp = Experience(
                state=self.buffer[0][0],
                action=self.buffer[0][1],
                reward=n_step_reward,
                next_state=self.buffer[-1][3],
                done=True,
            )
            results.append(exp)
            self.buffer.pop(0)
        return results


# ------------------------------------------------------------------ #
#  Q-Learning Agent                                                    #
# ------------------------------------------------------------------ #

class DoubleQLearningAgent:
    """
    Double Q-Learning agent for honeypot evolution decisions.

    Actions = EvolutionStrategy enum values
    State = HoneypotState (discretized to key)
    """

    ACTIONS = [s.value for s in EvolutionStrategy]

    def __init__(
        self,
        learning_rate: float = 0.1,
        gamma: float = 0.99,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.05,
    ):
        self.lr = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        # Two Q-tables for Double Q-Learning (eliminates overestimation)
        self.q1: dict[str, dict[str, float]] = {}
        self.q2: dict[str, dict[str, float]] = {}

        self.training_steps = 0
        self.total_reward = 0.0

    def _init_state(self, state_key: str) -> None:
        if state_key not in self.q1:
            self.q1[state_key] = {a: 0.0 for a in self.ACTIONS}
        if state_key not in self.q2:
            self.q2[state_key] = {a: 0.0 for a in self.ACTIONS}

    def select_action(self, state: HoneypotState) -> str:
        """ε-greedy action selection using averaged Q-values."""
        if random.random() < self.epsilon:
            return random.choice(self.ACTIONS)

        state_key = state.to_key()
        self._init_state(state_key)

        # Use average of Q1 and Q2
        avg_q = {
            a: (self.q1[state_key][a] + self.q2[state_key].get(a, 0.0)) / 2
            for a in self.ACTIONS
        }
        return max(avg_q, key=avg_q.get)

    def get_q_values(self, state: HoneypotState) -> dict[str, float]:
        """Return averaged Q-values for all actions given a state."""
        state_key = state.to_key()
        self._init_state(state_key)
        return {
            a: (self.q1[state_key][a] + self.q2[state_key].get(a, 0.0)) / 2
            for a in self.ACTIONS
        }

    def update(self, experience: Experience) -> float:
        """Double Q-Learning update. Returns TD error for priority replay."""
        state_key = experience.state.to_key()
        next_key = experience.next_state.to_key()
        action = experience.action
        reward = experience.reward

        self._init_state(state_key)
        self._init_state(next_key)

        # Adaptive learning rate based on state visit count
        visit_count = sum(1 for v in self.q1[state_key].values() if v != 0)
        adaptive_lr = self.lr / math.sqrt(max(visit_count, 1))

        # Randomly update Q1 or Q2 (Double Q-Learning)
        if random.random() < 0.5:
            if not experience.done:
                best_action_q1 = max(self.q1[next_key], key=self.q1[next_key].get)
                target = reward + self.gamma * self.q2[next_key][best_action_q1]
            else:
                target = reward
            td_error = target - self.q1[state_key][action]
            self.q1[state_key][action] += adaptive_lr * td_error
        else:
            if not experience.done:
                best_action_q2 = max(self.q2[next_key], key=self.q2[next_key].get)
                target = reward + self.gamma * self.q1[next_key][best_action_q2]
            else:
                target = reward
            td_error = target - self.q2[state_key][action]
            self.q2[state_key][action] += adaptive_lr * td_error

        self.training_steps += 1
        self.total_reward += reward

        # Decay epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        return abs(td_error)

    def save_checkpoint(self, path: str) -> None:
        checkpoint = {
            "q1": self.q1,
            "q2": self.q2,
            "epsilon": self.epsilon,
            "training_steps": self.training_steps,
            "total_reward": self.total_reward,
        }
        with open(path, "wb") as f:
            pickle.dump(checkpoint, f)
        logger.info(f"RL checkpoint saved: {path}")

    def load_checkpoint(self, path: str) -> None:
        with open(path, "rb") as f:
            checkpoint = pickle.load(f)
        self.q1 = checkpoint["q1"]
        self.q2 = checkpoint["q2"]
        self.epsilon = checkpoint["epsilon"]
        self.training_steps = checkpoint["training_steps"]
        self.total_reward = checkpoint["total_reward"]
        logger.info(f"RL checkpoint loaded: {path} | steps={self.training_steps}")


# ------------------------------------------------------------------ #
#  Reward Calculator                                                   #
# ------------------------------------------------------------------ #

class RewardCalculator:
    """Calculates multi-factor RL rewards from honeypot interactions."""

    # Reward weights
    DETECTION_REWARD = 15.0        # Attacker triggered detection mechanism
    HONEYTOKEN_ACCESS = 25.0       # Attacker accessed a honeytoken
    DECOY_ACCESS = 18.0            # Attacker accessed a decoy table
    ATTACKER_CONFUSED = 10.0       # Attacker made repeated failed attempts
    DATA_PROTECTED = 8.0           # Real data was sanitized before exfil
    EXFIL_PENALTY = -20.0          # Real data was exfiltrated (bad for defense)
    PERSISTENCE_BLOCKED = 12.0     # Persistence attempt failed
    HIGH_SUSPICION_REWARD = 5.0    # Attacker reached high suspicion level

    def calculate(
        self,
        attack_results: list[AttackResult],
        evolution_record: Optional[Any] = None,
        state: Optional[HoneypotState] = None,
    ) -> float:
        total = 0.0

        for result in attack_results:
            # Suspicion-based reward (higher suspicion = better defense)
            if result.suspicion_delta > 0.5:
                total += self.HIGH_SUSPICION_REWARD

            # Attacker failed (not success = defense win)
            if not result.success:
                total += self.DETECTION_REWARD

            # Honeytoken triggered
            if any("honeytoken" in str(v).lower() for v in result.data_extracted.values()):
                total += self.HONEYTOKEN_ACCESS

            # Decoy table accessed
            if any("decoy" in cmd.lower() or "audit_log" in cmd.lower()
                   or "payment_processor_keys" in cmd.lower()
                   for cmd in result.commands_executed):
                total += self.DECOY_ACCESS

            # Real data exfiltrated (penalty)
            if result.phase == AttackPhase.EXFILTRATION and result.success:
                total += self.EXFIL_PENALTY

            # Persistence phase blocked
            if result.phase == AttackPhase.PERSISTENCE and not result.success:
                total += self.PERSISTENCE_BLOCKED

        # Evolution reward delta contribution
        if evolution_record and hasattr(evolution_record, "reward_delta"):
            total += evolution_record.reward_delta * 0.5

        return total


# ------------------------------------------------------------------ #
#  TrainingIntegration (main connector)                               #
# ------------------------------------------------------------------ #

class TrainingIntegration:
    """
    Connects the adversarial attack loop to RL training and structure evolution.

    Flow per training step:
    1. Extract state from recent attack results
    2. RL agent selects evolution strategy
    3. Evolver applies strategy to file_structure.py
    4. Calculate reward
    5. Store experience in prioritized replay buffer (with N-step returns)
    6. Sample batch and update Double Q-Learning agent
    7. Checkpoint periodically
    """

    CHECKPOINT_EVERY_N_STEPS = 100
    BATCH_SIZE = 32
    EVOLUTION_EVERY_N_ATTACKS = 5  # Trigger evolution after N attack cycles
    def __init__(
        self,
        agent: AdversarialAgent,
        checkpoint_dir: str = "rl_checkpoints",
        session_log_path: str = "training_session.json",
    ):
        self.agent = agent
        self.checkpoint_dir = Path(checkpoint_dir)
        self.session_log_path = Path(session_log_path)

        self.rl_agent = DoubleQLearningAgent()
        self.replay_buffer = PrioritizedReplayBuffer(capacity=10_000)
        self.n_step_buffer = NStepBuffer(n=3, gamma=0.99)
        self.reward_calculator = RewardCalculator()

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # State tracking
        self._last_state: Optional[HoneypotState] = None
        self._last_action: Optional[str] = None
        self._attack_count = 0
        self._training_steps = 0
        self._session_start = time.time()
        self._session_rewards: list[float] = []

        # Try to load latest checkpoint
        self._try_load_checkpoint()

        logger.info("TrainingIntegration initialized")

    # ------------------------------------------------------------------ #
    #  State extraction                                                    #
    # ------------------------------------------------------------------ #

    def extract_state(self, attack_results: list[AttackResult]) -> HoneypotState:
        """Convert raw attack results into an RL state vector."""
        if not attack_results:
            return HoneypotState()

        latest = attack_results[-1]
        phase_map = {
            AttackPhase.RECONNAISSANCE: 0,
            AttackPhase.EXPLOITATION: 1,
            AttackPhase.PERSISTENCE: 2,
            AttackPhase.EXFILTRATION: 3,
            AttackPhase.CLEANUP: 4,
        }

        # Check for honeytoken/decoy access
        honeytoken_triggered = any(
            "honeytoken" in str(r.data_extracted).lower()
            for r in attack_results
        )
        decoy_accessed = any(
            any("decoy" in cmd.lower() or "audit_log" in cmd.lower()
                for cmd in r.commands_executed)
            for r in attack_results
        )

        total_tables = 10  # approx from file_structure.py
        probed_ratio = 0.0  # File structure evolver removed

        return HoneypotState(
            suspicion_level=latest.suspicion_delta,
            attack_phase_encoded=phase_map.get(latest.phase, 0),
            commands_per_session=sum(len(r.commands_executed) for r in attack_results),
            data_exfiltrated_fields=len(latest.data_extracted),
            multi_protocol_active=len(set(r.protocol for r in attack_results)) > 1,
            probed_table_ratio=probed_ratio,
            evolution_count=0,  # File structure evolver removed
            honeytoken_triggered=honeytoken_triggered,
            decoy_table_accessed=decoy_accessed,
            time_since_last_attack=time.time() - self._session_start,
            attack_frequency=self._attack_count / max((time.time() - self._session_start) / 3600, 0.01),
        )

    # ------------------------------------------------------------------ #
    #  Main training step                                                  #
    # ------------------------------------------------------------------ #

    def process_attack_batch(self, attack_results: list[AttackResult]) -> dict:
        """
        Process a batch of attack results through the full training pipeline.
        Returns training metrics for monitoring.
        """
        self._attack_count += len(attack_results)

        # Extract current state
        current_state = self.extract_state(attack_results)

        # Store transition from previous step
        if self._last_state is not None and self._last_action is not None:
            step_reward = self.reward_calculator.calculate(attack_results)
            self._session_rewards.append(step_reward)

            exp = self.n_step_buffer.push(
                self._last_state, self._last_action, step_reward, current_state, done=False
            )
            if exp:
                self.replay_buffer.push(exp)

        # RL agent selects evolution action
        q_values = self.rl_agent.get_q_values(current_state)
        action = self.rl_agent.select_action(current_state)

        # Train RL agent if we have enough experiences
        td_error = 0.0
        if len(self.replay_buffer) >= self.BATCH_SIZE:
            td_error = self._train_step()

        # Save state/action for next step
        self._last_state = current_state
        self._last_action = action
        self._training_steps += 1

        # Periodic checkpoint
        if self._training_steps % self.CHECKPOINT_EVERY_N_STEPS == 0:
            self._save_checkpoint()

        metrics = {
            "training_step": self._training_steps,
            "attack_count": self._attack_count,
            "suspicion_level": current_state.suspicion_level,
            "epsilon": round(self.rl_agent.epsilon, 4),
            "td_error": round(td_error, 4),
            "replay_buffer_size": len(self.replay_buffer),
            "selected_action": action,
            "recent_avg_reward": (
                sum(self._session_rewards[-20:]) / len(self._session_rewards[-20:])
                if self._session_rewards else 0.0
            ),
            "evolution_applied": evolution_record is not None,
            "evolution_strategy": evolution_record.strategy.value if evolution_record else None,
        }

        self._log_session_step(metrics)
        return metrics

    def _train_step(self) -> float:
        """Sample batch from replay buffer and update Q-agent. Returns avg TD error."""
        batch = self.replay_buffer.sample(self.BATCH_SIZE)
        if not batch:
            return 0.0

        total_td_error = 0.0
        for i, exp in enumerate(batch):
            td_error = self.rl_agent.update(exp)
            total_td_error += td_error
            # Update priority based on TD error
            self.replay_buffer.update_priority(i, td_error + 1e-5)

        return total_td_error / len(batch)

    def end_episode(self) -> None:
        """Flush N-step buffer at end of an episode."""
        remaining = self.n_step_buffer.flush()
        for exp in remaining:
            self.replay_buffer.push(exp)
        self._last_state = None
        self._last_action = None

    # ------------------------------------------------------------------ #
    #  Checkpointing                                                       #
    # ------------------------------------------------------------------ #

    def _save_checkpoint(self) -> None:
        path = self.checkpoint_dir / f"rl_step_{self._training_steps}.pkl"
        self.rl_agent.save_checkpoint(str(path))

        # Keep only latest 5 checkpoints
        checkpoints = sorted(self.checkpoint_dir.glob("rl_step_*.pkl"))
        for old in checkpoints[:-5]:
            old.unlink()

    def _try_load_checkpoint(self) -> None:
        checkpoints = sorted(self.checkpoint_dir.glob("rl_step_*.pkl"))
        if checkpoints:
            try:
                self.rl_agent.load_checkpoint(str(checkpoints[-1]))
            except Exception as exc:
                logger.warning(f"Could not load checkpoint: {exc}")

    # ------------------------------------------------------------------ #
    #  Session logging                                                     #
    # ------------------------------------------------------------------ #

    def _log_session_step(self, metrics: dict) -> None:
        log_data: list[dict] = []
        if self.session_log_path.exists():
            try:
                with open(self.session_log_path) as f:
                    log_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        log_data.append({"timestamp": time.time(), **metrics})

        # Cap log size
        if len(log_data) > 10_000:
            log_data = log_data[-5_000:]

        with open(self.session_log_path, "w") as f:
            json.dump(log_data, f)

    def get_training_report(self) -> dict:
        elapsed = time.time() - self._session_start
        return {
            "session_elapsed_minutes": round(elapsed / 60, 1),
            "total_training_steps": self._training_steps,
            "total_attacks_processed": self._attack_count,
            "rl_epsilon": round(self.rl_agent.epsilon, 4),
            "replay_buffer_size": len(self.replay_buffer),
            "avg_reward_last_100": (
                sum(self._session_rewards[-100:]) / len(self._session_rewards[-100:])
                if self._session_rewards else 0.0
            ),
        }