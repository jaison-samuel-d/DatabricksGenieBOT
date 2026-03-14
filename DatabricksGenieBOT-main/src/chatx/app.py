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


app = web.Application()
app.router.add_get("/", health)
app.router.add_get("/health", health)
app.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        host = os.getenv("HOST", "localhost")
        port = int(os.environ.get("PORT", 3978))
        web.run_app(app, host=host, port=port)
    except Exception as e:
        logger.exception(f"Error running app:  {str(e)}")
