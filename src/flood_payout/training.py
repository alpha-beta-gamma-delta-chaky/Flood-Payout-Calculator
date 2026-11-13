"""Training: fit the final models and pack them into a bundle. Not used by the web service at request time.

Used by notebook 07 and retrain.py. The bundle it returns is read back by flood_payout.inference.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from . import __version__
from .features import BAND_LABELS, check_inputs
from .inference import TAUS
from .models import HGB_DEFAULT, hgb_quantile


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
