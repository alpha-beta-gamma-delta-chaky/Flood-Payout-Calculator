"""Infrastructure: reads the model bundle from disk. The only code in app/ that touches the model file.

Nothing is loaded when this module is imported. create_app (app/main.py) calls load_bundle once at start-up
and hands the bundle to the service layer.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from flood_payout import bundle as B


@lru_cache(maxsize=4)
def load_bundle(path: Path) -> dict:
    """Load the bundle at `path`. Cached, so creating several apps (the tests do) reads the file once."""
    return B.load(Path(path))


def info(bundle: dict) -> dict:
    """What /health reports about the loaded model."""
    return {"model_version": bundle["version"], "trained_on": bundle["trained_on"],
            "sklearn_version": bundle["sklearn_version"]}
