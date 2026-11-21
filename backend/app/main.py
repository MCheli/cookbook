"""FastAPI application: the API under /api and the built Vue app for everything else."""

from __future__ import annotations

import html
import json
import logging
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from app.config import check_production_settings, settings
from app.core.headers import SecurityHeadersMiddleware
from app.db.session import AsyncSessionLocal, engine
from app.demo import DemoReadOnlyMiddleware, NoIndexMiddleware
from app.routers import account, ai, auth, grocery, health, recipes

# The Home Screen web app manifest needs its JSON type (Safari ignores it otherwise).
mimetypes.add_type("application/manifest+json", ".webmanifest")

logger = logging.getLogger("cookbook")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")


async def _check_demo() -> None:
    from app.demo import check_demo_database, check_demo_settings

    check_demo_settings()
    async with AsyncSessionLocal() as db:
        await check_demo_database(db)
    logger.info("Demo mode: read-only, visitors see %s.", settings.DEMO_USER_EMAIL)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    errors, warnings = check_production_settings(settings)
    for warning in warnings:
        logger.warning("Insecure production setting: %s", warning)
    if errors:
        for error in errors:
            logger.error("INSECURE PRODUCTION SETTING: %s", error)
        raise RuntimeError("FATAL: insecure production settings: " + " ".join(errors))
    if settings.DEMO_MODE:
        await _check_demo()
    else:
        from app.services.seed import run_startup_seed

        await run_startup_seed()
    yield
    await engine.dispose()


app = FastAPI(
    title="Cookbook",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.docs_enabled else None,
    openapi_url="/api/openapi.json" if settings.docs_enabled else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.JWT_SECRET,
    session_cookie="cookbook_oauth_state",
    https_only=settings.COOKIE_SECURE,
    same_site="lax",
)
app.add_middleware(DemoReadOnlyMiddleware)
app.add_middleware(NoIndexMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def _unhandled(_request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(account.router, prefix="/api/me", tags=["account"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(grocery.router, prefix="/api", tags=["grocery"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])

STATIC_DIR = Path(os.environ.get("COOKBOOK_STATIC_DIR", "/app/static"))
_RECIPE_PATH = re.compile(r"^r/([a-z0-9-]{1,160})/?$")


def static_file(static_dir: Path, full_path: str) -> Path | None:
    """The file under static_dir that full_path names, or None ('..%2f' must not escape)."""
    root = static_dir.resolve()
    try:
        candidate = (root / full_path).resolve()
    except (OSError, ValueError):
        return None
    if candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    return None


async def _recipe_head(slug: str) -> str | None:
    """Title, description, Open Graph and schema.org JSON-LD for a public recipe page, so links
    preview well and search engines read the recipe. Private recipes get nothing."""
    from app.models import Recipe, User
    from app.services import recipes as svc

    async with AsyncSessionLocal() as db:
        recipe = await db.scalar(select(Recipe).where(Recipe.slug == slug))
        if not recipe or not svc.can_view(recipe, None):
            return None
        owner = await db.get(User, recipe.owner_id)
        data = svc.jsonld(recipe, owner.display_name if owner else None)
    title = html.escape(f"{recipe.title} · Cookbook")
    desc = html.escape(
        recipe.description
        or f"{svc.method_label(recipe.method)} · {recipe.servings_text or ''} servings · "
        f"{', '.join(i.item for i in recipe.ingredients[:6])}"
    )
    ld = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (
        f"<title>{title}</title>"
        f'<meta name="description" content="{desc}">'
        f'<meta property="og:title" content="{html.escape(recipe.title)}">'
        f'<meta property="og:description" content="{desc}">'
        f'<meta property="og:type" content="article">'
        f'<script type="application/ld+json">{ld}</script>'
    )


if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = static_file(STATIC_DIR, full_path)
        if candidate:
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        m = _RECIPE_PATH.match(full_path)
        if m and not settings.DEMO_MODE:
            head = await _recipe_head(m.group(1))
            if head:
                page = index.read_text(encoding="utf-8")
                page = re.sub(r"<title>.*?</title>", "", page, count=1, flags=re.S)
                return HTMLResponse(page.replace("</head>", head + "</head>", 1))
        return FileResponse(index)

else:
    logger.info("Static dir %s missing; SPA not mounted (dev mode).", STATIC_DIR)
