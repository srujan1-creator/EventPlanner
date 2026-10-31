"""Vercel Serverless Function entry point for FestivaFlow FastAPI application."""

import os
import sys

# Ensure project root directory is in sys.path for Vercel's serverless runtime
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from backend.app.main import app
except Exception as e:
    import traceback
    tb = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="FestivaFlow Diagnostic Mode")

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def diagnostic_error_handler(full_path: str):
        return PlainTextResponse(
            f"FestivaFlow Serverless Startup Traceback (Python {sys.version}):\n{tb}",
            status_code=500,
        )

# Export app instance for @vercel/python
__all__ = ["app"]
