import os

from flask import Flask

from server.config import STATIC_DIR
from server.database import init_db
from server.routes.config import config_bp
from server.routes.wallpaper import wallpaper_bp

DEV_MODE = os.environ.get("KABEKANJI_DEV") == "1"


def create_app() -> Flask:
    # static_url_path="" serves static files at the site root (e.g. /style.css -> static/style.css)
    # A directory index (index.html) is served automatically at "/"
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="",
    )

    init_db()

    app.register_blueprint(config_bp)
    app.register_blueprint(wallpaper_bp)

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    if DEV_MODE:
        # Disable HTTP caching so a manual browser refresh always shows the latest CSS/JS
        @app.after_request
        def no_cache(response):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            return response

    return app


app = create_app()
