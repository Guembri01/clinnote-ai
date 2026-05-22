"""
ClinNote AI — Server Entry Point
=================================
Sets Windows-compatible asyncio event loop BEFORE uvicorn starts.
Required for psycopg3 async support on Windows (Python 3.10+).

Usage:
    python run.py [--port 8001]
"""
import asyncio
import sys

# MUST be set before any async libraries are initialized
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level="info",
        reload=args.reload,
    )
