# Finance Portal Backend Startup Script
# This sets up the environment and starts the server

# Set your Anthropic API key here
$env:ANTHROPIC_API_KEY = "YOUR_API_KEY_HERE"

# Activate virtual environment and start server
Write-Host "Starting Finance Portal Backend..." -ForegroundColor Cyan
Write-Host "Claude API: Enabled" -ForegroundColor Green

& .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload


