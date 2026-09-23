from flask import Blueprint, Response, abort, request

from server.config import DEFAULTS
from server.database import get_config, get_kanji_by_char
from server.services.renderer import render_preview, render_wallpaper
from server.services.selector import select_kanji

wallpaper_bp = Blueprint("wallpaper", __name__, url_prefix="/api")


@wallpaper_bp.get("/wallpaper")
def get_wallpaper():
    """Generate and return a fresh kanji wallpaper as a PNG

    Each call picks a new kanji (respecting the recency window) and records it in history
    If the token has no saved config yet (e.g. user installed the shortcut before clicking Save), render with defaults
    """
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")

    config = get_config(token) or dict(DEFAULTS)

    kanji = select_kanji(token, config)
    if not kanji:
        return "No kanji available", 404

    png_bytes = render_wallpaper(kanji, config)

    return Response(
        png_bytes,
        mimetype="image/png",
        headers={
            "Content-Disposition": "inline; filename=kanji-wallpaper.png",
            "Cache-Control": "no-store",
        },
    )


@wallpaper_bp.post("/preview")
def post_preview():
    """Generate a smaller preview for the web UI config editor

    Body may contain unsaved config overrides (from the live UI). Missing
    keys fall back to the saved config for the token, or DEFAULTS if the
    token hasn't been saved yet. If `char` is provided, preview that
    specific kanji without recording history
    """
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")

    char = request.args.get("char", "")

    saved = get_config(token) or dict(DEFAULTS)
    body = request.get_json(silent=True) or {}
    config = {**saved, **body}

    if char:
        kanji = get_kanji_by_char(char)
    else:
        kanji = select_kanji(token, config)

    if not kanji:
        return "No kanji available", 404

    png_bytes = render_preview(kanji, config)

    return Response(
        png_bytes,
        mimetype="image/png",
        headers={"Cache-Control": "no-store"},
    )
