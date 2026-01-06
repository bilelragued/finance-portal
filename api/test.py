"""Simple test function with import debugging."""
from http.server import BaseHTTPRequestHandler
import json
import sys
import traceback
from pathlib import Path

# Add api directory to Python path
api_dir = Path(__file__).parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

results = {"tests": [], "api_dir": str(api_dir), "sys_path": sys.path[:5]}

# Test 1: app.database import
try:
    from app.database import init_db, engine, DATABASE_URL
    results["tests"].append({"name": "app.database", "status": "ok", "database_url": DATABASE_URL[:50] + "..." if DATABASE_URL and len(DATABASE_URL) > 50 else DATABASE_URL})
except Exception as e:
    results["tests"].append({"name": "app.database", "status": "error", "error": str(e), "traceback": traceback.format_exc()})

# Test 2: app.main import
try:
    from app.main import app
    results["tests"].append({"name": "app.main", "status": "ok"})
except Exception as e:
    results["tests"].append({"name": "app.main", "status": "error", "error": str(e), "traceback": traceback.format_exc()})

# Test 3: db init
try:
    init_db()
    results["tests"].append({"name": "init_db", "status": "ok"})
except Exception as e:
    results["tests"].append({"name": "init_db", "status": "error", "error": str(e), "traceback": traceback.format_exc()})


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(results, indent=2).encode())
        return
