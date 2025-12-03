#!/usr/bin/env python3
"""Deploy SigilHive to Grafana via MCP"""
import json

GRAFANA_API_KEY = "glc_eyJvIjoiMTU5OTMxMSIsIm4iOiJzdGFjay0xNDQ5MDczLWludGVncmF0aW9uLWdyYWZhbmFfbWNwIiwiayI6Img1SlhGdzYxZG84cjY4SUtBRjlpMmoyOSIsIm0iOnsiciI6InByb2QtYXAtc291dGgtMSJ9fQ=="
LOKI_URL = "https://logs-prod-028.grafana.net"
LOKI_USERNAME = "1406866"
LOKI_PASSWORD = "glc_eyJvIjoiMTU5OTMxMSIsIm4iOiJzdGFjay0xNDQ5MDczLWludGVncmF0aW9uLWdyYWZhbmFfbWNwIiwiayI6Img1SlhGdzYxZG84cjY4SUtBRjlpMmoyOSIsIm0iOnsiciI6InByb2QtYXAtc291dGgtMSJ9fQ=="

print("""
SIGILHIVE GRAFANA MCP DEPLOYMENT PLAN
=====================================

Loading configurations...""")

with open('grafana_dashboard.json') as f:
    dashboard_config = json.load(f)
with open('grafana_alerts.json') as f:
    alerts_config = json.load(f)
with open('grafana_annotations.json') as f:
    annotations_config = json.load(f)
with open('grafana_incidents.json') as f:
    incidents_config = json.load(f)

print("OK - Configurations loaded")
print()

print("STEP 1: QUERY LOKI LOGS TO VERIFY DATA")
print("=" * 50)
print("MCP Call: query_loki_logs(query='{job=\"honeypot\"}')")
print("MCP Call: query_loki_logs(query='{job=\"honeypot\", service=\"http\"}')")
print("MCP Call: query_loki_logs(query='{job=\"honeypot\", service=\"database\"}')")
print("MCP Call: query_loki_logs(query='{job=\"honeypot\", service=\"ssh\"}')")
print()

print("STEP 2: LIST EXISTING ALERT RULES")
print("=" * 50)
print("MCP Call: list_alert_rules()")
print()

print("STEP 3: DEPLOY DASHBOARD")
print("=" * 50)
print(f"Dashboard: {dashboard_config['dashboard']['title']}")
print(f"Panels: {len(dashboard_config['dashboard']['panels'])}")
print(f"Tags: {', '.join(dashboard_config['dashboard']['tags'])}")
print("MCP Call: update_dashboard(dashboard=...)")
print()

print("STEP 4: CREATE ALERT RULES")
print("=" * 50)
for i, alert in enumerate(alerts_config['alerts'], 1):
    print(f"{i}. {alert['title']}")
    print(f"   Condition: {alert['condition']}")
    print(f"   Severity: {alert['severity']}")
print()

print("STEP 5: CREATE ANNOTATIONS")
print("=" * 50)
for i, ann in enumerate(annotations_config['annotations'], 1):
    print(f"{i}. {ann['text']}")
    print(f"   Tags: {', '.join(ann['tags'])}")
print()

print("STEP 6: CREATE INCIDENTS")
print("=" * 50)
for i, incident in enumerate(incidents_config['incidents'], 1):
    print(f"{i}. {incident['title']}")
    print(f"   Severity: {incident['severity']}")
    print(f"   Description: {incident['description']}")
print()

print("=" * 70)
print("DEPLOYMENT SUMMARY")
print("=" * 70)
print(f"Dashboard: 1 with {len(dashboard_config['dashboard']['panels'])} panels")
print(f"Alert Rules: {len(alerts_config['alerts'])}")
print(f"Annotations: {len(annotations_config['annotations'])}")
print(f"Incidents: {len(incidents_config['incidents'])}")
print()

print("CONFIGURATION READY FOR MCP DEPLOYMENT")
print("=" * 70)
print("Files created:")
print("  - grafana_dashboard.json")
print("  - grafana_alerts.json")
print("  - grafana_annotations.json")
print("  - grafana_incidents.json")
print()

print("Next: Use Grafana MCP tools to execute deployment")
print()

print("GRAFANA CLOUD ENDPOINTS")
print("=" * 70)
print("Dashboard: https://sigilhive.grafana.net/d/sigilhive")
print("Alerts: https://sigilhive.grafana.net/alerting/list")
print("Incidents: https://sigilhive.grafana.net/incidentevents")
print("Loki Explorer: https://sigilhive.grafana.net/explore?datasource=Loki")
