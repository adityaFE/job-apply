#!/usr/bin/env python3
"""
Launcher script to run the Job Apply Intelligence Hub dashboard.
"""
import sys
import uvicorn

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    print(f"🚀 Launching Job Apply Intelligence Hub at http://{host}:{port}")
    uvicorn.run("src.dashboard.app:app", host=host, port=port, reload=True)
