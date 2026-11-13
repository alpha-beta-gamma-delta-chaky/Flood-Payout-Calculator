"""Preprocessing: the request schema, input checks, and the mapping from a form to model features.

This is the single place where a homeowner's form becomes the columns the model expects. It uses the same
shared definitions as training (flood_payout.features: the category lists, harmonise_foundation and
set_categories, which training reaches through features.prepare), so serving and training cannot drift apart.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from .features import CATEGORIES, STATES, harmonise_foundation, set_categories

MAX_COVERAGE = 250_000          # NFIP maximum building coverage for a single-family home

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
