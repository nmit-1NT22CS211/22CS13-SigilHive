"""
LangGraph-Based Adversarial Training System Integration
════════════════════════════════════════════════════════════════════════════

Unified workflow orchestrating:
  • Adversarial Agent (Gemini-powered attack planning)
  • Q-Learning Agent (strategy selection & learning)
  • Honeypot Services (HTTP, SSH, Database)
  • Training Integration (RL feedback loop)
  • File Structure Evolution (adaptive defense)

This creates a complete adversarial training cycle:
  observe_environment → select_strategy → execute_attack → evaluate_results
  → update_learning → evolve_honeypot → next_episode
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from .adversarial_agent import AdversarialAgent, AttackPhase, Protocol, AttackResult
from .training_integration import (
    TrainingIntegration,
    HoneypotState,
    Experience,
)
from rl_core import shared_rl_agent, extract_state, calculate_reward

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  State Management
# ════════════════════════════════════════════════════════════════════════════

class ExecutionMode(str, Enum):
    """Execution mode for the training system."""
    TRAINING = "training"        # Full learning loop
    EVALUATION = "evaluation"    # No learning updates
    TESTING = "testing"          # Single attack for testing


class SystemPhase(str, Enum):
    """High-level system phase in the adversarial training cycle."""
    OBSERVE = "observe"
    PLAN = "plan"
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    LEARN = "learn"
    EVOLVE = "evolve"
    COMPLETE = "complete"


@dataclass
class EnvironmentSnapshot:
    """Current state of the honeypot environment."""
    timestamp: float = field(default_factory=time.time)
    suspicion_level: float = 0.0
    active_sessions: int = 0
    recent_attacks: list[AttackResult] = field(default_factory=list)
    evolution_count: int = 0
    honeypot_state: Optional[HoneypotState] = None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyDecision:
    """Decision made by RL agent for attack strategy."""
    action: str  # Evolution strategy or attack approach
    q_value: float
    epsilon: float
    reasoning: str = ""
    selected_protocol: str = "http"
    intensity_level: int = 1  # 1-3 scale


@dataclass
class AttackExecution:
    """Result of executing an attack."""
    attack_results: list[AttackResult] = field(default_factory=list)
    total_suspicion_delta: float = 0.0
    data_exfiltrated: dict[str, Any] = field(default_factory=dict)
    honeypot_responses: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    success: bool = False


@dataclass
class LearningUpdate:
    """Information about learning update."""
    reward: float
    td_error: float
    q_table_size: int
    batch_size: int
    learning_rate: float
    epsilon: float
    is_episode_terminal: bool = False


@dataclass
class EvolutionDecision:
    """Decision about evolving honeypot structure (disabled)."""
    should_evolve: bool
    reward_delta: float = 0.0
    changes_made: list[str] = field(default_factory=list)


class TrainingSystemState(TypedDict):
    """Main state for the LangGraph training system."""
    # Phase tracking
    current_phase: str
    execution_mode: str
    episode_number: int
    step_number: int

    # Environment observation
    environment: EnvironmentSnapshot

    # Attack planning
    strategy_decision: Optional[StrategyDecision]
    gemini_reasoning: str

    # Execution
    attack_execution: Optional[AttackExecution]
    error_message: Optional[str]

    # Learning
    learning_update: Optional[LearningUpdate]
    experience: Optional[Experience]

    # Evolution
    evolution_decision: Optional[EvolutionDecision]

    # Metrics & history
    episode_summary: dict[str, Any]
    attack_history: list[dict]

    # Control signals
    should_continue: bool
    should_abort: bool


# ════════════════════════════════════════════════════════════════════════════
#  Node Functions
# ════════════════════════════════════════════════════════════════════════════

class TrainingSystemNodes:
    """Node implementations for the LangGraph training workflow."""

    def __init__(
        self,
        adversarial_agent: AdversarialAgent,
        training_integration: TrainingIntegration,
    ):
        self.adversarial_agent = adversarial_agent
        self.training_integration = training_integration

    def observe_environment(self, state: TrainingSystemState) -> TrainingSystemState:
        """📊 Observe current environment state."""
        logger.info(f"[OBSERVE] Step {state['step_number']}")

        try:
            # Gather honeypot metrics
            recent_attacks = getattr(
                self.adversarial_agent, "attack_history", []
            )[-10:]  # Last 10 attacks

            # Extract state from recent attacks
            if recent_attacks:
                honeypot_state = self.training_integration.extract_state(recent_attacks)
            else:
                honeypot_state = HoneypotState()

            # Create environment snapshot
            snapshot = EnvironmentSnapshot(
                suspicion_level=honeypot_state.suspicion_level,
                active_sessions=honeypot_state.commands_per_session,
                recent_attacks=recent_attacks,
                evolution_count=honeypot_state.evolution_count,
                honeypot_state=honeypot_state,
                metrics={
                    "total_sessions": len(recent_attacks),
                    "avg_suspicion": honeypot_state.suspicion_level,
                    "data_fields_exposed": honeypot_state.data_exfiltrated_fields,
                    "tables_probed": honeypot_state.probed_table_ratio,
                },
            )

            state["environment"] = snapshot
            state["current_phase"] = SystemPhase.OBSERVE.value

            logger.debug(
                f"  Environment captured: suspicion={snapshot.suspicion_level:.2f}, "
                f"sessions={snapshot.active_sessions}"
            )

        except Exception as e:
            logger.error(f"Environment observation failed: {e}", exc_info=True)
            state["error_message"] = str(e)

        return state

    def plan_strategy(self, state: TrainingSystemState) -> TrainingSystemState:
        """🧠 RL Agent selects attack strategy."""
        logger.info(f"[PLAN] Step {state['step_number']}")

        try:
            honeypot_state = state["environment"].honeypot_state
            if not honeypot_state:
                raise ValueError("No honeypot state available")

            # Convert to discrete state for Q-learning
            state_key = honeypot_state.to_key()

            # Q-Learning agent selects action
            action = shared_rl_agent.select_action(
                state=self._state_tuple_from_honeypot(honeypot_state),
                evaluation=state["execution_mode"] == ExecutionMode.EVALUATION.value,
            )

            # Determine protocol and intensity
            protocol = self._select_protocol(honeypot_state)
            intensity = self._calculate_intensity(honeypot_state.suspicion_level)

            decision = StrategyDecision(
                action=action,
                q_value=self._get_q_value(state_key, action),
                epsilon=shared_rl_agent.epsilon,
                reasoning=f"State: {state_key}, Action: {action}",
                selected_protocol=protocol,
                intensity_level=intensity,
            )

            state["strategy_decision"] = decision
            state["current_phase"] = SystemPhase.PLAN.value

            logger.info(
                f"  Strategy selected: {action} | Protocol: {protocol} | "
                f"Intensity: {intensity}/3 | Q={decision.q_value:.3f}"
            )

        except Exception as e:
            logger.error(f"Strategy planning failed: {e}", exc_info=True)
            state["error_message"] = str(e)
            state["should_abort"] = True

        return state

    def execute_attack(self, state: TrainingSystemState) -> TrainingSystemState:
        """⚔️ Execute the adversarial attack."""
        logger.info(f"[EXECUTE] Step {state['step_number']}")

        try:
            strategy_decision = state["strategy_decision"]
            if not strategy_decision:
                raise ValueError("No strategy decision available")

            protocol = Protocol[strategy_decision.selected_protocol.upper()]
            intensity = strategy_decision.intensity_level

            # Execute attack via adversarial agent
            attack_results = []
            total_suspicion_delta = 0.0

            for _ in range(intensity):
                # Build and run attack
                result = self.adversarial_agent.run_attack(protocol)
                if result:
                    attack_results.append(result)
                    total_suspicion_delta += result.suspicion_delta

            execution = AttackExecution(
                attack_results=attack_results,
                total_suspicion_delta=total_suspicion_delta,
                success=len(attack_results) > 0,
                execution_time=time.time() - state["environment"].timestamp,
            )

            state["attack_execution"] = execution
            state["current_phase"] = SystemPhase.EXECUTE.value

            logger.info(
                f"  Attack executed: {len(attack_results)} phases, "
                f"suspicion_delta={total_suspicion_delta:.2f}"
            )

        except Exception as e:
            logger.error(f"Attack execution failed: {e}", exc_info=True)
            state["error_message"] = str(e)

        return state

    def evaluate_results(self, state: TrainingSystemState) -> TrainingSystemState:
        """📈 Evaluate attack results and extract reward signal."""
        logger.info(f"[EVALUATE] Step {state['step_number']}")

        try:
            environment = state["environment"]
            execution = state["attack_execution"]

            if not execution:
                raise ValueError("No attack execution data")

            # Calculate reward using training integration
            old_state = environment.honeypot_state
            
            # Update environment to get new state
            self.observe_environment(state)
            new_state = state["environment"].honeypot_state

            # Convert to tuple format for reward calculation
            old_state_tuple = self._state_tuple_from_honeypot(old_state)
            new_state_tuple = self._state_tuple_from_honeypot(new_state)

            # Calculate multi-factor reward
            reward = calculate_reward(
                old_state_tuple,
                new_state_tuple,
                protocol=state["strategy_decision"].selected_protocol,
            )

            # Calculate TD error
            td_error = self._calculate_td_error(
                old_state_tuple,
                state["strategy_decision"].action,
                reward,
                new_state_tuple,
            )

            state["learning_update"] = LearningUpdate(
                reward=reward,
                td_error=td_error,
                q_table_size=len(shared_rl_agent.q_table_a),
                batch_size=0,  # Updated in learning phase
                learning_rate=shared_rl_agent.config.get("learning_rate", 0.1),
                epsilon=shared_rl_agent.epsilon,
                is_episode_terminal=False,
            )

            state["current_phase"] = SystemPhase.EVALUATE.value

            logger.info(
                f"  Evaluation complete: reward={reward:.3f}, "
                f"td_error={td_error:.4f}"
            )

        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            state["error_message"] = str(e)

        return state

    def update_learning(self, state: TrainingSystemState) -> TrainingSystemState:
        """🎓 Update Q-Learning agent with new experience."""
        logger.info(f"[LEARN] Step {state['step_number']}")

        if state["execution_mode"] == ExecutionMode.EVALUATION.value:
            logger.info("  Skipping learning update (evaluation mode)")
            return state

        try:
            strategy = state["strategy_decision"]
            environment = state["environment"]
            learning = state["learning_update"]

            if not all([strategy, environment, learning]):
                raise ValueError("Missing required state for learning")

            old_state = self._state_tuple_from_honeypot(environment.honeypot_state)
            
            # Observe new state
            self.observe_environment(state)
            new_state = self._state_tuple_from_honeypot(
                state["environment"].honeypot_state
            )

            # Update Q-Learning agent
            shared_rl_agent.update(
                state=old_state,
                action=strategy.action,
                reward=learning.reward,
                next_state=new_state,
                done=False,
            )

            # Update learning update stats
            learning.batch_size = len(shared_rl_agent.replay_buffer)

            state["current_phase"] = SystemPhase.LEARN.value

            logger.info(
                f"  Q-table updated: |Q-table|={len(shared_rl_agent.q_table_a)}, "
                f"ε={shared_rl_agent.epsilon:.4f}"
            )

        except Exception as e:
            logger.error(f"Learning update failed: {e}", exc_info=True)
            state["error_message"] = str(e)

        return state

    def make_evolution_decision(self, state: TrainingSystemState) -> TrainingSystemState:
        """🔄 Decide whether to evolve honeypot structure."""
        logger.info(f"[EVOLVE] Step {state['step_number']}")

        try:
            learning = state["learning_update"]
            if not learning:
                raise ValueError("No learning data available")

            # Evolution trigger: if learning is successful and Q-table growing
            should_evolve = (
                learning.reward > 0.3
                and learning.q_table_size > 50
                and state["step_number"] % 10 == 0  # Every 10 steps
            )

            evolution_decision = EvolutionDecision(
                should_evolve=should_evolve,
                reward_delta=learning.reward,
            )

            if should_evolve:
                logger.info(
                    f"  Honeypot evolution disabled (FileStructureEvolver removed)"
                )

            state["evolution_decision"] = evolution_decision
            state["current_phase"] = SystemPhase.EVOLVE.value

        except Exception as e:
            logger.error(f"Evolution decision failed: {e}", exc_info=True)
            state["error_message"] = str(e)

        return state

    def complete_step(self, state: TrainingSystemState) -> TrainingSystemState:
        """✅ Complete the training step and prepare for next iteration."""
        logger.info(f"[COMPLETE] Step {state['step_number']}")

        try:
            # Update episode summary
            state["step_number"] += 1
            state["current_phase"] = SystemPhase.COMPLETE.value

            # Record to history
            step_record = {
                "step": state["step_number"],
                "episode": state["episode_number"],
                "phase": SystemPhase.COMPLETE.value,
                "timestamp": time.time(),
                "reward": state["learning_update"].reward if state["learning_update"] else 0.0,
                "evolved": (
                    state["evolution_decision"].should_evolve
                    if state["evolution_decision"]
                    else False
                ),
            }

            state["attack_history"].append(step_record)

            # Determine continuation
            state["should_continue"] = (
                state["step_number"] < 1000
                and not state["should_abort"]
                and state["error_message"] is None
            )

            logger.info(
                f"  Step complete | Next: {state['should_continue']}"
            )

        except Exception as e:
            logger.error(f"Step completion failed: {e}", exc_info=True)

        return state

    def handle_error(self, state: TrainingSystemState) -> TrainingSystemState:
        """❌ Handle errors gracefully."""
        logger.error(f"[ERROR] {state['error_message']}")
        state["should_continue"] = False
        state["should_abort"] = True
        return state

    # ────────────────────────────────────────────────────────────────────────
    #  Helper Methods
    # ────────────────────────────────────────────────────────────────────────

    def _state_tuple_from_honeypot(self, honeypot_state: HoneypotState) -> tuple:
        """Convert HoneypotState to 5-element tuple for reward calculation.
        
        Maps to: (rate, unique, duration, errors, privesc)
        """
        return (
            int(honeypot_state.attack_frequency * 10),  # rate: discretize frequency
            honeypot_state.commands_per_session,         # unique: number of commands
            int(honeypot_state.time_since_last_attack),  # duration: seconds since last attack
            int(honeypot_state.suspicion_level * 10),    # errors: discretize suspicion
            1 if honeypot_state.data_exfiltrated_fields > 0 else 0,  # privesc: any data exfil?
        )

    def _get_q_value(self, state_key: str, action: str) -> float:
        """Get Q-value for a state-action pair."""
        return shared_rl_agent.q_table_a.get((state_key, action), 0.0)

    def _select_protocol(self, honeypot_state: HoneypotState) -> str:
        """Select protocol based on state."""
        # Rotate protocols or choose based on suspicion
        protocols = ["http", "ssh", "database"]
        if honeypot_state.suspicion_level > 0.5:
            return "database"  # Switch to stealthier protocol
        return protocols[int(honeypot_state.evolution_count % 3)]

    def _calculate_intensity(self, suspicion_level: float) -> int:
        """Calculate attack intensity based on suspicion."""
        if suspicion_level > 0.75:
            return 1  # Low intensity when highly suspicious
        elif suspicion_level > 0.5:
            return 2  # Medium intensity
        return 3  # High intensity when suspicion is low

    def _calculate_td_error(
        self,
        state: tuple,
        action: str,
        reward: float,
        next_state: tuple,
    ) -> float:
        """Calculate TD error for experience replay."""
        current_q = shared_rl_agent.q_table_a.get((state, action), 0.0)
        next_q = max(
            [
                shared_rl_agent.q_table_b.get((next_state, a), 0.0)
                for a in shared_rl_agent.config.get("actions", [])
            ],
            default=0.0,
        )
        target_q = reward + 0.99 * next_q
        return abs(target_q - current_q)



# ════════════════════════════════════════════════════════════════════════════
#  Main Training System
# ════════════════════════════════════════════════════════════════════════════

class LangGraphTrainingSystem:
    """
    Main LangGraph-based adversarial training system.

    Workflow:
      observe → plan → execute → evaluate → learn → complete
      ↑                                                 ↓
      └──────────── continue if should_continue? ──────┘

    Usage:
        system = LangGraphTrainingSystem(
            adversarial_agent=agent,
            training_integration=training,
        )
        results = system.run(
            mode=ExecutionMode.TRAINING,
            max_episodes=100,
            max_steps_per_episode=50,
        )
    """

    def __init__(
        self,
        adversarial_agent: AdversarialAgent,
        training_integration: TrainingIntegration,
    ):
        self.adversarial_agent = adversarial_agent
        self.training_integration = training_integration
        self.nodes_impl = TrainingSystemNodes(
            adversarial_agent, training_integration
        )
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Construct the LangGraph workflow."""
        graph = StateGraph(TrainingSystemState)

        # Add nodes
        graph.add_node("observe", self.nodes_impl.observe_environment)
        graph.add_node("plan", self.nodes_impl.plan_strategy)
        graph.add_node("execute", self.nodes_impl.execute_attack)
        graph.add_node("evaluate", self.nodes_impl.evaluate_results)
        graph.add_node("learn", self.nodes_impl.update_learning)
        graph.add_node("evolve", self.nodes_impl.make_evolution_decision)
        graph.add_node("complete", self.nodes_impl.complete_step)
        graph.add_node("error", self.nodes_impl.handle_error)

        # Define edges
        graph.set_entry_point("observe")

        graph.add_edge("observe", "plan")
        graph.add_edge("plan", "execute")
        graph.add_edge("execute", "evaluate")
        graph.add_edge("evaluate", "learn")
        graph.add_edge("learn", "evolve")
        graph.add_edge("evolve", "complete")

        # Conditional edge for continuation
        def router(state: TrainingSystemState) -> str:
            return "observe" if state["should_continue"] else "__end__"
        
        graph.add_conditional_edges(
            "complete",
            router,
            {"observe": "observe", "__end__": END},
        )

        # Error handling
        graph.add_edge("error", END)

        return graph.compile()

    def run(
        self,
        mode: ExecutionMode = ExecutionMode.TRAINING,
        max_episodes: int = 10,
        max_steps_per_episode: int = 50,
    ) -> dict[str, Any]:
        """
        Run the adversarial training system.

        Args:
            mode: TRAINING, EVALUATION, or TESTING
            max_episodes: Maximum episodes to run
            max_steps_per_episode: Maximum steps per episode

        Returns:
            Summary of training results
        """
        logger.info("=" * 70)
        logger.info("  LANGGRAPH ADVERSARIAL TRAINING SYSTEM")
        logger.info(f"  Mode: {mode.value} | Episodes: {max_episodes} | "
                    f"Steps/episode: {max_steps_per_episode}")
        logger.info("=" * 70)

        session_start = time.time()
        all_results = []

        for episode in range(max_episodes):
            logger.info(f"\n{'=' * 70}")
            logger.info(f"  EPISODE {episode + 1}/{max_episodes}")
            logger.info(f"{'=' * 70}\n")

            initial_state: TrainingSystemState = {
                "current_phase": SystemPhase.OBSERVE.value,
                "execution_mode": mode.value,
                "episode_number": episode + 1,
                "step_number": 0,
                "environment": EnvironmentSnapshot(),
                "strategy_decision": None,
                "attack_execution": None,
                "error_message": None,
                "gemini_reasoning": "",
                "learning_update": None,
                "experience": None,
                "evolution_decision": None,
                "episode_summary": {},
                "attack_history": [],
                "should_continue": True,
                "should_abort": False,
            }

            # Run single episode
            for step in range(max_steps_per_episode):
                initial_state["step_number"] = step

                try:
                    final_state = self.workflow.invoke(initial_state)
                    all_results.append(final_state)
                    initial_state = final_state

                    if not initial_state["should_continue"]:
                        logger.info(
                            f"\nEpisode {episode + 1} terminated at step {step}"
                        )
                        break

                except Exception as e:
                    logger.error(
                        f"Workflow execution error at step {step}: {e}",
                        exc_info=True,
                    )
                    initial_state["should_abort"] = True
                    break

            # End episode
            total_reward = sum(
                r.get("reward", 0.0)
                for r in initial_state.get("attack_history", [])
            )
            episode_length = initial_state["step_number"]
            shared_rl_agent.end_episode(
                total_reward=total_reward,
                episode_length=episode_length,
            )

            episode_duration = time.time() - session_start
            logger.info(
                f"\nEpisode {episode + 1} complete | "
                f"Duration: {episode_duration:.1f}s | "
                f"Steps: {episode_length} | "
                f"Reward: {total_reward:.2f}"
            )

        # Generate summary
        summary = self._generate_summary(all_results, session_start)
        logger.info("\n" + "=" * 70)
        logger.info("  TRAINING COMPLETE")
        logger.info("=" * 70)
        self._print_summary(summary)

        return summary

    def _generate_summary(
        self, results: list[dict], session_start: float
    ) -> dict[str, Any]:
        """Generate training summary from results."""
        return {
            "total_steps": len(results),
            "total_duration": time.time() - session_start,
            "q_table_size": len(shared_rl_agent.q_table_a),
            "final_epsilon": shared_rl_agent.epsilon,
            "replay_buffer_size": len(
                shared_rl_agent.replay_buffer
            ) if hasattr(shared_rl_agent, 'replay_buffer') else 0,
            "stats": shared_rl_agent.get_statistics(),
        }

    def _print_summary(self, summary: dict) -> None:
        """Print training summary."""
        print(f"\n  Total Steps:        {summary['total_steps']}")
        print(f"  Total Duration:     {summary['total_duration']:.1f}s")
        print(f"  Q-Table Size:       {summary['q_table_size']}")
        print(f"  Final Epsilon:      {summary['final_epsilon']:.4f}")
        print(f"  Replay Buffer Size: {summary['replay_buffer_size']}")
        
        stats = summary.get('stats', {})
        if stats:
            print(f"\n  RL Agent Statistics:")
            print(f"    Episodes:        {stats.get('episode_count', 0)}")
            print(f"    Avg Reward:      {stats.get('avg_episode_reward', 0):.3f}")
            print(f"    Success Rate:    {stats.get('success_rate', 0):.1%}")
