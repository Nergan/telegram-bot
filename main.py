import os
import logging
import asyncio
import uvloop
from aiohttp import web
from app import app

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    
    # Dynamically bind to Render's assigned port, default to 8080 locally
    port = int(os.environ.get("PORT", 8080))
    
    logging.info(f"Starting web server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)