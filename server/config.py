import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
FONTS_DIR = BASE_DIR / "fonts"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "kanji.db"

# Base URL where this server is reachable, used to build the wallpaper API URL
# shown in the UI (which the user pastes into their iOS Shortcut)
# Explicit SERVER_URL > Render's RENDER_EXTERNAL_URL > localhost
SERVER_URL = (
    os.environ.get("SERVER_URL")
    or os.environ.get("RENDER_EXTERNAL_URL")
    or "http://localhost:8000"
).rstrip("/")

# Default wallpaper settings (iPhone 17)
DEFAULTS = {
    "screen_width": 1206,
    "screen_height": 2622,
    "top_margin": 400,
    "bottom_margin": 300,
    "recency_window": 5,
    "bg_color": "#121214",
    "text_color": "#F0F0F5",
    "show_gothic": True,
    "show_mincho": True,
    "show_handwritten": True,
    "show_sinovi": True,
    "show_vocabulary": True,
}

FONTS = {
    "stroke_order": FONTS_DIR / "KanjiStrokeOrders.ttf",
    "gothic": FONTS_DIR / "NotoSansJP-Regular.ttf",
    "serif_bold": FONTS_DIR / "NotoSerifJP-Bold.ttf",
    "mincho": FONTS_DIR / "NotoSerifJP-Regular.ttf",
    "handwritten": FONTS_DIR / "HitoriGothic-Regular.ttf",
    # Serif for Vietnamese/Latin
    "serif": FONTS_DIR / "CrimsonPro-Regular.ttf",
}
