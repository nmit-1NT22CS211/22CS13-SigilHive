"""
Main Orchestrator for SigilHive Adversarial Training System
Three operating modes: scheduled, manual, and continuous training loop.
"""

import logging
import os
import signal
import sys
import time
from enum import Enum
from typing import Optional

from .adversarial_agent import AdversarialAgent, Protocol
from .attack_scheduler import AttackConfig, AttackScheduler
from .training_integration import TrainingIntegration

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class OrchestratorMode(str, Enum):
    SCHEDULED = "scheduled"    # Automated attacks on schedule (recommended)
    MANUAL = "manual"          # Interactive CLI for testing
    CONTINUOUS = "continuous"  # Intensive training loop


class Orchestrator:
    """
    Main coordinator for the SigilHive adversarial training system.

    Wires together:
      - AdversarialAgent  (LangGraph + Gemini attacker)
      - AttackScheduler   (timing and campaign management)
      - TrainingIntegration  (RL training loop)

    Usage:
        orchestrator = Orchestrator(gemini_api_key="your-key")
        orchestrator.run(mode=OrchestratorMode.SCHEDULED)
    """

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        target_host: str = "localhost",
        ssh_port: int = 5555,
        http_port: int = 8080,
        db_port: int = 2225,
        file_structure_path: str = "file_structure.py",
        attack_config: Optional[AttackConfig] = None,
        log_level: str = "INFO",
    ):
        logging.getLogger().setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # Resolve API key
        self.gemini_api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.gemini_api_key:
            raise ValueError(
                "Gemini API key required. Pass gemini_api_key= or set GEMINI_API_KEY env var."
            )

        # Build components
        self.agent = AdversarialAgent(
            gemini_api_key=self.gemini_api_key,
            target_host=target_host,
            ssh_port=ssh_port,
            http_port=http_port,
            db_port=db_port,
        )

        self.training = TrainingIntegration(
            agent=self.agent,
            checkpoint_dir="rl_checkpoints",
            session_log_path="training_session.json",
        )

        self.scheduler = AttackScheduler(
            agent=self.agent,
            config=attack_config or AttackConfig(),
            result_callback=self._on_attack_results,
        )

        self._running = False

        # Register SIGINT/SIGTERM handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

        logger.info(
            f"Orchestrator initialized | target={target_host} | "
            f"SSH={ssh_port} | HTTP={http_port} | DB={db_port}"
        )

    def _handle_shutdown(self, signum, frame) -> None:
        logger.info("Shutdown signal received, stopping gracefully...")
        self._running = False
        self.scheduler.stop()
        self.training.end_episode()
        self._print_final_report()
        sys.exit(0)

    def _on_attack_results(self, results) -> None:
        """Callback: called by AttackScheduler after each attack batch."""
        try:
            metrics = self.training.process_attack_batch(results)
            if metrics.get("evolution_applied"):
                logger.info(
                    f"✓ Structure evolved | strategy={metrics['evolution_strategy']} | "
                    f"step={metrics['training_step']}"
                )
        except Exception as exc:
            logger.error(f"Training integration error: {exc}", exc_info=True)

    # ------------------------------------------------------------------ #
    #  Operating modes                                                     #
    # ------------------------------------------------------------------ #

    def run_scheduled(self) -> None:
        """
        SCHEDULED mode: attacks happen automatically on a configurable schedule.
        Recommended for production honeypot training.
        """
        logger.info("=" * 60)
        logger.info("  SigilHive Adversarial Training - SCHEDULED MODE")
        logger.info("=" * 60)
        logger.info("  Attack rate: 2-3/hour per protocol")
        logger.info("  Multi-protocol attacks: 15% probability")
        logger.info("  Campaign bursts: every 6 hours at 3x intensity")
        logger.info("  File structure evolution: enabled (RL-guided)")
        logger.info("=" * 60)

        self._running = True
        self.scheduler.start()

        try:
            while self._running:
                time.sleep(300)  # Status report every 5 minutes
                self._print_status_report()
        except KeyboardInterrupt:
            pass
        finally:
            self.scheduler.stop()
            self.training.end_episode()
            self._print_final_report()

    def run_manual(self) -> None:
        """
        MANUAL mode: interactive CLI for testing individual attacks and evolutions.
        """
        logger.info("=" * 60)
        logger.info("  SigilHive Adversarial Training - MANUAL MODE")
        logger.info("=" * 60)
        print("\nCommands:")
        print("  attack [ssh|http|database]  - Run a single attack")
        print("  status                      - Print current status")
        print("  report                      - Print full training report")
        print("  quit                        - Exit\n")

        protocols = {"ssh": Protocol.SSH, "http": Protocol.HTTP, "database": Protocol.DATABASE}

        while True:
            try:
                cmd = input("sigilhive> ").strip().lower().split()
                if not cmd:
                    continue

                if cmd[0] == "quit":
                    break
                elif cmd[0] == "attack":
                    protocol = protocols.get(cmd[1] if len(cmd) > 1 else "ssh", Protocol.SSH)
                    print(f"\nRunning {protocol.value} attack...")
                    results = self.scheduler.run_manual_attack(protocol.value)
                    metrics = self.training.process_attack_batch(results)
                    print(f"  Results: {len(results)} phases completed")
                    print(f"  Suspicion: {metrics.get('suspicion_level', 0):.2f}")
                    print(f"  TD Error: {metrics.get('td_error', 0):.4f}")
                elif cmd[0] == "status":
                    self._print_status_report()
                elif cmd[0] == "report":
                    self._print_final_report()
                else:
                    print(f"  Unknown command: {cmd[0]}")

            except (KeyboardInterrupt, EOFError):
                break

        self.training.end_episode()
        self._print_final_report()

    def run_continuous(self, max_steps: int = 1000, step_delay: float = 2.0) -> None:
        """
        CONTINUOUS mode: intensive training loop for rapid RL convergence.
        Runs attacks as fast as possible (with configurable delay between steps).
        """
        logger.info("=" * 60)
        logger.info("  SigilHive Adversarial Training - CONTINUOUS MODE")
        logger.info(f"  Max steps: {max_steps} | Step delay: {step_delay}s")
        logger.info("=" * 60)

        self._running = True
        step = 0

        protocols = [Protocol.SSH, Protocol.HTTP, Protocol.DATABASE]

        while self._running and step < max_steps:
            try:
                # Rotate through protocols
                protocol = protocols[step % len(protocols)]
                results = self.scheduler.run_manual_attack(protocol.value)
                metrics = self.training.process_attack_batch(results)

                if step % 10 == 0:
                    logger.info(
                        f"Step {step}/{max_steps} | "
                        f"ε={metrics['epsilon']:.3f} | "
                        f"buffer={metrics['replay_buffer_size']} | "
                        f"reward={metrics['recent_avg_reward']:.2f} | "
                        f"evolutions={metrics['evolution_count']}"
                    )

                step += 1
                time.sleep(step_delay)

            except KeyboardInterrupt:
                logger.info("Continuous mode interrupted by user")
                break
            except Exception as exc:
                logger.error(f"Step {step} error: {exc}", exc_info=True)
                time.sleep(10)

        self.training.end_episode()
        self._print_final_report()

    def run(self, mode: OrchestratorMode = OrchestratorMode.SCHEDULED, **kwargs) -> None:
        """Entry point: dispatch to the selected operating mode."""
        mode_map = {
            OrchestratorMode.SCHEDULED: self.run_scheduled,
            OrchestratorMode.MANUAL: self.run_manual,
            OrchestratorMode.CONTINUOUS: self.run_continuous,
        }
        runner = mode_map.get(mode)
        if runner is None:
            raise ValueError(f"Unknown mode: {mode}")
        runner(**kwargs)

    # ------------------------------------------------------------------ #
    #  Reporting                                                           #
    # ------------------------------------------------------------------ #

    def _print_status_report(self) -> None:
        scheduler_stats = self.scheduler.get_stats()

        print("\n--- STATUS REPORT ---")
        print(f"  Attacks:     {scheduler_stats.get('total_attacks', 0)} total | "
              f"{scheduler_stats.get('success_rate', '0%')} success rate")
        print(f"  Campaigns:   {scheduler_stats.get('total_campaigns', 0)}")
        print(f"  RL Epsilon:  {self.training.rl_agent.epsilon:.4f}")
        print(f"  Buffer size: {len(self.training.replay_buffer)}")

    def _print_final_report(self) -> None:
        report = self.training.get_training_report()
        print("\n" + "=" * 60)
        print("  FINAL TRAINING REPORT")
        print("=" * 60)
        
        for key, value in report.items():
            if isinstance(value, dict):
                print(f"\n  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey:<30} {subvalue}")
            else:
                print(f"  {key:<35} {value}")
        
        print("=" * 60)


