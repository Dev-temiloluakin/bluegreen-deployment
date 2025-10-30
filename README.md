# Blue/Green Deployment with Nginx

This project demonstrates a Blue/Green deployment pattern with automatic failover using Nginx as a reverse proxy.

## Architecture
```
User Request → Nginx (Port 8080) → Blue App (Port 8081) [Primary]
                                 → Green App (Port 8082) [Backup]
```

## Prerequisites

- Docker Desktop installed and running
- Docker Compose v2.x
- WSL2 (for Windows users)

## Setup Instructions

### 1. Clone/Download this repository

### 2. Configure environment variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and update with your actual image URLs:
```bash
BLUE_IMAGE= https://hub.docker.com/r/yimikaade/wonderful/tags
GREEN_IMAGE= https://hub.docker.com/r/yimikaade/wonderful/tags
```

### 3. Start the services
```bash
./start.sh
```

# Start services
docker compose up -d
```

## Testing

### Test Normal Operation (Blue Active)
```bash
# Check version endpoint
curl http://localhost:8080/version

# Expected response headers:
# X-App-Pool: blue
# X-Release-Id: blue-v1.0.0
```

### Test Failover (Blue → Green)
```bash
# 1. Induce failure on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Test main endpoint - should automatically failover to Green
curl http://localhost:8080/version

# Expected response headers:
# X-App-Pool: green
# X-Release-Id: green-v1.0.0

# 3. Stop chaos (restore Blue)
curl -X POST http://localhost:8081/chaos/stop
```

### Stress Test (Verify Zero Downtime)
```bash
# Run multiple requests during failover
for i in {1..20}; do
  curl -s http://localhost:8080/version -w "\nStatus: %{http_code}\n"
  sleep 0.5
done
```

Expected: All requests return 200 OK

## Endpoints

### Via Nginx (Port 8080)
- `GET http://localhost:8080/version` - Get app version and pool info
- `GET http://localhost:8080/healthz` - Health check

### Direct Blue Access (Port 8081)
- `POST http://localhost:8081/chaos/start?mode=error` - Start chaos (500 errors)
- `POST http://localhost:8081/chaos/start?mode=timeout` - Start chaos (timeouts)
- `POST http://localhost:8081/chaos/stop` - Stop chaos

### Direct Green Access (Port 8082)
- Same endpoints as Blue

## How Failover Works

1. **Detection**: Nginx sends health checks every 5 seconds
2. **Failure**: Blue fails 2 consecutive requests within 5 seconds
3. **Switchover**: Nginx marks Blue as down and routes to Green (backup)
4. **Retry**: Within the same client request, Nginx retries failed requests on Green
5. **Recovery**: After 5 seconds, Nginx retries Blue automatically

## Configuration

### Key Nginx Settings

- `max_fails=2` - Mark server down after 2 failures
- `fail_timeout=5s` - Retry server after 5 seconds
- `proxy_connect_timeout=2s` - Fast failure detection
- `proxy_next_upstream` - Retry on errors/timeouts
- `backup` - Green only used when Blue is down

## Troubleshooting

### Check service status
```bash
docker compose ps
```

### View logs
```bash
# All services
docker compose logs

# Specific service
docker compose logs nginx
docker compose logs app_blue
docker compose logs app_green
```

### Restart services
```bash
docker compose restart
```

### Stop services
```bash
docker compose down
```

## Project Structure
```
.
├── docker-compose.yml      # Service definitions
├── nginx.conf.template     # Nginx config template
├── nginx.conf             # Generated nginx config (do not edit)
├── .env                   # Environment variables (git-ignored)
├── .env.example           # Environment template
├── start.sh               # Startup script
└── README.md             # This file
```

## Environment Variables

| Variable           | Description                    | Example                  |
|--------------------|--------------------------------|--------------------------|
| `BLUE_IMAGE`       | Docker image for Blue service  | `ghcr.io/user/app:blue`  |
| `GREEN_IMAGE`      | Docker image for Green service | `ghcr.io/user/app:green` |
| `ACTIVE_POOL`      | Currently active pool          | `blue` or `green`        |
| `RELEASE_ID_BLUE`  | Blue release identifier        | `blue-v1.0.0`            |
| `RELEASE_ID_GREEN` | Green release identifier       | `green-v1.0.0`           |
| `PORT`             | App internal port              | `3000`                   |
| `NGINX_PORT`       | Nginx public port              | `8080`                   |
| `BLUE_PORT`        | Blue external port             | `8081`                   |
| `GREEN_PORT`       | Green external port            | `8082`                   |

## Success Criteria

- All traffic goes to Blue in normal state
- Automatic failover to Green when Blue fails
- Zero failed client requests during failover
- Headers `X-App-Pool` and `X-Release-Id` are forwarded correctly
- Response time < 10 seconds per request
