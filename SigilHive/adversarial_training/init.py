"""
SigilHive Adversarial Training System
════════════════════════════════════════════════════════════════════════════

Complete adversarial training environment with:
  • LangGraph-based attack planning (Gemini AI)
  • Reinforcement learning (Double Q-Learning with prioritized replay)
  • Adaptive file structure evolution
  • Multi-protocol honeypot coordination
  • Real-time monitoring and metrics

Version 2.0: Full LangGraph integration for seamless workflow management.

Quick Start:
    from adversarial_training import get_training_app, ExecutionMode
    
    app = get_training_app()
    results = app.start_training(mode=ExecutionMode.TRAINING, max_episodes=50)

For honeypots:
    from adversarial_training import get_training_app
    from rl_core import shared_rl_agent
    
    app = get_training_app()
    rl_agent = app.get_rl_agent()
"""

from .adversarial_agent import AdversarialAgent, AttackPhase, AttackResult, Protocol, AgentState
from .attack_scheduler import AttackScheduler, AttackConfig
from .training_integration import TrainingIntegration, HoneypotState, Experience, PrioritizedReplayBuffer
from .orchestrator import Orchestrator, OrchestratorMode

# LangGraph Integration (v2.0)
from .langgraph_integration import (
    LangGraphTrainingSystem,
    ExecutionMode,
    SystemPhase,
    TrainingSystemState,
    TrainingSystemNodes,
    EnvironmentSnapshot,
    StrategyDecision,
    AttackExecution,
    LearningUpdate,
    EvolutionDecision,
)

# Application Integration
from .app_integration import (
    SigilHiveAdversarialTraining,
    TrainingConfig,
    initialize_training_app,
    get_training_app,
)

__all__ = [
    # Core Components (v1.0)
    "AdversarialAgent",
    "AttackPhase",
    "AttackResult",
    "Protocol",
    "AgentState",
    "AttackScheduler",
    "AttackConfig",
    "TrainingIntegration",
    "HoneypotState",
    "Experience",
    "PrioritizedReplayBuffer",
    "Orchestrator",
    "OrchestratorMode",
    
    # LangGraph Integration (v2.0)
    "LangGraphTrainingSystem",
    "ExecutionMode",
    "SystemPhase",
    "TrainingSystemState",
    "TrainingSystemNodes",
    "EnvironmentSnapshot",
    "StrategyDecision",
    "AttackExecution",
    "LearningUpdate",
    "EvolutionDecision",
    
    # Application Integration
    "SigilHiveAdversarialTraining",
    "TrainingConfig",
    "initialize_training_app",
    "get_training_app",
]

__version__ = "2.0.0"
__description__ = "LangGraph-based adversarial training with integrated RL, file evolution, and monitoring"