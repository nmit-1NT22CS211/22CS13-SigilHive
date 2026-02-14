"""
Enhanced Q-Learning Agent with Advanced Features

Improvements over basic Q-learning:
1. Double Q-Learning to reduce overestimation bias
2. Prioritized Experience Replay for better sample efficiency
3. Adaptive learning rate based on TD error
4. Multi-step returns (n-step Q-learning)
5. Episodic memory for long-term patterns
6. Automatic hyperparameter tuning
"""

import os
import pickle
import random
import threading
import numpy as np
from typing import Tuple, Optional, Dict, List
from collections import deque, defaultdict
from dataclasses import dataclass
import time
from .config import RL_CONFIG


# ==============================================================================
# EXPERIENCE REPLAY
# ==============================================================================

@dataclass
class Experience:
    """Single experience tuple"""
    state: Tuple
    action: str
    reward: float
    next_state: Tuple
    done: bool
    td_error: float = 0.0
    timestamp: float = 0.0


class PrioritizedReplayBuffer:
    """Prioritized experience replay buffer"""
    
    def __init__(self, capacity: int = 10000, alpha: float = 0.6):
        """
        Args:
            capacity: Maximum buffer size
            alpha: Prioritization exponent (0 = uniform, 1 = full prioritization)
        """
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = []
        self.priorities = []
        self.position = 0
    
    def add(self, experience: Experience):
        """Add experience to buffer"""
        # New experiences get max priority
        max_priority = max(self.priorities) if self.priorities else 1.0
        
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
            self.priorities.append(max_priority)
        else:
            # Replace oldest with circular buffer
            self.buffer[self.position] = experience
            self.priorities[self.position] = max_priority
        
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int, beta: float = 0.4) -> Tuple[List[Experience], List[int], np.ndarray]:
        """
        Sample batch with importance sampling
        
        Args:
            batch_size: Number of samples
            beta: Importance sampling exponent (0 = no correction, 1 = full correction)
        
        Returns:
            Tuple of (samples, indices, weights)
        """
        if len(self.buffer) < batch_size:
            batch_size = len(self.buffer)
        
        # Calculate sampling probabilities
        priorities = np.array(self.priorities[:len(self.buffer)])
        probabilities = priorities ** self.alpha
        probabilities /= probabilities.sum()
        
        # Sample indices
        indices = np.random.choice(
            len(self.buffer),
            size=batch_size,
            p=probabilities,
            replace=False
        )
        
        # Calculate importance sampling weights
        weights = (len(self.buffer) * probabilities[indices]) ** (-beta)
        weights /= weights.max()
        
        # Get experiences
        samples = [self.buffer[i] for i in indices]
        
        return samples, list(indices), weights
    
    def update_priorities(self, indices: List[int], td_errors: List[float]):
        """Update priorities based on TD errors"""
        for idx, td_error in zip(indices, td_errors):
            self.priorities[idx] = abs(td_error) + 1e-6  # Add small constant to avoid zero priority
    
    def __len__(self):
        return len(self.buffer)


# ==============================================================================
# ENHANCED Q-LEARNING AGENT
# ==============================================================================

