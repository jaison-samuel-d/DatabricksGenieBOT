"""
Databricks Genie Bot

Author : Vuong Nguyen
Original Author: Luiz Carrossoni Neto
Revision: 2.0

This script implements an experimental chatbot that interacts with Databricks' Genie API.
The bot facilitates conversations with Genie,
Databricks' AI assistant, through a chat interface.

Note: This is experimental code and is not intended for production use.
"""

import logging
import os

from aiohttp import web
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    ConversationState,
    UserState,
    MemoryStorage,
)
from botbuilder.schema import Activity

from chatx.bot import MyBot
from chatx.const import APP_ID, APP_PASSWORD, CHANNEL_AUTH_TENANT, OAUTH_CONNECTION_NAME, AUTH_METHOD

from chatx.login_dialog import LoginDialog

# Log - ensure INFO is visible in Azure (stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create MemoryStorage and state
MEMORY = MemoryStorage()
USER_STATE = UserState(MEMORY)
CONVERSATION_STATE = ConversationState(MEMORY)

# Create dialog
DIALOG = LoginDialog(OAUTH_CONNECTION_NAME)

# Create Bot
BOT = MyBot(CONVERSATION_STATE, USER_STATE, DIALOG, auth_method=AUTH_METHOD)

SETTINGS = BotFrameworkAdapterSettings(
    APP_ID, APP_PASSWORD, channel_auth_tenant=CHANNEL_AUTH_TENANT or None
)
ADAPTER = BotFrameworkAdapter(SETTINGS)
logger.info("Genie bot started. APP_ID configured: %s", "yes" if APP_ID else "NO")


async def messages(req: web.Request) -> web.Response:
    logger.info("POST /api/messages received")
    content_type = req.headers.get("Content-Type", "")
    if "application/json" not in content_type:
        return web.Response(status=415)

    body = await req.json()
    activity = Activity().deserialize(body)
    logger.info("Activity type=%s", getattr(activity, "type", "?"))
    auth_header = req.headers.get("Authorization", "")

    try:
        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        if response:
            if response.body is None:
                args = {"status": response.status}
            else:
                args = {"data": response.body, "status": response.status}
            return web.json_response(**args)
        return web.Response(status=201)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return web.Response(status=500)


async def health(_req: web.Request) -> web.Response:
    """Health check endpoint for Azure and reachability tests."""
    return web.json_response({"status": "ok", "service": "genie-bot"})


async def chart_image(req: web.Request) -> web.Response:
    """Serve cached chart PNG by key (Vega-Lite rendered, Genie-style)."""
    from chatx.chart_cache import get_chart, prune_expired

    key = req.match_info.get("key", "")
    if not key:
        return web.Response(status=400, text="Missing chart key")
    prune_expired()
    png_data = get_chart(key)
    if not png_data:
        return web.Response(status=404, text="Chart expired or not found")
    return web.Response(
        body=png_data,
        content_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def export_download(req: web.Request) -> web.Response:
    """Serve exported CSV/Excel file by token."""
    from chatx.export_store import get_export

    token = req.query.get("token")
    fmt = req.query.get("format", "csv")
    if not token:
        return web.Response(status=400, text="Missing token")

    result = get_export(token)
    if not result:
        return web.Response(status=404, text="Export expired or not found")

    content, filename = result
    content_type = "text/csv; charset=utf-8"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type,
    }
    return web.Response(body=content, headers=headers)


async def privacy(_req: web.Request) -> web.Response:
    """Privacy policy page (required by Teams manifest)."""
    return web.Response(
        text="<h1>Privacy Policy</h1><p>This bot processes your messages to answer questions via Databricks Genie. Messages are sent to the Genie API and are subject to Databricks privacy terms.</p>",
        content_type="text/html",
    )


async def terms(_req: web.Request) -> web.Response:
    """Terms of use page (required by Teams manifest)."""
    return web.Response(
        text="<h1>Terms of Use</h1><p>Use of this bot is subject to your organization's policies and Databricks terms of service.</p>",
        content_type="text/html",
    )


app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_get("/privacy", privacy)
app.router.add_get("/terms", terms)
app.router.add_get("/termsofuse", terms)
app.router.add_get("/api/chart/{key}", chart_image)
app.router.add_get("/api/export", export_download)
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        host = os.getenv("HOST", "localhost")
        port = int(os.environ.get("PORT", 3978))
        web.run_app(app, host=host, port=port)
    except Exception as e:
        logger.exception(f"Error running app:  {str(e)}")
