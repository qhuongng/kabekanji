import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.config import STATIC_DIR
from server.database import init_db
from server.routes.wallpaper import router as wallpaper_router
from server.routes.config import router as config_router

DEV_MODE = os.environ.get("KABEKANJI_DEV") == "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Kanji Wallpaper",
    description="Daily kanji lock screen wallpaper generator",
    lifespan=lifespan,
)

app.include_router(wallpaper_router)
app.include_router(config_router)


# Dev-only: disable HTTP caching so a manual browser refresh always shows the latest CSS/JS
if DEV_MODE:

    @app.middleware("http")
    async def no_cache_in_dev(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
