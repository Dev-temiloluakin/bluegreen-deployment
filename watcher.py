#!/usr/bin/env python3
"""
Nginx Log Watcher - Monitors logs for failovers and error rates
Sends alerts to Slack with clear identification
"""

import re
import time
import os
import sys
import subprocess
from collections import deque
from datetime import datetime
import requests

# Configuration from environment
SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2'))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))
COOLDOWN = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'

# User identification
DEPLOYMENT_OWNER = os.getenv('DEPLOYMENT_OWNER', 'Unknown')
ENVIRONMENT_NAME = os.getenv('ENVIRONMENT_NAME', 'Production')

LOG_FILE = '/var/log/nginx/access.log'

# State tracking
last_pool = None
last_failover_alert = 0
last_error_alert = 0
request_window = deque(maxlen=WINDOW_SIZE)

# Log pattern
LOG_PATTERN = re.compile(
    r'pool=(?P<pool>\S+)\s+'
    r'release=(?P<release>\S+)\s+'
    r'upstream_status=(?P<status>\S+)'
)


def send_slack_alert(message, alert_type="info"):
    """Send alert to Slack with clear identification"""
    if not SLACK_WEBHOOK or MAINTENANCE_MODE:
        print(f"⚠️  Alert suppressed (no webhook or maintenance mode): {alert_type}")
        return

    emoji_map = {
        "failover": "🔄",
        "error": "🚨",
        "recovery": "✅",
        "info": "ℹ️"
    }

    emoji = emoji_map.get(alert_type, "📢")

    # Add owner identification to header
    header_text = f"{emoji} [{DEPLOYMENT_OWNER}] {alert_type.upper()} Alert"

    payload = {
        "text": f"{emoji} *[{DEPLOYMENT_OWNER}]* Blue/Green Alert - {alert_type.upper()}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Owner:*\n{DEPLOYMENT_OWNER}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Environment:*\n{ENVIRONMENT_NAME}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 🔧 {DEPLOYMENT_OWNER}"
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(SLACK_WEBHOOK, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✓ Slack alert sent: {alert_type}")
        else:
            print(f"✗ Slack alert failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error sending Slack alert: {e}")


def check_error_rate():
    """Check if error rate exceeds threshold"""
    global last_error_alert

    if len(request_window) < WINDOW_SIZE:
        return

    errors = sum(1 for status in request_window if status >= 500)
    error_rate = (errors / len(request_window)) * 100

    if error_rate > ERROR_THRESHOLD:
        now = time.time()
        if now - last_error_alert > COOLDOWN:
            message = (
                f"*High Error Rate Detected!*\n\n"
                f"• Error Rate: {error_rate:.1f}%\n"
                f"• Threshold: {ERROR_THRESHOLD}%\n"
                f"• Window: Last {WINDOW_SIZE} requests\n"
                f"• 5xx Errors: {errors}/{len(request_window)}\n\n"
                f"*Action Required:* Check upstream health and logs"
            )
            send_slack_alert(message, "error")
            last_error_alert = now


def detect_failover(current_pool):
    """Detect pool changes (failover events)"""
    global last_pool, last_failover_alert

    if last_pool is None:
        last_pool = current_pool
        print(f"📍 Initial pool: {current_pool}")
        return

    if current_pool != last_pool:
        now = time.time()
        if now - last_failover_alert > COOLDOWN:
            message = (
                f"*Failover Detected!*\n\n"
                f"• From: `{last_pool}`\n"
                f"• To: `{current_pool}`\n\n"
                f"*Action Required:* Check health of `{last_pool}` container"
            )
            send_slack_alert(message, "failover")
            last_failover_alert = now
            print(f"🔄 FAILOVER: {last_pool} → {current_pool}")

        last_pool = current_pool


def process_log_line(line):
    """Process a single log line"""
    # Parse log entry
    match = LOG_PATTERN.search(line)
    if match:
        pool = match.group('pool')
        status_str = match.group('status')

        # Handle upstream status
        try:
            # Nginx may return "status : status" for retries
            status = int(status_str.split(':')[-1].strip())
        except (ValueError, AttributeError):
            status = 0

        # Track request status
        request_window.append(status)
        
        # Print activity indicator
        status_emoji = "✓" if status < 400 else "⚠️" if status < 500 else "❌"
        print(f"{status_emoji} [{pool}] Status: {status}")

        # Detect failover
        if pool and pool != '-':
            detect_failover(pool)

        # Check error rate
        check_error_rate()


def tail_log():
    """Tail Nginx log file and process entries"""
    print(f"=" * 60)
    print(f"DEPLOYMENT WATCHER STARTING")
    print(f"=" * 60)
    print(f"Owner: {DEPLOYMENT_OWNER}")
    print(f"Environment: {ENVIRONMENT_NAME}")
    print(f"Log file: {LOG_FILE}")
    print(f"Slack webhook: {'✓ configured' if SLACK_WEBHOOK else '✗ NOT SET'}")
    print(f"Error threshold: {ERROR_THRESHOLD}%")
    print(f"Window size: {WINDOW_SIZE}")
    print(f"Maintenance mode: {MAINTENANCE_MODE}")
    print(f"=" * 60)
    print("")

    # Wait for log file to exist
    while not os.path.exists(LOG_FILE):
        print(f"⏳ Waiting for {LOG_FILE}...")
        time.sleep(2)

    print("✓ Log file found, starting monitoring...")
    print("✓ Now monitoring new log entries...")
    print("")

    # Use tail -F to follow the log file (even through rotations)
    # -F follows by name and retries if file is inaccessible
    # -n 0 starts from the end (don't show existing lines)
    process = subprocess.Popen(
        ['tail', '-F', '-n', '0', LOG_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )

    try:
        # Read lines as they come
        for line in iter(process.stdout.readline, ''):
            if line:
                process_log_line(line.strip())
    except KeyboardInterrupt:
        print("\n👋 Shutting down watcher...")
        process.terminate()
        sys.exit(0)
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        process.terminate()
        sys.exit(1)


if __name__ == '__main__':
    try:
        tail_log()
    except KeyboardInterrupt:
        print("\n👋 Shutting down watcher...")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
