from fastapi import APIRouter, Query

from server.database import get_config, save_config
from server.config import DEFAULTS, SERVER_URL

router = APIRouter(prefix="/api/config")


@router.get("")
async def read_config(token: str = Query(default="default")):
    """Get the current config for this token"""
    config = await get_config(token)
    return config


@router.put("")
async def update_config(token: str = Query(default="default"), body: dict = {}):
    """Update config for this token. Only saves known keys"""
    allowed_keys = set(DEFAULTS.keys())
    filtered = {k: v for k, v in body.items() if k in allowed_keys}
    current = await get_config(token)
    merged = {**current, **filtered}
    await save_config(token, merged)
    return merged


@router.get("/url")
async def get_wallpaper_url(token: str = Query(default="default")):
    """
    Return the wallpaper URL the user should paste into their iOS Shortcut
    """
    return {
        "url": f"{SERVER_URL}/api/wallpaper?token={token}"
    }


@router.get("/defaults")
async def read_defaults():
    """Return the default config values for reference"""
    return DEFAULTS
