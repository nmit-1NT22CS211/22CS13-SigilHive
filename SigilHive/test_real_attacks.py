#!/usr/bin/env python3
"""
Test script to verify real attack implementations work.
Run this to test SSH, HTTP, and Database attacks before starting full training.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adversarial_training.real_attacks import SSHAttacker, HTTPAttacker, DatabaseAttacker
from adversarial_training.result_storage import AttackResultStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("AttackTest")


def test_ssh(host: str, port: int):
    """Test SSH attack implementations."""
    logger.info("=" * 60)
    logger.info(f"Testing SSH attacks on {host}:{port}")
    logger.info("=" * 60)
    
    attacker = SSHAttacker(host, port)
    storage = AttackResultStorage()
    
    # Test reconnaissance
    logger.info("\n[SSH Recon] Attempting reconnaissance...")
    try:
        success, responses, metrics = attacker.attack_recon()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        for resp in responses[:2]:
            logger.info(f"    - {resp[:80]}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Duration: {m.duration:.2f}s")
            logger.info(f"  Suspicion delta: {m.suspicion_level}")
    except Exception as e:
        logger.error(f"  Failed: {e}")
    
    # Test exploitation
    logger.info("\n[SSH Exploit] Attempting exploitation...")
    try:
        success, responses, metrics = attacker.attack_exploit()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Suspicion delta: {m.suspicion_level}")
    except Exception as e:
        logger.error(f"  Failed: {e}")


def test_http(host: str, port: int):
    """Test HTTP attack implementations."""
    logger.info("\n" + "=" * 60)
    logger.info(f"Testing HTTP attacks on {host}:{port}")
    logger.info("=" * 60)
    
    attacker = HTTPAttacker(host, port)
    
    # Test reconnaissance
    logger.info("\n[HTTP Recon] Attempting endpoint enumeration...")
    try:
        success, responses, metrics = attacker.attack_recon()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        for resp in responses[:3]:
            logger.info(f"    - {resp}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Duration: {m.duration:.2f}s")
    except Exception as e:
        logger.error(f"  Failed: {e}")
    
    # Test exploitation
    logger.info("\n[HTTP Exploit] Attempting exploits...")
    try:
        success, responses, metrics = attacker.attack_exploit()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Suspicion delta: {m.suspicion_level}")
    except Exception as e:
        logger.error(f"  Failed: {e}")


def test_database(host: str, port: int):
    """Test Database attack implementations."""
    logger.info("\n" + "=" * 60)
    logger.info(f"Testing Database attacks on {host}:{port}")
    logger.info("=" * 60)
    
    attacker = DatabaseAttacker(host, port)
    
    # Test reconnaissance
    logger.info("\n[DB Recon] Attempting schema enumeration...")
    try:
        success, responses, metrics = attacker.attack_recon()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        for resp in responses[:2]:
            logger.info(f"    - {str(resp)[:80]}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Duration: {m.duration:.3f}s")
    except Exception as e:
        logger.error(f"  Failed: {e}")
    
    # Test exploitation
    logger.info("\n[DB Exploit] Attempting data extraction...")
    try:
        success, responses, metrics = attacker.attack_exploit()
        logger.info(f"  Success: {success}")
        logger.info(f"  Responses: {len(responses)}")
        
        if metrics:
            m = metrics[0]
            logger.info(f"  Data extracted: {m.data_extracted} bytes")
            logger.info(f"  Suspicion delta: {m.suspicion_level}")
    except Exception as e:
        logger.error(f"  Failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Test SigilHive real attack implementations"
    )
    parser.add_argument("--host", default="localhost", help="Target host")
    parser.add_argument("--ssh-port", type=int, default=5555, help="SSH port")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP port")
    parser.add_argument("--db-port", type=int, default=2225, help="Database port")
    parser.add_argument(
        "--protocol",
        choices=["ssh", "http", "database", "all"],
        default="all",
        help="Which attacks to test",
    )
    
    args = parser.parse_args()
    
    logger.info("SigilHive Attack Test Suite")
    logger.info(f"Target: {args.host}")
    logger.info("")
    
    try:
        if args.protocol in ["all", "ssh"]:
            test_ssh(args.host, args.ssh_port)
        
        if args.protocol in ["all", "http"]:
            test_http(args.host, args.http_port)
        
        if args.protocol in ["all", "database"]:
            test_database(args.host, args.db_port)
        
        logger.info("\n" + "=" * 60)
        logger.info("Test complete!")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.warning("Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
