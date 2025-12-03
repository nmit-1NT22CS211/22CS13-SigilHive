# SigilHive Grafana MCP Tool Calls - Ready for Execution

## 🎯 Complete MCP Command Sequence

### Step 1: Query Loki to Verify Data Availability
```
query_loki_logs(query='{job="honeypot"}')
```
Expected: Returns 450+ log entries from attack events

---

### Step 2: Get Loki Label Information
```
list_loki_label_names()
list_loki_label_values(label_name='service')
list_loki_label_values(label_name='event_type')
```
Expected: Shows available labels and values for filtering

---

### Step 3: Deploy the Monitoring Dashboard

Load the configuration from `grafana_dashboard.json` and execute:

```
update_dashboard(
  dashboard={
    "title": "SigilHive Honeypot Monitoring",
    "tags": ["honeypot", "security", "sigilhive"],
    "timezone": "browser",
    "schemaVersion": 38,
    "version": 0,
    "refresh": "30s",
    "time": {
      "from": "now-6h",
      "to": "now"
    },
    "panels": [
      {
        "id": 1,
        "title": "🔴 Attack Events (Loki)",
        "type": "logs",
        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
        "targets": [
          {"expr": "{job=\"honeypot\"}", "refId": "A"}
        ]
      },
      {
        "id": 2,
        "title": "📊 HTTP Attack Activity",
        "type": "logs",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 6},
        "targets": [
          {"expr": "{job=\"honeypot\", service=\"http\"}", "refId": "A"}
        ]
      },
      {
        "id": 3,
        "title": "🗄️ Database Attack Activity",
        "type": "logs",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 6},
        "targets": [
          {"expr": "{job=\"honeypot\", service=\"database\"}", "refId": "A"}
        ]
      },
      {
        "id": 4,
        "title": "🔐 SSH Activity",
        "type": "logs",
        "gridPos": {"x": 0, "y": 14, "w": 24, "h": 6},
        "targets": [
          {"expr": "{job=\"honeypot\", service=\"ssh\"}", "refId": "A"}
        ]
      }
    ]
  }
)
```

Expected: Dashboard "SigilHive Honeypot Monitoring" created with 4 panels

---

### Step 4: Create Alert Rule #1 - SQL Injection Detection

```
create_alert_rule(
  rule_name="🚨 SQL Injection Detected",
  condition="{job=\"honeypot\", service=\"database\"} |= \"UNION\" or \"DROP\" or \"SELECT\"",
  severity="CRITICAL",
  duration="1m",
  annotations={
    "summary": "SQL Injection spike detected",
    "description": "{{ $value }} SQL injection attempts detected"
  }
)
```

Expected: CRITICAL alert rule created for database attacks

---

### Step 5: Create Alert Rule #2 - Directory Traversal Attempts

```
create_alert_rule(
  rule_name="⚠️ Directory Traversal Attempt",
  condition="{job=\"honeypot\", service=\"http\"} |= \"../\" or \"..\\\\\"",
  severity="HIGH",
  duration="2m",
  annotations={
    "summary": "Directory traversal detected",
    "description": "Path traversal attempt detected: {{ $value }}"
  }
)
```

Expected: HIGH alert rule created for path traversal attacks

---

### Step 6: Create Alert Rule #3 - Admin Access Attempts

```
create_alert_rule(
  rule_name="🔓 Admin Access Attempt",
  condition="{job=\"honeypot\", service=\"http\"} |= \"admin\"",
  severity="HIGH",
  duration="1m",
  annotations={
    "summary": "Admin access attempt detected",
    "description": "Unauthorized admin endpoint access: {{ $value }}"
  }
)
```

Expected: HIGH alert rule created for unauthorized admin access

---

### Step 7: Create Alert Rule #4 - Reconnaissance Activity

```
create_alert_rule(
  rule_name="🔍 Reconnaissance Activity",
  condition="{job=\"honeypot\"} |= \"reconnaissance\" or \"scanning\" or \"probe\"",
  severity="MEDIUM",
  duration="5m",
  annotations={
    "summary": "Reconnaissance activity detected",
    "description": "{{ $value }} reconnaissance activities"
  }
)
```

