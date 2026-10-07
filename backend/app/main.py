import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, catalog, discover, findings, investigations, watches
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.services.recovery import fail_orphaned_investigations
from app.services.scheduler import scheduler_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app.request")

settings = get_settings()

# Fail fast rather than silently serving a forgeable-token production
# deployment — the dev default is fine locally (that's the whole point of
# having a zero-config default), but it must never reach a real deployment.
# Also rejects an empty secret (e.g. `JWT_SECRET=` left blank in a copied
# .env) — that's not "unset", it's an even weaker secret than the default.
if settings.ENV == "production" and (
    not settings.JWT_SECRET or settings.JWT_SECRET == "dev-only-insecure-secret-change-me"
):
    raise RuntimeError(
        "JWT_SECRET is unset, empty, or still the development default while ENV=production. "
        "Set a real secret via the JWT_SECRET environment variable before deploying."
    )

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await fail_orphaned_investigations()
    except Exception:
        logging.getLogger("app.recovery").exception("Could not clean up unfinished investigations")
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Structured per-request logging (request id, latency, status) and a
    small set of standard security response headers. Deliberately simple —
    no external APM dependency — but gives every request a correlatable id,
    which is the minimum needed to debug a production incident from logs
    alone."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "[%s] %s %s failed after %.1fms", request_id, request.method, request.url.path, duration_ms
            )
            # Answer here rather than re-raising: an exception that escapes to
            # Starlette's outermost error handler is answered without CORS
            # headers, which the browser then reports as a CORS failure and
            # hides the real 500 from the frontend.
            response = JSONResponse(status_code=500, content={"detail": "Internal server error."})
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "[%s] %s %s -> %s (%.1fms)",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(RequestObservabilityMiddleware)

# Added last so it is the outermost middleware: every response, including
# the 500s produced above, carries CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # HTTPException (404, 401, 409, ...) is handled by Starlette's default
    # handler before this ever runs — this only catches genuine bugs, so it
    # must never leak internals (stack traces, DB errors) to the client.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(investigations.router, prefix=settings.API_PREFIX)
app.include_router(discover.router, prefix=settings.API_PREFIX)
app.include_router(findings.router, prefix=settings.API_PREFIX)
app.include_router(catalog.router, prefix=settings.API_PREFIX)
app.include_router(watches.router, prefix=settings.API_PREFIX)


@app.get(f"{settings.API_PREFIX}/health")
async def health():
    """Reports genuine subsystem status — used by the frontend's mission
    status strip. Never fabricated: the LLM flag reflects whether a Groq
    key is actually configured, and the database flag reflects a real
    query, not an assumption."""
    db_ok = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "database": db_ok,
        "llm_available": bool(settings.GROQ_API_KEY),
        "nasa_power": True,  # NASA_POWER requires no credentials and is always registered; this reflects that the adapter is configured, not a live reachability probe (which would add latency to every poll)
    }
