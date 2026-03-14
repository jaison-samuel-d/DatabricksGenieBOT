import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Log
logger = logging.getLogger(__name__)

# Env vars
load_dotenv()

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID")
DATABRICKS_CLIENT_SECRET = os.getenv("DATABRICKS_CLIENT_SECRET")
# Azure Bot: support both naming conventions (Azure portal uses MICROSOFT_APP_*)
APP_ID = os.getenv("APP_ID") or os.getenv("MICROSOFT_APP_ID", "")
APP_PASSWORD = os.getenv("APP_PASSWORD") or os.getenv("MICROSOFT_APP_PASSWORD", "")
# For single-tenant bots: use your tenant ID to avoid AADSTS700016 "not found in Bot Framework"
CHANNEL_AUTH_TENANT = os.getenv("CHANNEL_AUTH_TENANT") or os.getenv("MICROSOFT_APP_TENANT_ID", "")
OAUTH_CONNECTION_NAME = os.getenv("OAUTH_CONNECTION_NAME", "")
WELCOME_MESSAGE = (
    "Welcome to Marketing Analytics Genie! I'm your Professional Marketing Analyst. "
    "Ask me about ROI, spend optimization, attribution, or trends. "
    "Type your question below to get started."
)
WAITING_MESSAGE = "Querying Genie for results..."
LOGIN_REQUIRED_MESSAGE = "Please type **login** to sign in and use Genie."
SWITCHING_MESSAGE = "switch to @"
AUTH_METHOD = os.getenv("AUTH_METHOD", "service_principal")  # or "oauth" for user sign-in (video flow)

# Spaces mapping in json file
__dir = Path(__file__).parent

with open(f"{__dir}/spaces.json") as f:
    SPACES = json.load(f)
REVERSE_SPACES = {v: k for k, v in SPACES.items()}
# Default space when user has not selected one (e.g. first message)
DEFAULT_SPACE_ID = next(iter(SPACES.values()), "") if SPACES else ""
LIST_SPACES = ", ".join([f"@{space_name}" for space_name in SPACES.keys()])
SPACE_NOT_FOUND = (
    f"Genie space not found. Please use {LIST_SPACES} to specify the space."
)

# Recommendation questions shown on welcome and after each answer (edit to match your data)
RECOMMENDATION_QUESTIONS = [
    "Give me Facebook ROI",
    "Show ROI by region and quarter",
    "What are the top performing channels?",
    "Compare bookings across regions",
]
