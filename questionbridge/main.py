"""
QuestionBridge — entry point.

Starts three services on the same asyncio event loop:
  • FastAPI REST API  (http://HOST:PORT/api/...)
  • NiceGUI dashboard (http://HOST:PORT/)
  • Aiogram Telegram bot (long-polling)
"""

import asyncio
import signal
import uvicorn
from nicegui import ui

from .config import settings
from . import dashboard  # noqa: F401 — registers @ui.page routes
from .api import app
from .bot import start_polling

ui.run_with(app, storage_secret="qbridge-secret-changeme")


async def _run_bot() -> None:
    while True:
        try:
            print("[bot] Starting polling…")
            await start_polling()
        except asyncio.CancelledError:
            print("[bot] Shutting down.")
            raise
        except Exception as exc:
            print(f"[bot] Error: {exc!r} — restarting in 5 s…")
            await asyncio.sleep(5)


async def _main() -> None:
    config = uvicorn.Config(
        app=app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    print(f"[main] QuestionBridge starting on http://{settings.API_HOST}:{settings.API_PORT}")
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, server.handle_exit, sig, None)
    try:
        await asyncio.gather(server.serve(), _run_bot())
    except asyncio.CancelledError:
        pass


def run() -> None:
    asyncio.run(_main())
