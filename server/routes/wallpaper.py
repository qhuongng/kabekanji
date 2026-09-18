from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from server.database import get_config, get_kanji_by_char
from server.services.renderer import render_preview, render_wallpaper
from server.services.selector import select_kanji

router = APIRouter(prefix="/api")


@router.get("/wallpaper")
async def get_wallpaper(token: str = Query(...)):
    """Generate and return a fresh kanji wallpaper as a PNG

    Each call picks a new kanji (respecting the recency window) and records
    it in history
    """
    config = await get_config(token)
    if config is None:
        raise HTTPException(status_code=404, detail="unknown token")

    kanji = await select_kanji(token, config)
    if not kanji:
        return Response(content="No kanji available", status_code=404)

    png_bytes = render_wallpaper(kanji, config)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": "inline; filename=kanji-wallpaper.png",
            "Cache-Control": "no-store",
        },
    )


@router.post("/preview")
async def post_preview(
    body: dict = Body(default_factory=dict),
    token: str = Query(...),
    char: str = Query(default=""),
):
    """Generate a smaller preview for the web UI config editor

    Body may contain unsaved config overrides (from the live UI). Any missing
    keys fall back to the saved config for the token. If `char` is provided,
    preview that specific kanji without recording history
    """
    saved = await get_config(token)
    if saved is None:
        raise HTTPException(status_code=404, detail="unknown token")

    config = {**saved, **(body or {})}

    if char:
        kanji = await get_kanji_by_char(char)
    else:
        kanji = await select_kanji(token, config)

    if not kanji:
        return Response(content="No kanji available", status_code=404)

    png_bytes = render_preview(kanji, config)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )
