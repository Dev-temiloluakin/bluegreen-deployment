cat > runbook.md << 'EOF'
# Blue/Green Deployment Runbook

## Alert Types and Response Actions

### 1. Failover Detected Alert

**What it means:**
Traffic has automatically switched from one pool to another (Blue→Green or Green→Blue).

**Alert Example:**
```
🔄 FAILOVER Alert
Failover Detected!
- From: blue
- To: green
Action Required: Check health of blue container
```

**Operator Actions:**
1. Check container health:
```bash
   docker compose ps
   docker compose logs app_blue
```

2. If container is down, restart it:
```bash
   docker compose restart app_blue
```

3. Monitor for automatic recovery after 5 seconds

---

### 2. High Error Rate Alert

**What it means:**
The upstream services are returning too many 5xx errors (> threshold%).

**Alert Example:**
```
🚨 ERROR Alert
High Error Rate Detected!
- Error Rate: 5.2%
- Threshold: 2%
- Window: Last 200 requests
Action Required: Check upstream health and logs
```

**Operator Actions:**
1. Check container health:
```bash
   docker compose ps
```

2. Check application logs:
```bash
   docker compose logs app_blue
   docker compose logs app_green
```

3. Check Nginx logs:
```bash
   docker compose exec nginx tail -n 50 /var/log/nginx/access.log
```

---

## Maintenance Mode

To suppress alerts during planned maintenance:
```bash
# Enable maintenance mode
nano .env
# Set: MAINTENANCE_MODE=true

# Restart watcher
docker compose restart alert_watcher
```

---

## Manual Failover Testing
```bash
# 1. Check current pool
curl -I http://localhost:8080/version | grep X-App-Pool

# 2. Trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# 3. Watch for failover alert in Slack

# 4. Verify traffic switched
curl -I http://localhost:8080/version | grep X-App-Pool

# 5. Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| SLACK_WEBHOOK_URL | (required) | Slack incoming webhook URL |
| ERROR_RATE_THRESHOLD | 2 | Error rate % to trigger alert |
| WINDOW_SIZE | 200 | Number of requests to track |
| ALERT_COOLDOWN_SEC | 300 | Minimum seconds between alerts |
| MAINTENANCE_MODE | false | Suppress all alerts when true |

---

## Emergency Procedures

### Complete Service Failure
```bash
# Stop all services
docker compose down

# Check logs
docker compose logs --tail=100

# Start fresh
docker compose up -d
```
EOF
