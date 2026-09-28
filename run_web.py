"""
ClinRESET Web Server Launcher.
Starts the FastAPI application with Uvicorn.

Usage:
    python run_web.py [--host 127.0.0.1] [--port 8000] [--reload]
"""

import argparse
import sys
import uvicorn


def main():
    parser = argparse.ArgumentParser(
        description="ClinRESET — Clinical Report Simplification Platform Web Server"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code modifications",
    )

    args = parser.parse_args()

    print("=" * 72)
    print("ClinRESET — Clinical Report Simplification Platform")
    print("=" * 72)
    print(f"Starting server at: http://{args.host}:{args.port}")
    print(f"Interactive API Docs: http://{args.host}:{args.port}/docs")
    print(f"Methodology Studio:   http://{args.host}:{args.port}#studio")
    print("=" * 72)

    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
