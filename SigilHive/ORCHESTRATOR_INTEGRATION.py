"""
Example: How to integrate EnhancedAdversarialAgent into Orchestrator
Copy this to replace the agent initialization in orchestrator.py

Replace this section in orchestrator.py __init__:
    self.agent = AdversarialAgent(
        gemini_api_key=self.gemini_api_key,
        target_host=target_host,
        ssh_port=ssh_port,
        http_port=http_port,
        db_port=db_port,
    )

With:
    self.agent = self._create_agent(
        gemini_api_key=self.gemini_api_key,
        target_host=target_host,
        ssh_port=ssh_port,
        http_port=http_port,
        db_port=db_port,
    )

Then add this method to the Orchestrator class:
"""

def _create_agent(
    self,
    gemini_api_key: str,
    target_host: str,
    ssh_port: int,
    http_port: int,
    db_port: int,
):
    """Factory method to create agent with real attacks and storage integration."""
    try:
        from .enhanced_agent import EnhancedAdversarialAgent
        from .result_storage import AttackResultStorage
        from .metrics_service import create_metrics_service
        
        # Initialize storage
        storage = AttackResultStorage()
        
        # Create enhanced agent with real attacks
        agent = EnhancedAdversarialAgent(
            gemini_api_key=gemini_api_key,
            target_host=target_host,
            ssh_port=ssh_port,
            http_port=http_port,
            db_port=db_port,
            storage=storage,
        )
        
        # Start metrics service in background (optional)
        logger.info("Starting metrics service on port 5000...")
        import threading
        metrics = create_metrics_service(storage_path="attack_results.db", port=5000)
        metrics_thread = threading.Thread(target=metrics.run, kwargs={"debug": False}, daemon=True)
        metrics_thread.start()
        
        return agent
        
    except ImportError as e:
        logger.warning(f"Failed to import enhanced agent components: {e}")
        logger.warning("Falling back to standard AdversarialAgent (simulated attacks)")
        
        # Fallback to original agent
        from .adversarial_agent import AdversarialAgent
        return AdversarialAgent(
            gemini_api_key=gemini_api_key,
            target_host=target_host,
            ssh_port=ssh_port,
            http_port=http_port,
            db_port=db_port,
        )