Expected: MEDIUM alert rule created for reconnaissance/scanning

---

### Step 8: Create Annotation #1 - High HTTP Activity

```
create_annotation(
  text="High HTTP Attack Activity Detected",
  tags=["http", "attack", "high-rate"],
  dashboard="sigilhive",
  time_start="now-30m",
  time_end="now"
)
```

Expected: Annotation created marking HTTP attack period

---

### Step 9: Create Annotation #2 - SQL Injection Block

```
create_annotation(
  text="SQL Injection Attempt Blocked",
  tags=["database", "sql-injection", "critical"],
  dashboard="sigilhive",
  time_start="now-1h",
  time_end="now"
)
```

Expected: Annotation created marking SQL injection detection

---

### Step 10: Create Annotation #3 - Directory Traversal Events

```
create_annotation(
  text="Directory Traversal Attack Detected",
  tags=["http", "traversal", "security"],
  dashboard="sigilhive",
  time_start="now-30m",
  time_end="now"
)
```

Expected: Annotation created marking traversal attacks

---

### Step 11: Create Incident #1 - SQL Injection Wave

```
create_incident(
  title="SQL Injection Attack Wave",
  description="Multiple SQL injection attempts detected targeting database honeypot. UNION SELECT and DROP TABLE commands observed.",
  severity="CRITICAL",
  status="triggered",
  labels=["sql-injection", "database", "security-threat"]
)
```

Expected: CRITICAL incident created for security team response

---

### Step 12: Create Incident #2 - Directory Traversal Campaign

```
create_incident(
  title="Directory Traversal Reconnaissance",
  description="Series of directory traversal attempts on HTTP honeypot. /../ and ..\\\ patterns detected. Possible pre-attack reconnaissance.",
  severity="HIGH",
  status="triggered",
  labels=["traversal", "http", "reconnaissance"]
)
```

Expected: HIGH incident created for security team response

---

## ✅ Verification Queries

After deployment, verify everything is working:

### Query 1: Count all events in past hour
```
count(count_over_time({job="honeypot"}[1h]))
```

### Query 2: Count by service
```
count by (service) ({job="honeypot"})
```

### Query 3: Find SQL injection attempts
```
{job="honeypot", service="database"} |= "UNION" or "DROP"
```

### Query 4: Find directory traversal
```
{job="honeypot", service="http"} |= "../"
```

### Query 5: Admin access attempts
```
{job="honeypot", service="http"} |= "admin"
```

---

## 📊 Expected Results

After running all MCP tools:

✅ Dashboard deployed with 4 panels showing real-time attack data
✅ 4 alert rules active and monitoring for security events
✅ 3 annotations marking critical events in the timeline
✅ 2 incidents created for security team response
✅ 450+ attack events visible in Grafana Loki
✅ Real-time metrics aggregation (278+ HTTP events tracked)

---

## 🔗 Access Points

Once deployed, access via:

- **Dashboard**: https://sigilhive.grafana.net/d/sigilhive
- **Alerts**: https://sigilhive.grafana.net/alerting/list
- **Incidents**: https://sigilhive.grafana.net/incidentevents
- **Loki Logs**: https://sigilhive.grafana.net/explore?datasource=Loki
- **Explore**: Query logs and set up custom panels

---

## 📝 Configuration Files

Load data from these generated JSON files:

- `grafana_dashboard.json` - Dashboard structure
- `grafana_alerts.json` - Alert rule configurations
- `grafana_annotations.json` - Annotation templates
- `grafana_incidents.json` - Incident response templates

---

## ⏱️ Execution Time

Total estimated time for all MCP calls: 2-5 minutes

---

**Status**: Ready for MCP Tool Execution  
**Last Updated**: December 3, 2025  
**System**: SigilHive Honeypot Monitoring v1.0
