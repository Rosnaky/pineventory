
from aiohttp import web

from app.config import WEB_SERVER_PORT
from app.utils.logger import logger

async def health_check(request):
    return web.Response(text=f"Bot is running.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', WEB_SERVER_PORT)
    await site.start()
    logger.info(f"Web server listening on port {WEB_SERVER_PORT}")
    
    # Keep the server running
    return runner
