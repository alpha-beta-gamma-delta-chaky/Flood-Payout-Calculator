"""Feature definitions shared by the notebooks and the deployed service.

Everything a model may see is defined here, so the notebooks, the final model and the web service
use exactly the same columns, categories and leakage rules.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- the form a homeowner fills in
FORM10 = ["state", "flood_zone", "year_built", "floors", "foundation", "basement",
          "elevated", "primary_residence", "coverage_building", "deductible_building"]
DEPTH_DEFAULT = "depth_rule_in"          # Phase 1 default: waterDepth with the "<= 8 means feet" rule

STATES = ['AK', 'AL', 'AR', 'AS', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA', 'GU', 'HI', 'IA', 'ID', 'IL',
          'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH',
          'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN', 'TX', 'UN', 'UT', 'VA',
          'VI', 'VT', 'WA', 'WI', 'WV', 'WY']

CATEGORIES = {
    "state": STATES,
    "flood_zone": ["A", "V", "X", "D", "unknown"],
    "floors": ["1", "2", "3+", "split_level", "mobile_home", "townhouse_3+", "unknown"],
    "foundation": ["slab", "basement", "crawlspace", "elevated_open", "elevated_enclosed_piles",
                   "elevated_enclosed_walls", "unknown"],
    "basement": ["none", "finished_basement", "unfinished_basement", "crawlspace", "subgrade_crawlspace",
                 "unknown"],
    "foundation_h": ["slab", "basement", "crawlspace", "elevated", "slab_or_other", "unknown"],
    "depth_source": ["interior", "rule", "missing"],
}

# ---------------------------------------------------------------- leakage rules
# Allow-list: only these columns may ever reach a model. Anything else is rejected, whatever its name.
ALLOWED_INPUTS = set(FORM10) | {
    "foundation_h",                                                     # harmonised foundation (derived)
    "depth_rule_in", "depth_raw", "depth_interior_in", "depth_best_in", "depth_source",   # depth versions
    "depth_interior_clean",                                             # interior depth, placeholder zeros removed
    "loss_year", "loss_month",                                          # date of the flood (user knows it)
    "storm_county_events_4d", "storm_state_tropical_4d", "storm_county_floods_prev_year",  # NOAA merge
    "county_payout_history",                                            # computed from training floods only
}
# Deny-list on top: adjuster-only and payment columns (filled in after the visit).
FORBIDDEN_PREFIXES = ("post_", "paid")
FORBIDDEN_EXACT = {"id", "flood_group", "floodEvent", "split", "loss_date"}

NICE = {"depth_rule_in": "water depth", "depth_interior_in": "interior water depth",
        "depth_interior_clean": "water depth inside", "depth_raw": "water depth (raw)",
        "depth_best_in": "water depth (combined)", "depth_source": "depth source flag",
        "coverage_building": "building coverage", "state": "state", "basement": "basement type",
        "year_built": "year built", "elevated": "raised building", "deductible_building": "deductible",
        "foundation": "foundation type", "foundation_h": "foundation (harmonised)", "floors": "number of floors",
        "primary_residence": "primary residence", "flood_zone": "flood zone", "loss_year": "loss year",
        "loss_month": "loss month", "county_payout_history": "county payout history"}


class LeakageError(ValueError):
    """Raised when a column that is not allowed would reach a model."""


def check_inputs(features) -> None:
    """Fail loudly if any feature is not on the allow-list or looks like an adjuster/payment field."""
    bad = [f for f in features
           if f not in ALLOWED_INPUTS or f.startswith(FORBIDDEN_PREFIXES) or f in FORBIDDEN_EXACT]
    if bad:
        raise LeakageError(f"not allowed as model inputs: {bad}")


# ---------------------------------------------------------------- preprocessing
def harmonise_foundation(foundation, basement, elevated) -> str:
    """One foundation field that repairs FEMA's old/new coding split (same rule as Phase 1)."""
    if foundation != "unknown":
        return "elevated" if str(foundation).startswith("elevated") else foundation
    if basement in ("finished_basement", "unfinished_basement"):
        return "basement"
    if basement in ("crawlspace", "subgrade_crawlspace"):
        return "crawlspace"
    if elevated == 1:
        return "elevated"
    return "slab_or_other" if basement == "none" else "unknown"


def clean_interior_depth(interior, rule):
    """Interior water depth (inches above the floor) with FEMA's placeholder zeros removed.

    An interior depth of 0 recorded together with a positive waterDepth is a placeholder, not "no water
    inside": those claims have a median payout of $52,500 and only 3% are paid $0. They become missing
    ("not recorded"). A 0 is kept when waterDepth is also 0 or missing (median payout $10,400).
    """
    interior = pd.Series(interior, dtype=float).to_numpy()
    rule = pd.Series(rule, dtype=float).to_numpy()
    placeholder = (interior == 0) & (rule > 0)
    return np.where(placeholder, np.nan, interior)


def set_categories(data: pd.DataFrame) -> pd.DataFrame:
    """Cast categorical columns to pandas categoricals with the fixed category lists above.

    Fixed lists mean a model trained here and a request arriving at the web service map
    every category to the same code; an unseen value becomes missing instead of a crash.
    """
    for col, cats in CATEGORIES.items():
        if col in data:
            data[col] = pd.Categorical(data[col].astype("string").fillna("unknown" if col != "state" else pd.NA),
                                       categories=cats)
    return data


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns and fixed categories to a copy of the modelling table."""
    out = df.copy()
    out["depth_interior_clean"] = clean_interior_depth(out["depth_interior_in"], out["depth_rule_in"])
    out["foundation_h"] = [harmonise_foundation(f, b, e)
                           for f, b, e in zip(out["foundation"], out["basement"], out["elevated"])]
    return set_categories(out)


def payout_band(y) -> np.ndarray:
    """0 = $0, 1 = under $10k, 2 = $10-50k, 3 = $50-100k, 4 = over $100k."""
    y = np.asarray(y, dtype=float)
    return np.digitize(y, [1e-9, 10_000, 50_000, 100_000], right=False)


BAND_LABELS = ["$0", "under $10k", "$10–50k", "$50–100k", "over $100k"]


def era_of(year) -> np.ndarray:
    year = np.asarray(year)
    return np.select([year <= 2015, year <= 2019], ["2010–15", "2016–19"], "2020–24")
