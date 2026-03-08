"""
SigilHive Application Integration Layer
════════════════════════════════════════════════════════════════════════════

Main entry point for integrating the LangGraph adversarial training system
with the SigilHive honeypot application.

Provides high-level APIs for:
  • Starting adversarial training sessions
  • Running in different execution modes
  • Real-time monitoring and metrics
  • Integration with honeypot services
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from .adversarial_agent import AdversarialAgent
from .training_integration import TrainingIntegration
from .langgraph_integration import (
    LangGraphTrainingSystem,
    ExecutionMode,
    TrainingSystemState,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  Configuration
# ════════════════════════════════════════════════════════════════════════════

class TrainingConfig:
    """Configuration for adversarial training."""

    def __init__(self):
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.target_host = os.environ.get("TARGET_HOST", "localhost")
        self.ssh_port = int(os.environ.get("SSH_PORT", "5555"))
        self.http_port = int(os.environ.get("HTTP_PORT", "8080"))
        self.db_port = int(os.environ.get("DB_PORT", "2225"))
        self.max_episodes = int(os.environ.get("MAX_EPISODES", "50"))
        self.max_steps_per_episode = int(os.environ.get("MAX_STEPS", "100"))
        self.checkpoint_dir = os.environ.get("CHECKPOINT_DIR", "rl_checkpoints")
        self.metrics_file = os.environ.get("METRICS_FILE", "training_metrics.json")
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        
        # Attack Scheduling Configuration
        self.enable_scheduling = os.environ.get("ENABLE_SCHEDULING", "false").lower() == "true"
        self.attack_interval_days = int(float(os.environ.get("ATTACK_INTERVAL_DAYS", "1")))
        self.attack_interval_hours = int(float(os.environ.get("ATTACK_INTERVAL_HOURS", "0")))
        self.attack_interval_minutes = int(float(os.environ.get("ATTACK_INTERVAL_MINUTES", "0")))
        
        # Convert days, hours, and minutes to seconds
        self.interval_seconds = (
            (self.attack_interval_days * 24 * 3600) + 
            (self.attack_interval_hours * 3600) + 
            (self.attack_interval_minutes * 60)
        )

    @classmethod
    def from_file(cls, config_path: str) -> "TrainingConfig":
        """Load configuration from JSON file."""
        config = cls()
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                # Recalculate interval_seconds after loading
                if "attack_interval_days" in data or "attack_interval_hours" in data or "attack_interval_minutes" in data:
                    config.interval_seconds = (
                        (config.attack_interval_days * 24 * 3600) + 
                        (config.attack_interval_hours * 3600) + 
                        (config.attack_interval_minutes * 60)
                    )
        return config

    def validate(self) -> None:
        """Validate configuration."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        if not self.target_host:
            raise ValueError("TARGET_HOST not set")
        if self.attack_interval_days < 0 or self.attack_interval_hours < 0:
            raise ValueError("Attack interval cannot be negative")


# ════════════════════════════════════════════════════════════════════════════
#  Main Application Integration
# ════════════════════════════════════════════════════════════════════════════

