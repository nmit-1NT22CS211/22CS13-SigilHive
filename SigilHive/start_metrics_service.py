#!/usr/bin/env python3
"""
Standalone launcher for SigilHive Metrics Service
Exposes attack metrics to Grafana via Prometheus format and REST API.

Usage:
    python start_metrics_service.py [--port 5000] [--db attack_results.db]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from adversarial_training.metrics_service import create_metrics_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("MetricsService")


def main():
    parser = argparse.ArgumentParser(
        description="SigilHive Metrics Service for Grafana"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("METRICS_PORT", 5000)),
        help="Port to run metrics service on (default: 5000)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("METRICS_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("STORAGE_PATH", "attack_results.db"),
        help="Path to SQLite database (default: attack_results.db)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SigilHive Metrics Service")
    logger.info("=" * 60)
    logger.info(f"Host:     {args.host}")
    logger.info(f"Port:     {args.port}")
    logger.info(f"Database: {args.db}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Endpoints:")
    logger.info(f"  Health:              http://{args.host}:{args.port}/health")
    logger.info(f"  Prometheus metrics:  http://{args.host}:{args.port}/metrics")
    logger.info(f"  Attack results:      http://{args.host}:{args.port}/api/metrics/attacks")
    logger.info(f"  Statistics:          http://{args.host}:{args.port}/api/metrics/statistics")
    logger.info(f"  Success rate:        http://{args.host}:{args.port}/api/metrics/success-rate")
    logger.info(f"  Data extracted:      http://{args.host}:{args.port}/api/metrics/data-extracted")
    logger.info("")
    
    metrics = create_metrics_service(
        storage_path=args.db,
        port=args.port,
        host=args.host,
    )
    
    try:
        metrics.run(debug=args.debug)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        sys.exit(0)


if __name__ == "__main__":
    main()
