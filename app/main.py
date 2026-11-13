"""Flood payout calculator: FastAPI service. This file is the API layer: HTTP in, HTTP out.

    GET  /health         liveness and model version (container health check, smoke tests)
    POST /api/estimate   one form as JSON -> payout range, middle guess, chance of $0, band probabilities
    GET  /docs           automatic API documentation
    GET  /               the React web page (built into frontend/dist, or STATIC_DIR in the container)

Run locally from the repository root:   uvicorn app.main:app --port 8000

The layers, top to bottom (each one only uses the ones below it):
    app/main.py, app/schema.py    API: routes, request and response shapes, rate limit, errors -> status codes
    app/service.py                Service: the estimate use case, counters, timing log
    src/flood_payout/             Model: input checks, features, prediction
    app/config.py, app/model.py   Infrastructure: settings from the environment, loading the model file

Rate limit: per client IP (settings.rate_limit, default 30/minute). Behind Caddy the client IP comes from the
X-Forwarded-For header, so uvicorn runs with --proxy-headers; only Caddy can reach the app container.
No personal data is stored; only anonymous counts are logged.
"""
import logging
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import model
from app.config import Settings
from app.schema import EstimateRequest, EstimateResponse
from app.service import EstimateService, InputError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def create_app(settings: Settings | None = None, **overrides) -> FastAPI:
    """Build the app. Settings come from the environment unless given; keyword arguments replace single
    settings, for example create_app(rate_limit="3/minute", static_dir=None) in the tests."""
    settings = replace(settings or Settings.from_env(), **overrides)

    # The model is loaded here, once, when the app is created, and kept on app.state for the routes.
    service = EstimateService(model.load_bundle(settings.model_path))
    app = FastAPI(title="Flood Payout Calculator", version=service.info()["model_version"])
    app.state.settings = settings
    app.state.service = service
    app.state.limiter = Limiter(key_func=get_remote_address)

    @app.exception_handler(RateLimitExceeded)
    async def too_many_requests(_: Request, exc: RateLimitExceeded):
        return JSONResponse({"error": "rate limit", "detail": f"Too many requests ({exc.detail}). Try again soon."},
                            status_code=429, headers={"Retry-After": "60"})

    @app.exception_handler(InputError)
    async def rejected_by_model(_: Request, exc: InputError):      # same shape as a Pydantic 422
        detail = [{"loc": ["body", field], "msg": msg} for field, msg in exc.errors.items()]
        return JSONResponse({"detail": detail}, status_code=422)

    @app.get("/health")
    def health(request: Request):
        return {"status": "ok", **request.app.state.service.info()}

    @app.post("/api/estimate", response_model=EstimateResponse)
    @app.state.limiter.limit(settings.rate_limit)
    def estimate(request: Request, body: EstimateRequest):
        return request.app.state.service.estimate(body.model_dump())

    static_dir = settings.static_dir
    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")    # last: API routes win
    else:
        @app.get("/")
        def root(request: Request):
            return {"message": "API only: the web page is not built. See /docs.",
                    **request.app.state.service.info()}

    return app


app = create_app()
