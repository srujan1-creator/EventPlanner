"""Vercel Serverless Function entry point for FestivaFlow FastAPI application."""

import os
import sys

# Ensure project root directory is in sys.path for Vercel's serverless runtime
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from backend.app.main import app

# Export app instance for @vercel/python
__all__ = ["app"]
