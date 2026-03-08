# SigilHive Adversarial Agent - Real Attack & Grafana Integration Guide

## Problem Summary
The original adversarial agent was **simulating** attacks instead of executing real ones:
- No real SSH/HTTP/Database connections
- No metrics sent to Grafana
- No persistent result storage
- Training data lost on restart

## Solution Overview
I've implemented:
1. **Real Attack Executors** (`real_attacks.py`) - Execute actual SSH, HTTP, and Database attacks
2. **Persistent Storage** (`result_storage.py`) - SQLite database for all attack results
3. **Metrics Service** (`metrics_service.py`) - HTTP service that exposes metrics to Grafana
4. **Enhanced Agent** (`enhanced_agent.py`) - Uses real attacks and stores all results

## Setup Instructions

### 1. Install Dependencies
```bash
pip install paramiko requests pymysql flask
```

### 2. Update docker-compose.yaml
Add the metrics service to expose attack metrics:

```yaml
  metrics-exporter:
    build: 
      context: .
      dockerfile: metrics_exporter.Dockerfile
    ports:
      - "5555:5000"
    environment:
      STORAGE_PATH: /shared/attack_results.db
      METRICS_HOST: 0.0.0.0
      METRICS_PORT: 5000
    volumes:
      - ./attack_results.db:/shared/attack_results.db
    depends_on:
      - adversarial-trainer
```

### 3. Create metrics_exporter.Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY adversarial_training/metrics_service.py /app/
COPY adversarial_training/result_storage.py /app/

CMD ["python", "-m", "flask", "--app=metrics_service:create_metrics_service", "run", "--host=0.0.0.0"]
```

### 4. Update Orchestrator to Use Enhanced Agent
In `orchestrator.py`, change:
```python
from .enhanced_agent import EnhancedAdversarialAgent

# In __init__:
self.agent = EnhancedAdversarialAgent(
    gemini_api_key=self.gemini_api_key,
    target_host=target_host,
    ssh_port=ssh_port,
    http_port=http_port,
    db_port=db_port,
)
```

### 5. Configure Grafana Data Source
In Grafana UI:
1. **Configuration → Data Sources → Add data source**
2. Select **Prometheus**
3. URL: `http://localhost:5555/metrics`
4. Save

### 6. Import/Create Grafana Dashboards

#### Dashboard 1: Attack Overview
Add panels:
- **Attack Success Rate** (time series)
  - Query: `sigilhive_attack_success`
  - Visualize as graph
  
- **Data Extracted (bytes)**
  - Query: `sigilhive_data_extracted`
  - Visualize as stat
  
- **Suspicion Level**
  - Query: `sigilhive_suspicion_level`
  - Visualize as gauge

- **Attacks by Protocol**
  - Query: `count(sigilhive_attack_success) by (protocol)`
  - Visualize as pie chart

#### Dashboard 2: API Endpoints (Optional)
Access these JSON endpoints directly:
- `GET http://localhost:5555/api/metrics/statistics` - Overall stats
- `GET http://localhost:5555/api/metrics/success-rate` - Success rate over time
- `GET http://localhost:5555/api/metrics/data-extracted?timeframe=24h` - Data extracted last 24 hours
- `GET http://localhost:5555/api/metrics/protocol-breakdown` - Attacks by protocol

### 7. Start Training with Real Attacks
```python
from adversarial_training.orchestrator import Orchestrator, OrchestratorMode

orchestrator = Orchestrator(
    gemini_api_key="your-key",
    target_host="localhost"
)

# This now executes REAL attacks against the honeypot
orchestrator.run(mode=OrchestratorMode.SCHEDULED)
```

### 8. Monitor Results
Check database directly:
```bash
sqlite3 attack_results.db
sqlite> SELECT protocol, COUNT(*), SUM(data_extracted) FROM attack_results GROUP BY protocol;
```

## What's Now Working

### Real Attacks ✓
- **SSH**: Reconnaissance and exploitation using paramiko
- **HTTP**: API enumeration and SQL injection attempts
- **Database**: Schema discovery and data extraction via SQL queries

### Data Collection ✓
- Every attack stores: protocol, attack_type, success, data_extracted, suspicion_level, duration
- Results persist in SQLite and survive service restarts
- Supports querying by session_id, protocol, time range

### Grafana Integration ✓
- Prometheus-format `/metrics` endpoint
- REST API endpoints for custom queries
- Real-time attack metrics visible in dashboards

## File Structure
```
adversarial_training/
├── real_attacks.py          # Real SSH/HTTP/DB attack implementations
├── result_storage.py        # SQLite storage for attack results
├── metrics_service.py       # Flask service exposing Prometheus metrics
├── enhanced_agent.py        # Agent wrapper using real attacks
├── orchestrator.py          # Updated to use EnhancedAdversarialAgent (TODO)
├── adversarial_agent.py     # Original agent (kept for compatibility)
└── attack_results.db        # SQLite database (auto-created)
```

## Troubleshooting

### No metrics appearing in Grafana
1. Check if metrics service is running: `curl http://localhost:5555/health`
2. Verify database exists: `ls -la attack_results.db`
3. Check if attacks are being stored: `curl http://localhost:5555/api/metrics/statistics`

### "Connection refused" errors
- Ensure honeypot services are running on correct ports
- Check firewall rules allowing connections to SSH (5555), HTTP (8080), DB (2225)

### Slow attacks
- Real attacks make actual network connections (slower than simulation)
- Adjust timeouts in `real_attacks.py` if needed
- Database attacks especially slow due to query complexity

## Performance Notes
- Real attacks are slower than simulations (5-10x)
- For faster training, use fewer max_steps or longer step_delay
- Consider scaling to multiple attack threads if needed

## Next Steps
1. Update `orchestrator.py` to instantiate `EnhancedAdversarialAgent`
2. Start metrics service in docker-compose
3. Configure Grafana data source pointing to metrics endpoint
4. Run training and verify attacks appear in Grafana
