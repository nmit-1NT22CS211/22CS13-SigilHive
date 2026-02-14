"""
Metrics Service for Grafana Integration
Exposes attack metrics via HTTP for Grafana to scrape.
"""

import json
import logging
from flask import Flask, jsonify, request
from pathlib import Path
from typing import Optional

from .result_storage import AttackResultStorage

logger = logging.getLogger(__name__)


class MetricsService:
    """Flask service for exposing attack metrics."""

    def __init__(self, storage: AttackResultStorage, port: int = 5000, host: str = "0.0.0.0"):
        self.storage = storage
        self.port = port
        self.host = host
        self.app = self._build_app()

    def _build_app(self) -> Flask:
        """Build Flask application."""
        app = Flask("SigilHive Metrics")

        @app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "service": "SigilHive Metrics"})

        @app.route("/metrics", methods=["GET"])
        def metrics_prometheus():
            """Prometheus-format metrics endpoint."""
            session_id = request.args.get("session_id")
            prometheus_text = self.storage.export_metrics_prometheus(session_id)
            return prometheus_text, 200, {"Content-Type": "text/plain; charset=utf-8"}

        @app.route("/api/metrics/attacks", methods=["GET"])
        def api_attacks():
            """JSON API for attack results."""
            session_id = request.args.get("session_id")
            protocol = request.args.get("protocol")
            limit = int(request.args.get("limit", 100))
            offset = int(request.args.get("offset", 0))

            results = self.storage.get_attack_results(
                session_id=session_id,
                protocol=protocol,
                limit=limit,
                offset=offset,
            )
            return jsonify({"attacks": results, "count": len(results)})

        @app.route("/api/metrics/statistics", methods=["GET"])
        def api_statistics():
            """Aggregate statistics endpoint."""
            session_id = request.args.get("session_id")
            stats = self.storage.get_attack_statistics(session_id)
            return jsonify(stats)

        @app.route("/api/metrics/success-rate", methods=["GET"])
        def api_success_rate():
            """Success rate over time."""
            session_id = request.args.get("session_id")
            window_size = int(request.args.get("window", 10))

            attacks = self.storage.get_attack_results(session_id=session_id, limit=10000)
            
            windows = []
            for i in range(0, len(attacks), window_size):
                window = attacks[i : i + window_size]
                if window:
                    success_count = sum(1 for a in window if a["success"])
                    rate = success_count / len(window)
                    avg_time = sum(a["timestamp"] for a in window) / len(window)
                    
                    windows.append({
                        "timestamp": int(avg_time),
                        "success_rate": rate,
                        "count": len(window),
                        "successful": success_count,
                    })
            
            return jsonify({"windows": windows})

        @app.route("/api/metrics/data-extracted", methods=["GET"])
        def api_data_extracted():
            """Total data extracted over time."""
            session_id = request.args.get("session_id")
            timeframe = request.args.get("timeframe", "1h")  # 1h, 6h, 24h

            import time
            import re

            # Parse timeframe
            match = re.match(r"(\d+)([hmd])", timeframe)
            if not match:
                return jsonify({"error": "Invalid timeframe format"}), 400

            amount = int(match.group(1))
            unit = match.group(2)
            seconds_map = {"h": 3600, "d": 86400, "m": 60}
            seconds = amount * seconds_map.get(unit, 3600)

            cutoff = time.time() - seconds
            attacks = self.storage.get_attack_results(session_id=session_id, limit=10000)

            filtered = [a for a in attacks if a["timestamp"] >= cutoff]

            total_by_protocol = {}
            for attack in filtered:
                proto = attack["protocol"]
                if proto not in total_by_protocol:
                    total_by_protocol[proto] = 0
                total_by_protocol[proto] += attack["data_extracted"]

            return jsonify({
                "timeframe": timeframe,
                "total_data": sum(total_by_protocol.values()),
                "by_protocol": total_by_protocol,
            })

        @app.route("/api/metrics/suspicion-trend", methods=["GET"])
        def api_suspicion_trend():
            """Suspicion level trend over time."""
            session_id = request.args.get("session_id")
            attacks = self.storage.get_attack_results(session_id=session_id, limit=1000)

            trend = [
                {
                    "timestamp": int(a["timestamp"]),
                    "suspicion": a["suspicion_level"],
                    "protocol": a["protocol"],
                }
                for a in attacks
            ]

            return jsonify({"trend": trend})

        @app.route("/api/metrics/protocol-breakdown", methods=["GET"])
        def api_protocol_breakdown():
            """Attack counts by protocol."""
            session_id = request.args.get("session_id")
            stats = self.storage.get_attack_statistics(session_id)

            breakdown = {
                proto: data.get("count", 0)
                for proto, data in stats.get("by_protocol", {}).items()
            }

            return jsonify({"protocol_breakdown": breakdown})

        return app

    def run(self, debug: bool = False) -> None:
        """Start the metrics service."""
        logger.info(f"Starting metrics service on {self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug)


def create_metrics_service(
    storage_path: str = "attack_results.db",
    port: int = 5000,
    host: str = "0.0.0.0",
) -> MetricsService:
    """Factory function for creating metrics service."""
    storage = AttackResultStorage(db_path=storage_path)
    return MetricsService(storage=storage, port=port, host=host)


if __name__ == "__main__":
    import os
    
    port = int(os.environ.get("METRICS_PORT", 5000))
    host = os.environ.get("METRICS_HOST", "0.0.0.0")
    storage_path = os.environ.get("STORAGE_PATH", "attack_results.db")
    
    metrics = create_metrics_service(storage_path, port, host)
    metrics.run(debug=False)