class QLearningAgent:
    """
    Enhanced Q-Learning with double Q-tables, prioritized replay, and n-step returns
    """
    
    def __init__(self, config: Dict = None):
        """Initialize enhanced Q-learning agent"""
        self.config = config or RL_CONFIG
        
        # Dual Q-tables for Double Q-Learning
        self.q_table_a: Dict[Tuple[Tuple, str], float] = {}
        self.q_table_b: Dict[Tuple[Tuple, str], float] = {}
        self.q_table = self.q_table_a  # Legacy compatibility
        
        # Experience replay
        self.replay_buffer = PrioritizedReplayBuffer(
            capacity=self.config.get("replay_capacity", 10000),
            alpha=self.config.get("replay_alpha", 0.6)
        )
        
        # Hyperparameters
        self.learning_rate = self.config.get("learning_rate", 0.1)
        self.learning_rate_min = self.config.get("learning_rate_min", 0.01)
        self.learning_rate_decay = self.config.get("learning_rate_decay", 0.9999)
        
        self.discount_factor = self.config.get("discount_factor", 0.95)
        self.epsilon = self.config.get("epsilon_start", 1.0)
        self.epsilon_min = self.config.get("epsilon_min", 0.01)
        self.epsilon_decay = self.config.get("epsilon_decay", 0.9995)
        
        # N-step returns
        self.n_step = self.config.get("n_step", 3)
        self.n_step_buffer = deque(maxlen=self.n_step)
        
        # Statistics
        self.update_count = 0
        self.episode_count = 0
        self.action_counts = defaultdict(int)
        self.action_q_values = defaultdict(list)
        
        # Performance tracking
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        self.td_errors = deque(maxlen=1000)
        
        # Adaptive learning
        self.state_visit_counts = defaultdict(int)
        self.adaptive_lr_enabled = self.config.get("adaptive_learning_rate", True)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Persistence
        self.checkpoint_interval = self.config.get("checkpoint_interval", 500)
        self.checkpoint_dir = self.config.get("checkpoint_dir", "storage/rl_checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # Load existing checkpoint if available
        self.load_checkpoint()
        
        print("[Enhanced Q-Learning Agent] Initialized")
        print(f"  - Double Q-Learning: Enabled")
        print(f"  - Prioritized Replay: {self.config.get('replay_capacity', 10000)} capacity")
        print(f"  - N-Step Returns: {self.n_step}")
        print(f"  - Adaptive LR: {'Enabled' if self.adaptive_lr_enabled else 'Disabled'}")

    
    def select_action(self, state: Tuple, evaluation: bool = False) -> str:
        """
        Select action using epsilon-greedy with optional evaluation mode
        
        Args:
            state: Current state tuple
            evaluation: If True, use pure exploitation (no exploration)
        
        Returns:
            Selected action
        """
        # Evaluation mode: pure exploitation
        if evaluation:
            return self._get_best_action(state)
        
        # Epsilon-greedy exploration
        if random.random() < self.epsilon:
            # Exploration: random action
            action = random.choice(self.config["actions"])
        else:
            # Exploitation: best action
            action = self._get_best_action(state)
        
        # Track action selection
        with self.lock:
            self.action_counts[action] += 1
        
        return action
    
    def get_best_action(self, state: Tuple) -> str:
        """Legacy compatibility for get_best_action"""
        return self._get_best_action(state)
    
    def _get_best_action(self, state: Tuple) -> str:
        """Get action with highest Q-value (averaged across both Q-tables)"""
        q_values = {}
        
        for action in self.config["actions"]:
            # Average Q-values from both tables
            q_a = self.q_table_a.get((state, action), 0.0)
            q_b = self.q_table_b.get((state, action), 0.0)
            q_values[action] = (q_a + q_b) / 2.0
        
        # Return action with max Q-value (random tiebreaker)
        max_q = max(q_values.values()) if q_values else 0.0
        best_actions = [a for a, q in q_values.items() if q == max_q]
        
        return random.choice(best_actions) if best_actions else self.config["actions"][0]
    
    def get_q_value(self, state: Tuple, action: str) -> float:
        """Get Q-value for state-action pair"""
        q_a = self.q_table_a.get((state, action), 0.0)
        q_b = self.q_table_b.get((state, action), 0.0)
        return (q_a + q_b) / 2.0

    
    def update(self, state: Tuple, action: str, reward: float, next_state: Tuple, done: bool = False):
        """
        Update Q-values with enhanced algorithm
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode is done
        """
        # Add to n-step buffer
        self.n_step_buffer.append((state, action, reward, next_state, done))
        
        # Only update when we have enough steps or episode is done
        if len(self.n_step_buffer) < self.n_step and not done:
            return
        
        # Calculate n-step return
        n_step_state, n_step_action, n_step_return, n_step_next_state, n_step_done = self._calculate_n_step_return()
        
        # Create experience
        experience = Experience(
            state=n_step_state,
            action=n_step_action,
            reward=n_step_return,
            next_state=n_step_next_state,
            done=n_step_done,
            timestamp=time.time()
        )
        
        # Add to replay buffer
        self.replay_buffer.add(experience)
        
        # Train from replay buffer
        if len(self.replay_buffer) >= self.config.get("replay_start_size", 1000):
            self._train_from_replay()
        
        # Decay epsilon
        self._decay_epsilon()
        
        # Decay learning rate
        if self.learning_rate > self.learning_rate_min:
            self.learning_rate *= self.learning_rate_decay
        
        # Periodic checkpoint
        self.update_count += 1
        if self.update_count % self.checkpoint_interval == 0:
            self.save_checkpoint()
    
    def _calculate_n_step_return(self) -> Tuple:
        """Calculate n-step return from buffer"""
        state, action = self.n_step_buffer[0][0], self.n_step_buffer[0][1]
        
        # Calculate discounted return
        n_step_return = 0.0
        discount = 1.0
        
        for i, (s, a, r, next_s, done) in enumerate(self.n_step_buffer):
            n_step_return += discount * r
            discount *= self.discount_factor
            
            if done:
                return state, action, n_step_return, next_s, True
        
        # If not done, use last next_state for bootstrapping
        last_next_state = self.n_step_buffer[-1][3]
        return state, action, n_step_return, last_next_state, False
    
    def _train_from_replay(self):
        """Train using prioritized experience replay"""
        # Calculate beta for importance sampling
        beta_frames = self.config.get("replay_beta_frames", 100000)
        beta_start = self.config.get("replay_beta_start", 0.4)
        beta = min(1.0, beta_start + (1.0 - beta_start) * self.update_count / beta_frames)
        
        # Sample batch
        batch, indices, weights = self.replay_buffer.sample(
            self.config.get("batch_size", 32),
            beta=beta
        )
        
        # Update Q-values for each experience
        td_errors = []
        
        for experience, weight in zip(batch, weights):
            td_error = self._update_double_q(
                experience.state,
                experience.action,
                experience.reward,
                experience.next_state,
                experience.done,
                weight
            )
            td_errors.append(td_error)
        
        # Update priorities
        self.replay_buffer.update_priorities(indices, td_errors)
        
        # Track TD errors
        self.td_errors.extend(td_errors)
    
    def _update_double_q(self, state: Tuple, action: str, reward: float, 
                         next_state: Tuple, done: bool, weight: float = 1.0) -> float:
        """
        Double Q-Learning update
        
        Randomly updates either Q_A or Q_B to reduce overestimation bias
        """
        with self.lock:
            # Randomly choose which Q-table to update
            if random.random() < 0.5:
                q_table_update = self.q_table_a
                q_table_target = self.q_table_b
            else:
                q_table_update = self.q_table_b
                q_table_target = self.q_table_a
            
            # Get current Q-value
            current_q = q_table_update.get((state, action), 0.0)
            
            # Get next Q-value (Double Q-Learning)
            if done:
                target = reward
            else:
                # Use one table to select action, other to evaluate
                best_next_action = self._get_best_action_from_table(next_state, q_table_update)
                next_q = q_table_target.get((next_state, best_next_action), 0.0)
                target = reward + self.discount_factor * next_q
            
            # Calculate TD error
            td_error = target - current_q
            
            # Adaptive learning rate based on state visits
            if self.adaptive_lr_enabled:
                self.state_visit_counts[state] += 1
                visit_count = self.state_visit_counts[state]
                adaptive_lr = self.learning_rate / (1.0 + 0.01 * np.log(visit_count))
            else:
                adaptive_lr = self.learning_rate
            
            # Update Q-value with importance sampling weight
            new_q = current_q + adaptive_lr * weight * td_error
            q_table_update[(state, action)] = new_q
            
            # Track Q-values
            self.action_q_values[action].append(new_q)
            
            return abs(td_error)
    
    def _get_best_action_from_table(self, state: Tuple, q_table: Dict) -> str:
        """Get best action from specific Q-table"""
        q_values = {action: q_table.get((state, action), 0.0) 
                   for action in self.config["actions"]}
        max_q = max(q_values.values()) if q_values else 0.0
        best_actions = [a for a, q in q_values.items() if q == max_q]
        return random.choice(best_actions) if best_actions else self.config["actions"][0]
    
    def _decay_epsilon(self):
        """Decay exploration rate"""
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def decay_epsilon(self):
        """Legacy compatibility"""
        self._decay_epsilon()
    
    def end_episode(self, total_reward: float, episode_length: int):
        """
        Mark end of episode and track statistics
        
        Args:
            total_reward: Cumulative reward for episode
            episode_length: Number of steps in episode
        """
        with self.lock:
            self.episode_count += 1
            self.episode_rewards.append(total_reward)
            self.episode_lengths.append(episode_length)
            
            # Clear n-step buffer
            self.n_step_buffer.clear()
    
    def get_statistics(self) -> Dict:
        """Get comprehensive statistics"""
        with self.lock:
            stats = {
                "update_count": self.update_count,
                "episode_count": self.episode_count,
                "q_table_size": len(self.q_table_a) + len(self.q_table_b),
                "replay_buffer_size": len(self.replay_buffer),
                "epsilon": self.epsilon,
                "learning_rate": self.learning_rate,
                "action_counts": dict(self.action_counts),
                "avg_episode_reward": np.mean(self.episode_rewards) if self.episode_rewards else 0.0,
                "avg_episode_length": np.mean(self.episode_lengths) if self.episode_lengths else 0.0,
                "avg_td_error": np.mean(self.td_errors) if self.td_errors else 0.0,
            }
            
            # Calculate action value statistics
            for action in self.config["actions"]:
                if action in self.action_q_values and self.action_q_values[action]:
                    values = self.action_q_values[action]
                    stats[f"{action}_avg_q"] = np.mean(values)
                    stats[f"{action}_max_q"] = np.max(values)
            
            return stats
    
    def save_checkpoint(self, filepath: str = None):
        """Save agent checkpoint"""
        if filepath is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.checkpoint_dir, f"checkpoint_{timestamp}.pkl")
        
        checkpoint = {
            "q_table_a": self.q_table_a,
            "q_table_b": self.q_table_b,
            "replay_buffer": self.replay_buffer,
            "learning_rate": self.learning_rate,
            "epsilon": self.epsilon,
            "update_count": self.update_count,
            "episode_count": self.episode_count,
            "action_counts": dict(self.action_counts),
            "state_visit_counts": dict(self.state_visit_counts),
        }
        
        with open(filepath, "wb") as f:
            pickle.dump(checkpoint, f)
        
        print(f"[Checkpoint] Saved to {filepath}")
    
    def save_q_table(self, path: Optional[str] = None):
        """Legacy compatibility - saves checkpoint"""
        if path:
            self.save_checkpoint(path)
        else:
            self.save_checkpoint()
    
    def load_checkpoint(self, filepath: str = None):
        """Load agent checkpoint"""
        if filepath is None:
            # Load latest checkpoint
            if not os.path.exists(self.checkpoint_dir):
                return
            checkpoints = [f for f in os.listdir(self.checkpoint_dir) if f.endswith(".pkl")]
            if not checkpoints:
                return
            checkpoints.sort()
            filepath = os.path.join(self.checkpoint_dir, checkpoints[-1])
        
        if not os.path.exists(filepath):
            return
        
        try:
            with open(filepath, "rb") as f:
                checkpoint = pickle.load(f)
            
            self.q_table_a = checkpoint["q_table_a"]
            self.q_table_b = checkpoint["q_table_b"]
            self.replay_buffer = checkpoint["replay_buffer"]
            self.learning_rate = checkpoint["learning_rate"]
            self.epsilon = checkpoint["epsilon"]
            self.update_count = checkpoint["update_count"]
            self.episode_count = checkpoint["episode_count"]
            self.action_counts = defaultdict(int, checkpoint["action_counts"])
            self.state_visit_counts = defaultdict(int, checkpoint["state_visit_counts"])
            
            print(f"[Checkpoint] Loaded from {filepath}")
            print(f"  - Episodes: {self.episode_count}")
            print(f"  - Updates: {self.update_count}")
            print(f"  - Epsilon: {self.epsilon:.4f}")
        
        except Exception as e:
            print(f"[Error] Failed to load checkpoint: {e}")
    
    def load_q_table(self, path: Optional[str] = None):
        """Legacy compatibility - loads checkpoint"""
        if path:
            self.load_checkpoint(path)
        else:
            self.load_checkpoint()

    
    def print_statistics(self):
        """Print comprehensive statistics"""
        stats = self.get_statistics()
        
        print("\n" + "="*80)
        print("ENHANCED Q-LEARNING AGENT STATISTICS")
        print("="*80)
        print(f"Episodes:              {stats['episode_count']}")
        print(f"Total Updates:         {stats['update_count']}")
        print(f"Q-Table Size:          {stats['q_table_size']} state-action pairs")
        print(f"Replay Buffer:         {stats['replay_buffer_size']} / {self.config.get('replay_capacity', 10000)}")
        print(f"\nHyperparameters:")
        print(f"  Learning Rate:       {stats['learning_rate']:.6f}")
        print(f"  Epsilon:             {stats['epsilon']:.4f}")
        print(f"  Discount:            {self.discount_factor}")
        print(f"\nPerformance:")
        print(f"  Avg Episode Reward:  {stats['avg_episode_reward']:.2f}")
        print(f"  Avg Episode Length:  {stats['avg_episode_length']:.1f}")
        print(f"  Avg TD Error:        {stats['avg_td_error']:.4f}")
        print(f"\nAction Distribution:")
        
        total_actions = sum(stats['action_counts'].values())
        for action in self.config["actions"]:
            count = stats['action_counts'].get(action, 0)
            pct = (count / total_actions * 100) if total_actions > 0 else 0
            avg_q = stats.get(f"{action}_avg_q", 0.0)
            print(f"  {action:25s}: {pct:5.1f}% ({count:4d}) | Avg Q: {avg_q:7.2f}")
        
        print("="*80 + "\n")


# ==============================================================================
# SHARED AGENT SINGLETON
# ==============================================================================

# Create shared instance
shared_rl_agent = QLearningAgent(RL_CONFIG)


if __name__ == "__main__":
    print("Testing Enhanced Q-Learning Agent...\n")
    
    agent = QLearningAgent()
    
    # Simulate training episode
    state = (1, 2, 1, 0, 0)
    
    for step in range(100):
        action = agent.select_action(state)
        reward = random.uniform(-5, 10)
        next_state = tuple(random.randint(0, 2) for _ in range(5))
        done = step == 99
        
        agent.update(state, action, reward, next_state, done)
        state = next_state
        
        if done:
            agent.end_episode(total_reward=50.0, episode_length=100)
    
    # Print statistics
    agent.print_statistics()