# ------------------------------------------------------------------ #
#  CLI entry point                                                     #
# ------------------------------------------------------------------ #

def main():
    """Command-line entry point for the orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(description="SigilHive Adversarial Training System")
    parser.add_argument(
        "--mode",
        choices=["scheduled", "manual", "continuous"],
        default="scheduled",
        help="Operating mode (default: scheduled)",
    )
    parser.add_argument("--host", default="localhost", help="Target host")
    parser.add_argument("--ssh-port", type=int, default=5555)
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--db-port", type=int, default=2225)
    parser.add_argument(
        "--file-structure",
        default="file_structure.py",
        help="Path to file_structure.py",
    )
    parser.add_argument("--max-steps", type=int, default=1000, help="Max steps (continuous mode)")
    parser.add_argument("--step-delay", type=float, default=2.0, help="Delay between steps (continuous mode)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    orchestrator = Orchestrator(
        target_host=args.host,
        ssh_port=args.ssh_port,
        http_port=args.http_port,
        db_port=args.db_port,
        file_structure_path=args.file_structure,
        log_level=args.log_level,
    )

    mode = OrchestratorMode(args.mode)
    kwargs = {}
    if mode == OrchestratorMode.CONTINUOUS:
        kwargs = {"max_steps": args.max_steps, "step_delay": args.step_delay}

    orchestrator.run(mode=mode, **kwargs)


if __name__ == "__main__":
    main()