"""Flood payout calculator web service.

The model code lives in src/flood_payout (shared with retraining). Putting src on the path here means
`uvicorn app.main:app` and the tests both find it without extra setup.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
