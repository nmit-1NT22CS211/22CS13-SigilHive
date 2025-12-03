#!/usr/bin/env python3
"""
SigilHive Grafana Dashboard Deployment Script
Deploys comprehensive monitoring dashboard and alert rules to Grafana Cloud
"""

import os
import json
import requests
import sys
from typing import Dict, Any

class GrafanaDeployer:
    def __init__(self):
        # Load Grafana credentials from environment
        self.grafana_url = os.getenv("GRAFANA_URL", "https://sigilhive.grafana.net")
        self.grafana_token = os.getenv("GRAFANA_DOCKER_API", "")
        self.org_id = os.getenv("GRAFANA_ORG_ID", "1")
        
        if not self.grafana_token:
            print("❌ ERROR: GRAFANA_DOCKER_API environment variable not set")
            sys.exit(1)
        
        self.headers = {
            "Authorization": f"Bearer {self.grafana_token}",
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> bool:
        """Test connection to Grafana API"""
        try:
            response = requests.get(
                f"{self.grafana_url}/api/user",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                user = response.json()
                print(f"✅ Connected to Grafana: {user.get('login', 'Unknown')}")
                return True
            else:
                print(f"❌ Grafana API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            return False
    
    def get_or_create_datasource(self) -> str:
        """Get or create Loki datasource"""
        try:
            # Check if Loki datasource exists
            response = requests.get(
                f"{self.grafana_url}/api/datasources",
                headers=self.headers,
                timeout=5
            )
            
            for ds in response.json():
                if ds.get("type") == "loki":
                    print(f"✅ Found existing Loki datasource: {ds['name']}")
                    return str(ds["id"])
            
            # Create Loki datasource if not found
            print("📊 Creating Loki datasource...")
            loki_url = os.getenv("LOKI_URL", "https://logs-prod-028.grafana.net/loki/api/v1")
            loki_user = os.getenv("LOKI_USERNAME", "1406866")
            loki_pass = os.getenv("LOKI_PASSWORD", "")
            
            datasource_config = {
                "name": "SigilHive Loki",
                "type": "loki",
                "url": loki_url,
                "access": "proxy",
                "isDefault": False,
                "basicAuth": True,
                "basicAuthUser": loki_user,
                "secureJsonData": {
                    "basicAuthPassword": loki_pass
                },
                "orgId": int(self.org_id),
                "jsonData": {
                    "maxLines": 1000,
                    "derivedFields": []
                }
            }
            
            response = requests.post(
                f"{self.grafana_url}/api/datasources",
                json=datasource_config,
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                ds_id = response.json().get("id")
                print(f"✅ Created Loki datasource with ID: {ds_id}")
                return str(ds_id)
            else:
                print(f"❌ Failed to create datasource: {response.text}")
                return None
        
        except Exception as e:
            print(f"❌ Error managing datasource: {str(e)}")
            return None
    
    def deploy_dashboard(self, dashboard_file: str) -> bool:
        """Deploy dashboard to Grafana"""
        try:
            with open(dashboard_file, 'r') as f:
                dashboard_config = json.load(f)
            
            print(f"📊 Deploying dashboard: {dashboard_config['dashboard']['title']}")
            
            # Prepare dashboard payload
            payload = {
                "dashboard": dashboard_config.get("dashboard", dashboard_config),
                "overwrite": True,
                "message": "SigilHive Security Operations Center - Auto Deployment"
            }
            
            response = requests.post(
                f"{self.grafana_url}/api/dashboards/db",
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                print(f"✅ Dashboard deployed successfully!")
                print(f"   ID: {result.get('id')}")
                print(f"   URL: {result.get('url')}")
                return True
            else:
                print(f"❌ Dashboard deployment failed: {response.text}")
                return False
        
        except Exception as e:
            print(f"❌ Error deploying dashboard: {str(e)}")
            return False
    
    def deploy_alert_rules(self, alerts_file: str) -> bool:
        """Deploy alert rules to Grafana"""
        try:
            with open(alerts_file, 'r') as f:
                alerts_config = json.load(f)
            
            alerts = alerts_config.get("alerts", [])
            print(f"🚨 Deploying {len(alerts)} alert rules...")
            
            deployed_count = 0
            for alert in alerts:
                alert_payload = {
                    "uid": alert.get("id"),
                    "title": alert.get("title"),
                    "condition": alert.get("condition"),
                    "data": alert.get("data"),
                    "noDataState": alert.get("noDataState", "NoData"),
                    "execErrState": alert.get("execErrState", "Alerting"),
                    "for": alert.get("for", "1m"),
                    "annotations": alert.get("annotations", {}),
                    "labels": alert.get("labels", {}),
                    "orgId": int(self.org_id)
                }
                
                response = requests.post(
                    f"{self.grafana_url}/api/v1/rules",
                    json=alert_payload,
                    headers=self.headers,
                    timeout=5
                )
                
                if response.status_code in [200, 201, 202]:
                    print(f"  ✅ {alert.get('title')}")
                    deployed_count += 1
                else:
                    print(f"  ❌ {alert.get('title')}: {response.status_code}")
            
            print(f"✅ Deployed {deployed_count}/{len(alerts)} alert rules")
            return deployed_count == len(alerts)
        
        except Exception as e:
            print(f"❌ Error deploying alerts: {str(e)}")
            return False
    
    def deploy(self):
        """Execute full deployment"""
        print("\n" + "="*60)
        print("🚀 SigilHive Grafana Deployment")
        print("="*60 + "\n")
        
        # Step 1: Test connection
        print("[1/4] Testing Grafana connection...")
        if not self.test_connection():
            print("\n❌ Deployment failed: Cannot connect to Grafana")
            return False
        
        # Step 2: Setup datasources
        print("\n[2/4] Setting up Loki datasource...")
        ds_id = self.get_or_create_datasource()
        if not ds_id:
            print("\n⚠️  Warning: Datasource setup failed, continuing...")
        
        # Step 3: Deploy dashboard
        print("\n[3/4] Deploying comprehensive dashboard...")
        dashboard_file = "grafana_comprehensive_dashboard.json"
        if os.path.exists(dashboard_file):
            if not self.deploy_dashboard(dashboard_file):
                print("\n❌ Dashboard deployment failed")
                return False
        else:
            print(f"⚠️  Dashboard file not found: {dashboard_file}")
        
        # Step 4: Deploy alerts
        print("\n[4/4] Deploying alert rules...")
        alerts_file = "grafana_alert_rules.json"
        if os.path.exists(alerts_file):
            if not self.deploy_alert_rules(alerts_file):
                print("\n⚠️  Some alerts failed to deploy")
        else:
            print(f"⚠️  Alerts file not found: {alerts_file}")
        
        print("\n" + "="*60)
        print("✅ Deployment Complete!")
        print("="*60)
        print(f"\n📊 Access your dashboard at:")
        print(f"   {self.grafana_url}/dashboards")
        print(f"\n🚨 Manage alerts at:")
        print(f"   {self.grafana_url}/alerting/list")
        print("\n")
        
        return True

def main():
    deployer = GrafanaDeployer()
    success = deployer.deploy()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
