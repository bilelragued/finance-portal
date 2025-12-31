"""
Vercel serverless function entry point.
This wraps the FastAPI app for Vercel's serverless environment.
"""
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from mangum import Mangum
from app.main import app

# Mangum handler for Vercel
handler = Mangum(app, lifespan="off")
