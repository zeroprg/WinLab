"""FastAPI application entrypoint for WinLab.

Wires the migrated chat backend (text + Realtime voice + invite consume)
from `server/server.py`. The orchestration layer in `app/modules/chatbot/`
remains the target home for the next phases of the plan.
"""

from server.server import app

__all__ = ["app"]
