"""
Run the FastAPI server in dev mode.

Usage:
    python scripts/dev.py

- Uvicorn restarts the server whenever a Python file under server/ changes.
- Static files (HTML/CSS/JS) are served with Cache-Control: no-store, so a
  manual browser refresh (F5) always picks up the latest version — no need
  for Ctrl+Shift+R.
"""

import os
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent

# Flag consumed by server.main to enable the no-cache middleware
os.environ["KABEKANJI_DEV"] = "1"


if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT / "server")],
        app_dir=str(ROOT),
    )
