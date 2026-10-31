"""Loads the model bundle once at start-up and answers one request."""
from __future__ import annotations

import os
from pathlib import Path

from flood_payout import bundle as B

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.environ.get("MODEL_PATH", ROOT / "models" / "flood_payout_v2.joblib"))
BUNDLE = B.load(MODEL_PATH)

InputError = B.InputError


def estimate(form: dict) -> dict:
    """One validated form in, the homeowner-facing result out (range, middle guess, chance of $0, bands)."""
    return B.predict(BUNDLE, [form])[0]


def info() -> dict:
    return {"model_version": BUNDLE["version"], "trained_on": BUNDLE["trained_on"],
            "sklearn_version": BUNDLE["sklearn_version"]}
