"""
Run the Flask server in dev mode

Usage:
    python scripts/dev.py

- Flask restarts the server whenever a Python file under server/ changes
- Static files (HTML/CSS/JS) are served with Cache-Control: no-store, so a
  manual browser refresh (F5) always picks up the latest version
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Make `server` importable when running this script directly
sys.path.insert(0, str(ROOT))

# Flag consumed by server.main to enable the no-cache middleware
os.environ["KABEKANJI_DEV"] = "1"


if __name__ == "__main__":
    from server.main import app

    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True,
        use_reloader=True,
        extra_files=[str(p) for p in (ROOT / "server").rglob("*.py")],
    )
