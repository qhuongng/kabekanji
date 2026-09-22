from flask import Blueprint, Response, abort, request

from server.database import get_config, get_kanji_by_char
from server.services.renderer import render_preview, render_wallpaper
from server.services.selector import select_kanji

wallpaper_bp = Blueprint("wallpaper", __name__, url_prefix="/api")


@wallpaper_bp.get("/wallpaper")
def get_wallpaper():
    """Generate and return a fresh kanji wallpaper as a PNG

    Each call picks a new kanji (respecting the recency window) and records
    it in history
    """
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")

    config = get_config(token)
    if config is None:
        abort(404, description="unknown token")

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

    Body may contain unsaved config overrides (from the live UI). Any missing
    keys fall back to the saved config for the token. If `char` is provided,
    preview that specific kanji without recording history
    """
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")

    char = request.args.get("char", "")

    saved = get_config(token)
    if saved is None:
        abort(404, description="unknown token")

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
