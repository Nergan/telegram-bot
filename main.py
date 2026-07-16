import logging
import asyncio
import uvloop
from aiohttp import web
from app import app

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # uvloop is a high-performance drop-in replacement for the standard asyncio event loop.
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    # Render provides the PORT environment variable.
    port = 8080
    
    logging.info(f"Starting web server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)