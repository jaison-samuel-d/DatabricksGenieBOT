# Entry point for gunicorn (--chdir src app:app)
from chatx.app import app

__all__ = ["app"]
