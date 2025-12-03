"""
Grafana Dashboard Provisioning Configuration

This module provides the necessary configurations and dashboards for monitoring
SigilHive honeypot activities in Grafana Cloud.
"""

GRAFANA_DASHBOARD = {
    "dashboard": {
        "title": "SigilHive Security Monitoring Dashboard",
        "description": "Real-time monitoring of honeypot attacks and security events",
        "tags": ["honeypot", "security", "sigilhive"],
        "timezone": "browser",
        "panels": [
            {
                "id": 1,
                "title": "Attack Activity (Last 24h)",
                "type": "graph",
                "targets": [
                    {
                        "expr": "sigilhive_ssh_attacks",
                        "legendFormat": "SSH Attacks",
                        "refId": "A",
                    },
                    {
                        "expr": "sigilhive_http_attacks",
                        "legendFormat": "HTTP Attacks",
                        "refId": "B",
                    },
                    {
                        "expr": "sigilhive_database_attacks",
                        "legendFormat": "Database Attacks",
                        "refId": "C",
                    },
                ],
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
            },
            {
                "id": 2,
                "title": "Threat Level Distribution",
                "type": "piechart",
                "targets": [
                    {
                        "expr": "sum(rate(sigilhive_ssh_attacks[5m]))",
                        "legendFormat": "SSH",
                        "refId": "A",
                    },
                    {
                        "expr": "sum(rate(sigilhive_http_attacks[5m]))",
                        "legendFormat": "HTTP",
                        "refId": "B",
                    },
                    {
                        "expr": "sum(rate(sigilhive_database_attacks[5m]))",
                        "legendFormat": "Database",
                        "refId": "C",
                    },
                ],
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
            },
            {
                "id": 3,
                "title": "SQL Injection Attempts",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sigilhive_sql_injection_attempts",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
            },
            {
                "id": 4,
                "title": "Privilege Escalation Attempts",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sigilhive_privilege_escalation_attempts",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
            },
            {
                "id": 5,
                "title": "Active Sessions",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sigilhive_total_sessions",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 8},
            },
            {
                "id": 6,
                "title": "Suspicious Commands Detected",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sigilhive_suspicious_commands",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 4, "w": 6, "x": 18, "y": 8},
            },
            {
                "id": 7,
                "title": "Security Alerts (Loki)",
                "type": "logs",
                "targets": [
                    {
                        "expr": '{job="honeypot-alerts"}',
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 8, "w": 24, "x": 0, "y": 12},
            },
            {
                "id": 8,
                "title": "Reconnaissance Activities",
                "type": "stat",
                "targets": [
                    {
                        "expr": "sigilhive_reconnaissance_activities",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 20},
            },
            {
                "id": 9,
                "title": "Attack Rate (per minute)",
                "type": "graph",
                "targets": [
                    {
                        "expr": "rate(sigilhive_ssh_attacks[1m]) + rate(sigilhive_http_attacks[1m]) + rate(sigilhive_database_attacks[1m])",
                        "legendFormat": "Total Attack Rate",
                        "refId": "A",
                    }
                ],
                "gridPos": {"h": 8, "w": 12, "x": 6, "y": 20},
            },
        ],
    }
}

ALERT_RULES = {
    "groups": [
        {
            "name": "sigilhive_alerts",
            "interval": "1m",
            "rules": [
                {
                    "alert": "HighSQLInjectionAttempts",
                    "expr": "sigilhive_sql_injection_attempts > 10",
                    "for": "5m",
                    "labels": {
                        "severity": "critical",
                        "service": "database"
                    },
                    "annotations": {
                        "summary": "High SQL Injection attempts detected",
                        "description": "{{ $value }} SQL injection attempts in the last 5 minutes"
                    }
                },
                {
                    "alert": "PrivilegeEscalationAttempt",
                    "expr": "sigilhive_privilege_escalation_attempts > 0",
                    "for": "1m",
                    "labels": {
                        "severity": "critical",
                        "service": "ssh"
                    },
                    "annotations": {
                        "summary": "Privilege escalation attempt detected",
                        "description": "Privilege escalation attempt detected: {{ $value }}"
                    }
                },
                {
                    "alert": "HighSuspiciousCommandsDetected",
                    "expr": "sigilhive_suspicious_commands > 20",
                    "for": "5m",
                    "labels": {
                        "severity": "high",
                        "service": "ssh"
                    },
                    "annotations": {
                        "summary": "High number of suspicious commands",
                        "description": "{{ $value }} suspicious commands detected"
                    }
                },
                {
                    "alert": "HighHTTPAttackRate",
                    "expr": "rate(sigilhive_http_attacks[5m]) > 10",
                    "for": "2m",
                    "labels": {
                        "severity": "high",
                        "service": "http"
                    },
                    "annotations": {
                        "summary": "High HTTP attack rate",
                        "description": "HTTP attack rate: {{ $value }} per second"
                    }
                },
                {
                    "alert": "UnusualReconnaissanceActivity",
                    "expr": "sigilhive_reconnaissance_activities > 15",
                    "for": "3m",
                    "labels": {
                        "severity": "medium",
                        "service": "all"
                    },
                    "annotations": {
                        "summary": "Unusual reconnaissance activity detected",
                        "description": "{{ $value }} reconnaissance activities detected"
                    }
                },
            ]
        }
    ]
}

# Loki alert query examples
LOKI_QUERIES = {
    "critical_alerts": '{job="honeypot-alerts", severity="CRITICAL"}',
    "ssh_events": '{job="honeypot", service="ssh"}',
    "http_events": '{job="honeypot", service="http"}',
    "database_events": '{job="honeypot", service="database"}',
    "sql_injection": '{job="honeypot", event_type=~".*sql.*"}',
    "privilege_escalation": '{job="honeypot", event_type="privilege_escalation"}',
}
