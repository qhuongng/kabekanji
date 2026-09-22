from fastapi import APIRouter, HTTPException, Query

from server.config import DEFAULTS, SERVER_URL, SHORTCUT_URL
from server.database import create_token, get_config, save_config, token_exists

router = APIRouter(prefix="/api")


@router.get("/app-info")
async def get_app_info():
    """Frontend-facing settings that don't depend on a token"""
    return {"shortcut_url": SHORTCUT_URL}


@router.post("/tokens")
async def create_new_token():
    """Generate a fresh token seeded with the default config"""
    token = await create_token()
    return {
        "token": token,
        "config": dict(DEFAULTS),
        "wallpaper_url": f"{SERVER_URL}/api/wallpaper?token={token}",
    }


@router.get("/config")
async def read_config(token: str = Query(...)):
    """Get the current config for this token"""
    config = await get_config(token)
    if config is None:
        raise HTTPException(status_code=404, detail="unknown token")
    return config


@router.put("/config")
async def update_config(token: str = Query(...), body: dict = {}):
    """Update config for this token. Only saves known keys"""
    current = await get_config(token)
    if current is None:
        raise HTTPException(status_code=404, detail="unknown token")

    allowed_keys = set(DEFAULTS.keys())
    filtered = {k: v for k, v in body.items() if k in allowed_keys}
    merged = {**current, **filtered}
    await save_config(token, merged)
    return merged


@router.get("/config/url")
async def get_wallpaper_url(token: str = Query(...)):
    """
    Return the wallpaper URL the user should paste into their iOS Shortcut
    """
    if not await token_exists(token):
        raise HTTPException(status_code=404, detail="unknown token")
    return {"url": f"{SERVER_URL}/api/wallpaper?token={token}"}


@router.get("/config/defaults")
async def read_defaults():
    """Return the default config values for reference"""
    return DEFAULTS
