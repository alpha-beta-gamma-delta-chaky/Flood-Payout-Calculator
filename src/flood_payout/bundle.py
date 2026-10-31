"""The deployable model bundle: training, saving, input validation and prediction.

Used by notebook 07 (to build the bundle) and by the web service (to answer requests), so the
service runs exactly the code that was evaluated.

A request is the homeowner's form (10 fields + water depth in inches, or no depth). The answer is
a calibrated payout range, a middle guess, the chance of a $0 building payment, the chance of each
payout band, and the coverage limit as the hard maximum.
"""
from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from . import __version__
from .features import BAND_LABELS, CATEGORIES, STATES, check_inputs, harmonise_foundation, set_categories
from .models import HGB_DEFAULT, apply_calibrator, hgb_quantile, to_dollars

MAX_COVERAGE = 250_000          # NFIP maximum building coverage for a single-family home
TAUS = (0.25, 0.5, 0.75)

# ---------------------------------------------------------------- the request schema
SCHEMA = {
    "state": dict(kind="category", values=STATES, default=None),      # optional: not used by the v2 model
    "flood_zone": dict(kind="category", values=CATEGORIES["flood_zone"], default="unknown"),
    "year_built": dict(kind="int", min=1800, max=dt.date.today().year, default=None),
    "floors": dict(kind="category", values=CATEGORIES["floors"], default="unknown"),
    "foundation": dict(kind="category", values=CATEGORIES["foundation"], default="unknown"),
    "basement": dict(kind="category", values=CATEGORIES["basement"], default="unknown"),
    "elevated": dict(kind="bool", required=True),
    "primary_residence": dict(kind="bool", required=True),
    "coverage_building": dict(kind="number", min=1_000, max=MAX_COVERAGE, required=True),
    "deductible_building": dict(kind="number", min=0, max=50_000, required=True),
    "water_depth_inches": dict(kind="number", min=0, max=240, default=None),   # None = "I don't know"
}


class InputError(ValueError):
    def __init__(self, errors: dict):
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))
        self.errors = errors


def validate(form: dict) -> dict:
    """Check one request against SCHEMA; return a clean copy or raise InputError listing every problem."""
    unknown = set(form) - set(SCHEMA)
    errors, clean = {}, {}
    for f in sorted(unknown):
        errors[f] = "unknown field"
    for name, spec in SCHEMA.items():
        v = form.get(name, None)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            if spec.get("required"):
                errors[name] = "required"
            clean[name] = spec.get("default")
            continue
        kind = spec["kind"]
        try:
            if kind == "category":
                v = str(v).strip()
                v = v.upper() if name == "state" else v
                if v not in spec["values"]:
                    raise ValueError(f"must be one of {spec['values']}")
            elif kind == "bool":
                if isinstance(v, str):
                    if v.lower() not in ("true", "false", "1", "0", "yes", "no"):
                        raise ValueError("must be true or false")
                    v = v.lower() in ("true", "1", "yes")
                v = bool(v)
            else:
                v = float(v)
                if not math.isfinite(v):
                    raise ValueError("must be a number")
                if kind == "int":
                    v = int(round(v))
                if v < spec["min"] or v > spec["max"]:
                    raise ValueError(f"must be between {spec['min']} and {spec['max']}")
        except (TypeError, ValueError) as exc:
            errors[name] = str(exc)
            continue
        clean[name] = v
    if errors:
        raise InputError(errors)
    return clean


def to_frame(forms: list[dict]) -> pd.DataFrame:
    """Map validated forms to the model's feature columns (same preprocessing as in training).

    The homeowner's depth is water inside the house in inches, i.e. the quantity FEMA records as
    interiorWaterDepth, and it is in inches, so every depth column gets the same value and the source
    flag says "interior". An unknown depth leaves the depth columns missing with flag "missing".
    """
    rows = []
    for f in forms:
        d = f["water_depth_inches"]
        r = {k: f[k] for k in ("state", "flood_zone", "year_built", "floors", "foundation", "basement",
                               "coverage_building", "deductible_building")}
        r["year_built"] = np.nan if r["year_built"] is None else float(r["year_built"])
        r["elevated"] = float(f["elevated"])
        r["primary_residence"] = float(f["primary_residence"])
        r["foundation_h"] = harmonise_foundation(r["foundation"], r["basement"], r["elevated"])
        for c in ("depth_rule_in", "depth_interior_in", "depth_best_in", "depth_interior_clean"):
            r[c] = np.nan if d is None else float(d)
        r["depth_source"] = "missing" if d is None else "interior"
        rows.append(r)
    return set_categories(pd.DataFrame(rows))


# ---------------------------------------------------------------- training
def _fit_path(data, y, features, params, seed=0, band=None):
    check_inputs(features)
    X, ylog = data[features], np.log1p(y)
    out = {f"q{q}": hgb_quantile(q, params, seed=seed).fit(X, ylog) for q in TAUS}
    clf = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=seed, **HGB_DEFAULT)
    out["bands"] = clf.fit(X, band)
    return out


def train_bundle(data: pd.DataFrame, y: np.ndarray, band: np.ndarray, features_depth: list[str],
                 features_nodepth: list[str], params: dict, calibration: dict, metrics: dict,
                 notes: str = "") -> dict:
    """Fit the final models on all development claims and pack everything the service needs.

    calibration: {"with_depth": {...}, "no_depth": {...}}, each holding the range calibrator
    (from fit_calibrator on out-of-fold predictions) and "d_mid", the shift for the middle guess.
    """
    return {
        "version": __version__,
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "trained_on": f"{len(y):,} NFIP single-family claims, losses 2010-2024",
        "features": {"with_depth": features_depth, "no_depth": features_nodepth},
        "params": params,
        "models": {"with_depth": _fit_path(data, y, features_depth, params, band=band),
                   "no_depth": _fit_path(data, y, features_nodepth, params, band=band)},
        "calibration": calibration,
        "metrics": metrics,
        "band_labels": BAND_LABELS,
        "notes": notes,
    }


def save(bundle: dict, path: Path):
    joblib.dump(bundle, path, compress=3)


def load(path: Path) -> dict:
    return joblib.load(path)


# ---------------------------------------------------------------- prediction
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
