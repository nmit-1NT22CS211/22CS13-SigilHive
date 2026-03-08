# Quick Start: Real Attacks & Grafana Dashboard

## What Was Wrong?
The original adversarial agent was a **simulation engine**:
- Simulated attacks with static responses
- No actual connections to honeypot services
- No Grafana metrics (nothing to display)
- Training data existed only in memory
- Results lost on service restart

## What's Fixed?
✅ **Real SSH/HTTP/Database attacks** executing against honeypot services  
✅ **Persistent SQLite storage** for all attack results  
✅ **Prometheus metrics endpoint** for Grafana integration  
✅ **REST API** for custom metrics queries  
✅ **Dashboard-ready** metrics (with examples)

---

## 5-Minute Setup

### Step 1: Download New Files
The following files were created:
```
adversarial_training/
├── real_attacks.py           ← SSH/HTTP/DB attack implementations
├── result_storage.py         ← SQLite persistent storage
├── metrics_service.py        ← Prometheus metrics HTTP service
├── enhanced_agent.py         ← Agent using real attacks
└── (attack_results.db)       ← Auto-created on first run

Root:
├── start_metrics_service.py  ← Standalone metrics launcher
├── test_real_attacks.py      ← Test script
├── REAL_ATTACKS_SETUP.md     ← Full setup guide
├── ORCHESTRATOR_INTEGRATION.py  ← Code example
└── QUICK_START.md            ← This file
```

### Step 2: Install Dependencies
```bash
pip install paramiko requests pymysql flask
```

### Step 3: Test Real Attacks (Optional but Recommended)
Verify attacks work before running full training:
```bash
python test_real_attacks.py --host localhost --ssh-port 5555 --http-port 8080 --db-port 2225
```

Expected output:
```
SSH Recon: Success: True | Data extracted: 256 bytes
HTTP Recon: Success: True | Responses: 3
Database Recon: Success: True | Data extracted: 512 bytes
```

### Step 4: Start Metrics Service
In a separate terminal:
```bash
python start_metrics_service.py --port 5000
```

This exposes:
- `http://localhost:5000/health` - Service health
- `http://localhost:5000/metrics` - Prometheus format metrics
- `http://localhost:5000/api/metrics/statistics` - JSON attack statistics

### Step 5: Update Orchestrator (Optional)
To use real attacks in training, update `orchestrator.py`:

Find this code (around line 75):
```python
self.agent = AdversarialAgent(
    gemini_api_key=self.gemini_api_key,
    target_host=target_host,
    ...
)
```

Replace with:
```python
try:
    from .enhanced_agent import EnhancedAdversarialAgent
    from .result_storage import AttackResultStorage
    
    storage = AttackResultStorage()
    self.agent = EnhancedAdversarialAgent(
        gemini_api_key=self.gemini_api_key,
        target_host=target_host,
        ssh_port=ssh_port,
        http_port=http_port,
        db_port=db_port,
        storage=storage,
    )
except ImportError:
    # Fallback to simulated attacks
    self.agent = AdversarialAgent(...)
```

See `ORCHESTRATOR_INTEGRATION.py` for full example.

### Step 6: Configure Grafana

**In Grafana:**
1. Create new dashboard
2. Add data source → Prometheus → `http://localhost:5000/metrics`
3. Create panels with these queries:

#### Panel 1: Attack Success Rate
```
rate(sigilhive_attack_success[5m])
```

#### Panel 2: Data Extracted (Last Hour)
```
sum(increase(sigilhive_data_extracted[1h])) by (protocol)
```

#### Panel 3: Suspicion Level
```
sigilhive_suspicion_level
```

#### Panel 4: Attacks by Protocol
```
count(sigilhive_attack_success) by (protocol)
```

---

## What's Happening Now?

### Attack Flow
```
AdversarialAgent (LangGraph + Gemini)
    ↓
EnhancedAdversarialAgent (real attacks wrapper)
    ↓
Real Attackers (SSH/HTTP/DB)
    ↓
Attack Results → SQLite Database
    ↓
Metrics Service (Prometheus format)
    ↓
Grafana Dashboard ← You see this!
```

### Real Attack Details

