"""Export token store for CSV/Excel download links."""
import csv
import io
import logging
import os
import time
import uuid

# Log
logger = logging.getLogger(__name__)

# In-memory cache: token -> {content: bytes, filename: str, format: str, created: float}
_EXPORT_CACHE: dict[str, dict] = {}
_TOKEN_TTL_SECONDS = 300  # 5 minutes


def create_export_token(columns: list[str], rows: list[list], fmt: str = "csv") -> str:
    """Create a one-time token for export. Returns token string."""
    content = _generate_excel(columns, rows)
    filename = "export.csv" if fmt == "csv" else "export_data.csv"

    token = str(uuid.uuid4())
    _EXPORT_CACHE[token] = {
        "content": content,
        "filename": filename,
        "format": fmt,
        "created": time.time(),
    }
    return token


def _generate_excel(columns: list[str], rows: list[list]) -> bytes:
    """Generate Excel-compatible CSV (UTF-8 BOM for Excel)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([str(v) if v is not None else "" for v in row])
    return output.getvalue().encode("utf-8-sig")


def get_export(token: str) -> tuple[bytes, str] | None:
    """Retrieve export content by token. Returns (content, filename) or None if expired."""
    entry = _EXPORT_CACHE.get(token)
    if not entry:
        return None
    if time.time() - entry["created"] > _TOKEN_TTL_SECONDS:
        del _EXPORT_CACHE[token]
        return None
    return entry["content"], entry["filename"]


def get_base_url() -> str:
    """Get base URL for export links."""
    url = os.getenv("APP_URL") or os.getenv("WEBSITE_HOSTNAME", "http://localhost:3978")
    if url and not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")
