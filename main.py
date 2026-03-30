#!/usr/bin/env python3
"""
Main entry point for the KVT Service Bot.
This file allows running both backend and bot.
"""

import asyncio
import sys
from bot.worker import main

# Only import backend modules when needed
def import_backend():
    try:
        import uvicorn
        from app.main import app
        return uvicorn, app
    except ImportError as e:
        print(f"Backend modules not available: {e}")
        return None, None

async def run_bot():
    """Run the Max messenger bot"""
    await main()

def run_backend():
    """Run the FastAPI backend"""
    uvicorn, app = import_backend()
    if uvicorn is None:
        print("Cannot run backend: modules not available")
        return
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload in Docker to avoid signal issues
        log_level="info"
    )

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "bot":
        # Run bot only
        print("Starting Max messenger bot...")
        asyncio.run(run_bot())
    elif len(sys.argv) > 1 and sys.argv[1] == "backend":
        # Run backend only
        print("Starting FastAPI backend...")
        run_backend()
    else:
        # Run both (default)
        print("Starting both backend and bot...")
        print("Backend: http://localhost:8000")
        print("Bot: Running...")
        
        # Start backend in a separate process/thread
        import threading
        backend_thread = threading.Thread(target=run_backend)
        backend_thread.daemon = True
        backend_thread.start()
        
        # Start bot in main thread
        asyncio.run(run_bot())
