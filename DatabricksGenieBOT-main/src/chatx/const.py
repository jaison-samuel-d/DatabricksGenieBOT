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
# Base URL for chart images (e.g. https://your-app.azurewebsites.net). When set with CHART_USE_VEGA=true, uses Vega-Lite.
# Default: QuickChart.io (reliable in Azure multi-worker; Vega-Lite uses in-memory cache that fails across workers).
CHART_BASE_URL = (os.getenv("CHART_BASE_URL") or os.getenv("APP_BASE_URL") or "").rstrip("/")
# Set to true to use Vega-Lite (requires --workers 1 in gunicorn for cache to work)
CHART_USE_VEGA = os.getenv("CHART_USE_VEGA", "").lower() in ("1", "true", "yes")
OAUTH_CONNECTION_NAME = os.getenv("OAUTH_CONNECTION_NAME", "")
WELCOME_MESSAGE = (
    "Hi! I'm your Marketing Analytics assistant. "
    "I have access to tables for attribution, spend optimization, ROI, and performance insights. "
    "Key tables include campaign attribution (bet_dme_attribution, d_me_attribution), spend curves (marginal_curve_spend), "
    "ROI by channel and region (roi_channel_deepdive), and recommendations (recommendation_table, new_insights). "
    "I can help you explore ROI, spend, pipeline, and more—just ask in plain English. What would you like to know?"
)
RECOMMENDATION_PROMPT = "Try these recommended questions:"
WAITING_MESSAGE = "Looking that up for you..."
LOGIN_REQUIRED_MESSAGE = "Please type **login** to sign in and use Genie."
SWITCHING_MESSAGE = "switch to @"
AUTH_METHOD = os.getenv("AUTH_METHOD", "service_principal")  # or "oauth" for user sign-in (video flow)

# Spaces mapping in json file
# Override via GENIE_SPACE_ID env to change space without redeploying (single space only)
__dir = Path(__file__).parent

with open(f"{__dir}/spaces.json") as f:
    SPACES = json.load(f)

# Allow env override for default space (useful for Azure Web App settings)
_genie_space_env = os.environ.get("GENIE_SPACE_ID", "").strip()
if _genie_space_env:
    SPACES["default"] = _genie_space_env
REVERSE_SPACES = {v: k for k, v in SPACES.items()}
# Default space when user has not selected one (e.g. first message)
DEFAULT_SPACE_ID = next(iter(SPACES.values()), "") if SPACES else ""
LIST_SPACES = ", ".join([f"@{space_name}" for space_name in SPACES.keys()])
SPACE_NOT_FOUND = (
    f"Genie space not found. Please use {LIST_SPACES} to specify the space."
)

# Chart dimensions for full-screen layout (Teams chat panel ~400–800px; render larger for crisp display)
CHART_WIDTH = 1400
CHART_HEIGHT = 700
CHART_PIE_SIZE = 700

# Recommendation questions shown on welcome and after each answer (edit to match your data)
RECOMMENDATION_QUESTIONS = [
    "What's the ROI by channel?",
    "Show me spend by region",
    "Which channels perform best?",
    "Compare pipeline across regions",
]
