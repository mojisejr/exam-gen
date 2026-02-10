"""
Vercel Serverless entrypoint for FastAPI.
"""
import os
import sys
from pathlib import Path

# Fix: Add the 'api' directory to sys.path so that absolute imports work on Vercel
api_dir = Path(__file__).parent.resolve()
if str(api_dir) not in sys.path:
    sys.path.append(str(api_dir))

from server.main import app

__all__ = ["app"]
