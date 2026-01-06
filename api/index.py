"""
Vercel serverless function entry point.
Exports FastAPI app directly for Vercel's ASGI runtime.
"""
import sys
from pathlib import Path

# Add api directory to Python path so 'app' module can be found
api_dir = Path(__file__).parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.main import app
from app.database import init_db

# Initialize database tables
try:
    init_db()
except Exception as e:
    print(f"Database initialization note: {e}")

# Export app for Vercel ASGI runtime
# The app variable is imported and exported for Vercel to use