class SigilHiveAdversarialTraining:
    """
    Main application class for integrating adversarial training with SigilHive.

    This class:
      • Initializes all components (RL agent, adversarial agent, file evolver)
      • Manages training sessions
      • Provides monitoring and metrics
      • Handles graceful shutdown
      • Integrates with honeypot services

    Usage:
        app = SigilHiveAdversarialTraining()
        results = app.start_training(
            mode=ExecutionMode.TRAINING,
            max_episodes=50,
        )

    Advanced Usage:
        app = SigilHiveAdversarialTraining(config_path="config.json")
        
        # Set up callbacks
        app.on_step_complete = lambda state: print(f"Step {state['step_number']}")
        
        # Start training with monitoring
        app.start_training_async(
            mode=ExecutionMode.TRAINING,
            monitor=True,
        )
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the adversarial training system."""
        # Load configuration
        self.config = (
            TrainingConfig.from_file(config_path)
            if config_path
            else TrainingConfig()
        )
        self.config.validate()

        # Setup logging
        self._setup_logging()

        # Initialize components
        logger.info("Initializing SigilHive adversarial training...")
        self.adversarial_agent = AdversarialAgent(
            gemini_api_key=self.config.gemini_api_key,
            target_host=self.config.target_host,
            ssh_port=self.config.ssh_port,
            http_port=self.config.http_port,
            db_port=self.config.db_port,
        )
        logger.info("✓ Adversarial agent initialized")

        self.training_integration = TrainingIntegration(
            agent=self.adversarial_agent,
        )
        logger.info("✓ Training integration initialized")

        # Initialize LangGraph system
        self.training_system = LangGraphTrainingSystem(
            adversarial_agent=self.adversarial_agent,
            training_integration=self.training_integration,
        )
        logger.info("✓ LangGraph training system initialized")

        # State management
        self._running = False
        self._paused = False
        self.metrics = {
            "sessions_started": 0,
            "total_episodes": 0,
            "total_steps": 0,
            "avg_reward": 0.0,
            "evolve_count": 0,
            "last_training_time": None,
        }

        # Callbacks
        self.on_step_complete: Optional[Callable[[TrainingSystemState], None]] = None
        self.on_episode_complete: Optional[Callable[[int, dict], None]] = None
        self.on_training_complete: Optional[Callable[[dict], None]] = None

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info("=" * 70)
        logger.info("SigilHive Adversarial Training System Ready")
        logger.info("=" * 70)

    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def _handle_shutdown(self, signum, frame) -> None:
        """Handle graceful shutdown."""
        logger.info("\nShutdown signal received, stopping gracefully...")
        self._running = False
        self.save_metrics()
        logger.info("Shutdown complete")
        sys.exit(0)

    # ────────────────────────────────────────────────────────────────────────
    #  Training Control
    # ────────────────────────────────────────────────────────────────────────

    def start_training(
        self,
        mode: ExecutionMode = ExecutionMode.TRAINING,
        max_episodes: Optional[int] = None,
        max_steps_per_episode: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Start adversarial training session.

        Args:
            mode: TRAINING, EVALUATION, or TESTING
            max_episodes: Override config value
            max_steps_per_episode: Override config value

        Returns:
            Training results summary
        """
        if self._running:
            raise RuntimeError("Training already in progress")

        self._running = True
        self.metrics["sessions_started"] += 1

        try:
            max_ep = max_episodes or self.config.max_episodes
            max_steps = max_steps_per_episode or self.config.max_steps_per_episode

            logger.info(
                f"\nStarting training session | Mode: {mode.value} | "
                f"Episodes: {max_ep} | Steps/episode: {max_steps}"
            )

            results = self.training_system.run(
                mode=mode,
                max_episodes=max_ep,
                max_steps_per_episode=max_steps,
            )

            self.metrics["total_episodes"] += max_ep
            self.metrics["total_steps"] += results.get("total_steps", 0)
            self.metrics["avg_reward"] = results.get("stats", {}).get(
                "avg_episode_reward", 0.0
            )

            # Trigger callback
            if self.on_training_complete:
                self.on_training_complete(results)

            logger.info(f"\n✓ Training session complete")
            self.save_metrics()

            return results

        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            raise
        finally:
            self._running = False

    def start_training_async(
        self,
        mode: ExecutionMode = ExecutionMode.TRAINING,
        monitor: bool = False,
    ) -> asyncio.Task:
        """
        Start training in background (async).

        Args:
            mode: ExecutionMode
            monitor: Print real-time monitoring info

        Returns:
            asyncio.Task for the training session
        """
        async def run_training():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self.start_training, mode
            )

        task = asyncio.create_task(run_training())

        if monitor:
            asyncio.create_task(self._monitor_training(task))

        return task

    async def _monitor_training(self, task: asyncio.Task) -> None:
        """Monitor training progress."""
        while not task.done():
            stats = self.get_current_stats()
            print(
                f"\r[Monitor] Steps: {stats['total_steps']} | "
                f"Episodes: {stats['total_episodes']} | "
                f"Avg Reward: {stats['avg_reward']:.3f}",
                end="",
            )
            await asyncio.sleep(5)

    def pause_training(self) -> None:
        """Pause ongoing training (not yet implemented in LangGraph)."""
        logger.warning("Pause not yet implemented")

    def resume_training(self) -> None:
        """Resume paused training."""
        logger.warning("Resume not yet implemented")

    def stop_training(self) -> dict[str, Any]:
        """Stop training and return summary."""
        self._running = False
        logger.info("Training stopped by user")
        return self.get_metrics()

    # ────────────────────────────────────────────────────────────────────────
    #  Monitoring & Metrics
    # ────────────────────────────────────────────────────────────────────────

    def get_current_stats(self) -> dict[str, Any]:
        """Get current training statistics."""
        return {
            "running": self._running,
            "sessions": self.metrics["sessions_started"],
            "total_episodes": self.metrics["total_episodes"],
            "total_steps": self.metrics["total_steps"],
            "avg_reward": self.metrics["avg_reward"],
            "q_table_size": len(self.adversarial_agent.agent.q_table_a)
            if hasattr(self.adversarial_agent, "agent")
            else 0,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics."""
        from rl_core import shared_rl_agent

        stats = shared_rl_agent.get_statistics() if hasattr(shared_rl_agent, 'get_statistics') else {}

        return {
            **self.metrics,
            "rl_stats": stats,
            "evolution_summary": self.file_evolver.get_evolution_summary(),
        }

    def save_metrics(self, file_path: Optional[str] = None) -> None:
        """Save metrics to file."""
        path = file_path or self.config.metrics_file
        metrics = self.get_metrics()
        with open(path, "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        logger.info(f"Metrics saved to {path}")

    def load_metrics(self, file_path: Optional[str] = None) -> None:
        """Load metrics from file."""
        path = file_path or self.config.metrics_file
        if os.path.exists(path):
            with open(path, "r") as f:
                self.metrics.update(json.load(f))
            logger.info(f"Metrics loaded from {path}")

    # ────────────────────────────────────────────────────────────────────────
    #  Integration with Honeypots
    # ────────────────────────────────────────────────────────────────────────

    def get_rl_agent(self):
        """Get the RL agent for use in honeypot services."""
        from rl_core import shared_rl_agent
        return shared_rl_agent

    def get_adversarial_agent(self):
        """Get the adversarial agent."""
        return self.adversarial_agent

    def inject_into_honeypot(self, honeypot_name: str) -> None:
        """
        Inject RL agent into a honeypot service.

        This should be called by honeypot services to get the RL agent.

        Example:
            from adversarial_training import get_training_app
            app = get_training_app()
            rl_agent = app.get_rl_agent()
        """
        logger.info(f"Injecting RL agent into {honeypot_name}")

    # ────────────────────────────────────────────────────────────────────────
    #  Health & Status
    # ────────────────────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, bool]:
        """Check health of all components."""
        return {
            "adversarial_agent": self.adversarial_agent is not None,
            "training_integration": self.training_integration is not None,
            "file_evolver": self.file_evolver is not None,
            "langgraph_system": self.training_system is not None,
        }

    def print_status(self) -> None:
        """Print current status."""
        stats = self.get_current_stats()
        health = self.health_check()

        print("\n" + "=" * 70)
        print("  SIGILHIVE ADVERSARIAL TRAINING - STATUS")
        print("=" * 70)
        print(f"  Status:           {'RUNNING' if stats['running'] else 'IDLE'}")
        print(f"  Sessions:         {stats['sessions']}")
        print(f"  Episodes:         {stats['total_episodes']}")
        print(f"  Steps:            {stats['total_steps']}")
        print(f"  Avg Reward:       {stats['avg_reward']:.3f}")
        print(f"  Q-Table Size:     {stats['q_table_size']}")
        print("\n  Component Health:")
        for component, healthy in health.items():
            status = "✓" if healthy else "✗"
            print(f"    {status} {component}")
        print("=" * 70 + "\n")


# ════════════════════════════════════════════════════════════════════════════
#  Global Instance Management
# ════════════════════════════════════════════════════════════════════════════

_global_training_app: Optional[SigilHiveAdversarialTraining] = None


def initialize_training_app(
    config_path: Optional[str] = None,
) -> SigilHiveAdversarialTraining:
    """Initialize global training application instance."""
    global _global_training_app
    _global_training_app = SigilHiveAdversarialTraining(config_path=config_path)
    return _global_training_app


def get_training_app() -> SigilHiveAdversarialTraining:
    """Get global training application instance."""
    global _global_training_app
    if _global_training_app is None:
        _global_training_app = SigilHiveAdversarialTraining()
    return _global_training_app


# ════════════════════════════════════════════════════════════════════════════
#  CLI Entry Point
# ════════════════════════════════════════════════════════════════════════════

def run_scheduled_training(
    config_path: Optional[str] = None,
    max_episodes: int = 50,
    max_steps_per_episode: int = 100,
) -> None:
    """
    Run training on a scheduled interval.
    
    Attacks occur every X days/hours as configured.
    Useful for continuous adversarial learning.
    """
    import time
    
    app = initialize_training_app(config_path=config_path)
    config = app.config
    
    logger.info(
        f"Starting scheduled training. "
        f"Attack interval: {config.attack_interval_days}d "
        f"{config.attack_interval_hours}h "
        f"({config.interval_seconds}s)"
    )
    
    attack_count = 0
    last_attack_time = 0
    
    try:
        while True:
            current_time = time.time()
            time_since_last = current_time - last_attack_time
            
            # Check if it's time for the next attack
            if time_since_last >= config.interval_seconds or last_attack_time == 0:
                attack_count += 1
                logger.info(
                    f"\n{'='*70}\n"
                    f"SCHEDULED ATTACK #{attack_count} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"{'='*70}"
                )
                
                try:
                    results = app.start_training(
                        mode=ExecutionMode.TRAINING,
                        max_episodes=1,  # Single episode per attack
                        max_steps_per_episode=max_steps_per_episode,
                    )
                    last_attack_time = time.time()
                    
                    logger.info(
                        f"Attack #{attack_count} completed. "
                        f"Next attack in {config.interval_seconds}s"
                    )
                except Exception as e:
                    logger.error(f"Scheduled attack #{attack_count} failed: {e}", exc_info=True)
                    last_attack_time = time.time()  # Reset timer even on failure
            else:
                # Sleep until next attack time
                sleep_time = min(60, config.interval_seconds - time_since_last)
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        logger.info(f"\nScheduled training stopped. Total attacks: {attack_count}")
    except Exception as e:
        logger.error(f"Scheduled training error: {e}", exc_info=True)
        sys.exit(1)


def cli_main() -> None:
    """Command-line entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SigilHive Adversarial Training System"
    )
    parser.add_argument(
        "--mode",
        choices=["training", "evaluation", "testing"],
        default="training",
        help="Execution mode",
    )
    parser.add_argument(
        "--episodes", type=int, default=50, help="Max episodes"
    )
    parser.add_argument(
        "--steps", type=int, default=100, help="Max steps per episode"
    )
    parser.add_argument(
        "--config", type=str, help="Config file path"
    )
    parser.add_argument(
        "--status", action="store_true", help="Print status only"
    )
    parser.add_argument(
        "--schedule", action="store_true", help="Run in scheduled mode (attacks every X days/hours)"
    )
    parser.add_argument(
        "--attack-interval-days", type=int, default=0, help="Attack interval in days (only with --schedule)"
    )
    parser.add_argument(
        "--attack-interval-hours", type=int, default=0, help="Attack interval in hours (only with --schedule)"
    )
    parser.add_argument(
        "--attack-interval-minutes", type=int, default=0, help="Attack interval in minutes (only with --schedule, for testing)"
    )

    args = parser.parse_args()

    # Handle scheduling mode
    if args.schedule:
        # Update environment variables for scheduling config
        if args.attack_interval_days > 0:
            os.environ["ATTACK_INTERVAL_DAYS"] = str(args.attack_interval_days)
        if args.attack_interval_hours > 0:
            os.environ["ATTACK_INTERVAL_HOURS"] = str(args.attack_interval_hours)
        if args.attack_interval_minutes > 0:
            os.environ["ATTACK_INTERVAL_MINUTES"] = str(args.attack_interval_minutes)
        os.environ["ENABLE_SCHEDULING"] = "true"
        
        run_scheduled_training(
            config_path=args.config,
            max_episodes=args.episodes,
            max_steps_per_episode=args.steps,
        )
        return

    # Initialize application
    app = initialize_training_app(config_path=args.config)

    if args.status:
        app.print_status()
        return

    # Start training
    mode = ExecutionMode(args.mode)
    try:
        results = app.start_training(
            mode=mode,
            max_episodes=args.episodes,
            max_steps_per_episode=args.steps,
        )
        print("\n✓ Training complete")
        print(json.dumps(results, indent=2, default=str))
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
