"""Infrastructure: every setting the web service reads from the environment, in one place.

    MODEL_PATH   the model bundle to load          default: models/flood_payout_v2.joblib
    STATIC_DIR   the folder with the built page    default: frontend/dist (the Docker image sets /srv/static)
    RATE_LIMIT   estimates allowed per client      default: 30/minute

Nothing else in app/ reads os.environ. Tests build a Settings object directly, or pass overrides to create_app.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    model_path: Path = ROOT / "models" / "flood_payout_v2.joblib"
    static_dir: Path | None = ROOT / "frontend" / "dist"
    rate_limit: str = "30/minute"

    @classmethod
    def from_env(cls) -> Settings:
        """Read the three settings from environment variables, falling back to the defaults above."""
        return cls(
            model_path=Path(os.environ.get("MODEL_PATH", cls.model_path)),
            static_dir=Path(os.environ.get("STATIC_DIR", cls.static_dir)),
            rate_limit=os.environ.get("RATE_LIMIT", cls.rate_limit),
        )
