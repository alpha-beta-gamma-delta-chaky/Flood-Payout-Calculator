"""Flood payout calculator: FastAPI service.

    GET  /health         liveness and model version (container health check, smoke tests)
    POST /api/estimate   one form as JSON -> payout range, middle guess, chance of $0, band probabilities
    GET  /docs           automatic API documentation
    GET  /               the React web page (built into frontend/dist, or STATIC_DIR in the container)

Run locally from the repository root:   uvicorn app.main:app --port 8000

Rate limit: per client IP, RATE_LIMIT (default 30/minute). Behind Caddy the client IP comes from the
X-Forwarded-For header, so uvicorn runs with --proxy-headers; only Caddy can reach the app container.
No personal data is stored; only anonymous counts are logged.
"""
import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import model
from app.schema import EstimateRequest, EstimateResponse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(os.environ.get("STATIC_DIR", ROOT / "frontend" / "dist"))
DEFAULT_RATE_LIMIT = os.environ.get("RATE_LIMIT", "30/minute")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("flood_payout")


def create_app(rate_limit: str = DEFAULT_RATE_LIMIT, static_dir: Path | None = STATIC_DIR) -> FastAPI:
    app = FastAPI(title="Flood Payout Calculator", version=model.info()["model_version"])
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    counts = {"requests": 0, "invalid": 0, "no_depth": 0}

    @app.exception_handler(RateLimitExceeded)
    async def too_many_requests(_: Request, exc: RateLimitExceeded):
        return JSONResponse({"error": "rate limit", "detail": f"Too many requests ({exc.detail}). Try again soon."},
                            status_code=429, headers={"Retry-After": "60"})

    @app.get("/health")
    def health():
        return {"status": "ok", **model.info()}

    @app.post("/api/estimate", response_model=EstimateResponse)
    @limiter.limit(rate_limit)
    def estimate(request: Request, body: EstimateRequest):
        t = time.perf_counter()
        counts["requests"] += 1
        try:
            result = model.estimate(body.model_dump())
        except model.InputError as exc:        # the model's own checks, a second line behind Pydantic
            counts["invalid"] += 1
            detail = [{"loc": ["body", field], "msg": msg} for field, msg in exc.errors.items()]
            return JSONResponse({"detail": detail}, status_code=422)
        counts["no_depth"] += int(not result["depth_used"])
        log.info("estimate ok in %.0f ms | counts %s", 1000 * (time.perf_counter() - t), counts)
        return result

    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")    # last: API routes win
    else:
        @app.get("/")
        def root():
            return {"message": "API only: the web page is not built. See /docs.", **model.info()}

    return app


app = create_app()
