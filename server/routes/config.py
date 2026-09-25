from flask import Blueprint, abort, jsonify, request

from server.config import DEFAULTS, SHORTCUT_URL
from server.database import create_token, get_config, save_config

config_bp = Blueprint("config", __name__, url_prefix="/api")


@config_bp.get("/app-info")
def get_app_info():
    """Frontend-facing settings that don't depend on a token"""
    return jsonify({"shortcut_url": SHORTCUT_URL})


@config_bp.post("/tokens")
def create_new_token():
    """Generate a fresh token seeded with the default config"""
    token = create_token()
    return jsonify({"token": token, "config": dict(DEFAULTS)})


@config_bp.get("/config")
def read_config():
    """Get the current config for this token"""
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")
    config = get_config(token)
    if config is None:
        abort(404, description="unknown token")
    return jsonify(config)


@config_bp.put("/config")
def update_config():
    """Upsert config for this token
    Creates the row on first save if the token was minted but never saved before
    Only known keys are stored
    """
    token = request.args.get("token")
    if not token:
        abort(400, description="token required")

    current = get_config(token) or dict(DEFAULTS)
    body = request.get_json(silent=True) or {}
    allowed_keys = set(DEFAULTS.keys())
    filtered = {k: v for k, v in body.items() if k in allowed_keys}
    merged = {**current, **filtered}
    save_config(token, merged)
    return jsonify(merged)


@config_bp.get("/config/defaults")
def read_defaults():
    """Return the default config values for reference"""
    return jsonify(DEFAULTS)