**SSH Attacks:**
- Uses paramiko library
- Recon: Executes `uname`, `whoami`, `id`, etc.
- Exploit: Attempts file access (`/etc/shadow`, SSH keys)
- Realistic timeouts and error handling

**HTTP Attacks:**
- Uses requests library
- Recon: Enumerates endpoints (`/admin`, `/api/v1`, etc.)
- Exploit: Attempts SQL injection, admin bypass
- Returns actual HTTP status codes

**Database Attacks:**
- Uses pymysql library
- Recon: Discovers databases and tables
- Exploit: Extracts user data and schema info
- Real MySQL error handling

### Storage
Every attack stores:
- Protocol (ssh/http/database)
- Attack type (recon/exploit/persist/exfil)
- Success (true/false)
- Data extracted (bytes)
- Suspicion level (0.0-1.0)
- Duration (seconds)
- Responses (actual output)
- Timestamp

All persisted to `attack_results.db`

---

## Check If It's Working

### Quick Checks
```bash
# Check database exists
ls -la attack_results.db

# Query stored results
sqlite3 attack_results.db "SELECT COUNT(*) FROM attack_results;"

# Check metrics service
curl http://localhost:5000/health

# Get statistics
curl http://localhost:5000/api/metrics/statistics | jq

# Get raw metrics
curl http://localhost:5000/metrics
```

### Grafana Verification
1. In Grafana, test the data source:
   - Grafana → Configuration → Data Sources → Prometheus (your metrics)
   - Click "Save & Test"
   - Should see "Data source is working"

2. Query the metrics:
   - Explore → Select Prometheus
   - Try `sigilhive_attack_success` in search
   - Should see real data points

---

## Performance Notes

### Real vs Simulated
```
Simulated Attack:  <1ms  (just generates fake data)
Real SSH Attack:   100-500ms (actual network + auth)
Real HTTP Attack:  200-800ms (HTTP requests + parsing)
Real DB Attack:    300-1000ms (SQL queries + data transfer)
```

**Training time impact:**
- If running 100 attacks/hour
- Simulated: ~10 attacks/minute
- Real: ~0.5-2 attacks/minute (depends on success rate)

### Optimization Tips
- Adjust timeouts in `real_attacks.py` (line ~20)
- Run multiple agents in parallel
- Use faster honeypot hardware
- Consider batch queries for database attacks

---

## Troubleshooting

### No data in Grafana
```bash
# 1. Check if metrics service is running
curl http://localhost:5000/health

# 2. Check if database has data
sqlite3 attack_results.db "SELECT * FROM attack_results LIMIT 1;"

# 3. Verify data source in Grafana (test connection)

# 4. Check metrics format
curl http://localhost:5000/metrics | head -20
```

### Attacks timing out
```python
# In real_attacks.py, increase timeout:
self.timeout = 10  # Was 5
```

### "Connection refused" errors
- SSH service running on 5555?
- HTTP service on 8080?
- Database on 2225?

Check: `docker-compose ps`

### Memory usage growing
- SQLite database getting large?
- Clear old data: `sqlite3 attack_results.db "DELETE FROM attack_results WHERE timestamp < datetime('now', '-7 days');"`

---

## Next Steps

1. ✅ Download new files
2. ✅ Install dependencies
3. ✅ Test with `test_real_attacks.py`
4. ✅ Start metrics service
5. ✅ Update orchestrator (optional)
6. ✅ Configure Grafana
7. ✅ Run training and watch the dashboard!

---

## File Reference

| File | Purpose |
|------|---------|
| `real_attacks.py` | SSH, HTTP, Database attack implementations |
| `result_storage.py` | SQLite database for persistent storage |
| `metrics_service.py` | HTTP service exposing Prometheus metrics |
| `enhanced_agent.py` | Agent wrapper combining them together |
| `start_metrics_service.py` | Standalone launcher for metrics |
| `test_real_attacks.py` | Test script for attack implementations |
| `REAL_ATTACKS_SETUP.md` | Full detailed setup guide |
| `ORCHESTRATOR_INTEGRATION.py` | Integration code example |

---

## Questions?

Check `REAL_ATTACKS_SETUP.md` for:
- Detailed Docker integration
- Custom dashboard creation
- API endpoint reference
- Performance tuning
- Advanced configuration
