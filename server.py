#!/usr/bin/env python3
"""
ZhipuAI Usage Monitor Server
- HTTP server for dashboard and API
- Background scheduler for auto-refresh (every 15 minutes)
"""

import os
import json
import time
import threading
import subprocess
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Configuration
PORT = int(os.environ.get("PORT", 8080))
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", 15)) * 60  # minutes to seconds
DATA_DIR = Path("/app/data")
SCRIPT_PATH = Path("/app/zhipu_usage.py")
HISTORY_FILE = DATA_DIR / "usage_history.json"

# Global state
last_update_time = None
next_update_time = None
update_lock = threading.Lock()

def load_env():
    """Load environment variables from .env file"""
    env_file = DATA_DIR / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

def run_query():
    """Run the usage query script"""
    global last_update_time, next_update_time
    
    try:
        now = datetime.now(timezone.utc)
        print(f"[{now.isoformat()}] Running usage query...")
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/app"
        )
        
        if result.returncode == 0:
            with update_lock:
                last_update_time = now
                next_update_time = now + timedelta(seconds=REFRESH_INTERVAL)
            print(f"[{datetime.now(timezone.utc).isoformat()}] Query completed successfully")
        else:
            print(f"[{datetime.now(timezone.utc).isoformat()}] Query failed: {result.stderr}")
            
    except Exception as e:
        print(f"[{datetime.now(timezone.utc).isoformat()}] Query error: {e}")

def scheduler():
    """Background scheduler for auto-refresh"""
    while True:
        time.sleep(REFRESH_INTERVAL)
        run_query()

def get_status():
    """Get current status"""
    with update_lock:
        return {
            "last_update": last_update_time.isoformat() if last_update_time else None,
            "next_update": next_update_time.isoformat() if next_update_time else None,
            "refresh_interval": REFRESH_INTERVAL,
            "refresh_interval_minutes": REFRESH_INTERVAL // 60
        }

class UsageHandler(SimpleHTTPRequestHandler):
    """Custom handler for API endpoints"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/app", **kwargs)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/status":
            self.send_json_response(get_status())
        elif path == "/api/refresh":
            # Trigger immediate refresh
            threading.Thread(target=run_query, daemon=True).start()
            self.send_json_response({"status": "refresh_triggered", **get_status()})
        elif path == "/api/history":
            # Return usage history
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r") as f:
                    data = json.load(f)
                self.send_json_response(data)
            else:
                self.send_json_response({"records": [], "error": "No data yet"})
        elif path == "/" or path == "/index.html":
            # Redirect to dashboard
            self.path = "/dashboard.html"
            super().do_GET()
        else:
            super().do_GET()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/refresh":
            # Trigger immediate refresh
            threading.Thread(target=run_query, daemon=True).start()
            self.send_json_response({"status": "refresh_triggered", **get_status()})
        else:
            self.send_error(404, "Not Found")
    
    def send_json_response(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}")

def main():
    """Main entry point"""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load environment variables
    load_env()
    
    # Run initial query
    print("="*60)
    print("🤖 ZhipuAI Usage Monitor Server")
    print("="*60)
    print(f"Port: {PORT}")
    print(f"Refresh interval: {REFRESH_INTERVAL // 60} minutes")
    print(f"Data directory: {DATA_DIR}")
    print("="*60)
    
    run_query()
    
    # Start scheduler thread
    scheduler_thread = threading.Thread(target=scheduler, daemon=True)
    scheduler_thread.start()
    print(f"[{datetime.now().isoformat()}] Scheduler started")
    
    # Start HTTP server
    server = HTTPServer(("0.0.0.0", PORT), UsageHandler)
    print(f"[{datetime.now().isoformat()}] Server started at http://0.0.0.0:{PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().isoformat()}] Server stopped")
        server.shutdown()

if __name__ == "__main__":
    main()
