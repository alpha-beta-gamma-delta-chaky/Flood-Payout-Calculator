"""Inference: load a saved bundle and answer requests with it. No training code in here.

A request is the homeowner's form (10 fields + water depth in inches, or no depth). The answer is
a calibrated payout range, a middle guess, the chance of a $0 building payment, the chance of each
payout band, and the coverage limit as the hard maximum.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .models import apply_calibrator, to_dollars
from .preprocessing import MAX_COVERAGE, to_frame, validate

TAUS = (0.25, 0.5, 0.75)        # the three quantile models in every bundle: low, middle, high


def load(path: Path) -> dict:
    return joblib.load(path)


def predict_frame(bundle: dict, frame: pd.DataFrame, path: str) -> dict:
    """Arrays of calibrated low / middle / high, p_zero and band probabilities for one model path."""
    m, cal = bundle["models"][path], bundle["calibration"][path]
    X = frame[bundle["features"][path]]
    cap = np.minimum(np.nan_to_num(frame["coverage_building"].to_numpy(float), nan=MAX_COVERAGE), MAX_COVERAGE)
    raw = {q: to_dollars(m[f"q{q}"].predict(X), cap) for q in TAUS}
    lo, hi = apply_calibrator(raw[0.25], raw[0.75], cap, cal["range"])
    mid = to_dollars(np.log1p(raw[0.5]) + cal["d_mid"], cap)
    mid = np.clip(mid, lo, hi)
    proba = np.zeros((len(X), 5))
    proba[:, m["bands"].classes_] = m["bands"].predict_proba(X)
    return {"low": lo, "middle": mid, "high": hi, "cap": cap, "p_zero": proba[:, 0], "bands": proba}


def predict(bundle: dict, forms: list[dict]) -> list[dict]:
    """Validate requests and answer each with the homeowner-facing result."""
    clean = [validate(f) for f in forms]
    out = [None] * len(clean)
    for path, sel in (("with_depth", [i for i, f in enumerate(clean) if f["water_depth_inches"] is not None]),
                      ("no_depth", [i for i, f in enumerate(clean) if f["water_depth_inches"] is None])):
        if not sel:
            continue
        r = predict_frame(bundle, to_frame([clean[i] for i in sel]), path)
        for j, i in enumerate(sel):
            lo, mid, hi, cap = (float(round(r[k][j], -2)) for k in ("low", "middle", "high", "cap"))
            out[i] = {
                "low": lo, "middle": mid, "high": hi, "coverage_limit": cap,
                "chance_of_zero": round(float(r["p_zero"][j]), 3),
                "band_probabilities": {lab: round(float(p), 3) for lab, p in zip(bundle["band_labels"], r["bands"][j])},
                "depth_used": path == "with_depth",
                "model_version": bundle["version"],
                "message": (f"About half of past claims like yours were paid between ${lo:,.0f} and ${hi:,.0f} "
                            f"for the building. Your policy cannot pay more than ${cap:,.0f}. "
                            f"About {100 * r['p_zero'][j]:.0f}% of similar claims were paid nothing for the "
                            "building. This is typical for claims like yours, not a promise: the adjuster "
                            "decides the final amount."),
            }
    return out
