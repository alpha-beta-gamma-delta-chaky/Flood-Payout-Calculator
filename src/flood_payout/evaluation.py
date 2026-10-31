"""Folds, metrics, bootstrap intervals and the experiment log."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

LOW, HIGH = 0.25, 0.75


# ---------------------------------------------------------------- folds
def flood_folds(groups, n_splits: int = 5, seed: int | None = None) -> np.ndarray:
    """Fold id per row; every flood sits in exactly one fold.

    seed=None reproduces Phase 1 (GroupKFold, size-balanced). An integer shuffles which
    floods go together, used to repeat the cross-validation with different fold assignments.
    """
    folds = np.zeros(len(groups), dtype=int)
    if seed is None:
        splitter = GroupKFold(n_splits=n_splits)
    else:
        splitter = GroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for k, (_, te) in enumerate(splitter.split(np.zeros(len(groups)), groups=groups)):
        folds[te] = k
    return folds


# ---------------------------------------------------------------- metrics
def pinball_vec(y, q, tau):
    d = np.asarray(y, float) - np.asarray(q, float)
    return np.maximum(tau * d, (tau - 1) * d)


def pinball(y, q, tau):
    return float(np.mean(pinball_vec(y, q, tau)))


def range_loss_vec(y, lo, hi):
    """Per-claim range loss: mean of the pinball losses at the 25th and 75th percentile."""
    return (pinball_vec(y, lo, LOW) + pinball_vec(y, hi, HIGH)) / 2


def range_loss(y, lo, hi):
    return float(np.mean(range_loss_vec(y, lo, hi)))


def one_range_baseline(y, folds):
    """B1: each claim gets the 25th-75th percentile of the payouts in the other folds."""
    lo, hi, mid = np.zeros(len(y)), np.zeros(len(y)), np.zeros(len(y))
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        lo[te], mid[te], hi[te] = np.quantile(y[tr], [LOW, 0.5, HIGH])
    return lo, hi, mid


def summarize(y, lo, hi, base_lo, base_hi, mid=None, base_mid=None, mask=None, weights=None) -> dict:
    """All headline metrics for one range model on one set of claims."""
    m = np.ones(len(y), bool) if mask is None else np.asarray(mask, bool)
    yy, l, h = y[m], lo[m], hi[m]
    w = None if weights is None else np.asarray(weights, float)[m]
    lm, lb = range_loss_vec(yy, l, h), range_loss_vec(yy, base_lo[m], base_hi[m])
    avg = (lambda a: np.average(a, weights=w)) if w is not None else np.mean
    out = {
        "skill": 1 - avg(lm) / avg(lb),
        "coverage": avg((yy >= l) & (yy <= h)),
        "below_range": avg(yy < l),           # paid less than the low end: the range was too optimistic
        "above_range": avg(yy > h),           # paid more than the high end
        "median_width": float(np.median(h - l)),
        "n": int(m.sum()),
    }
    if mid is not None:
        out["mid_medae"] = float(np.median(np.abs(yy - mid[m])))
        if base_mid is not None:
            out["mid_medae_baseline"] = float(np.median(np.abs(yy - base_mid[m])))
    return out


# ---------------------------------------------------------------- bootstrap over whole floods
def flood_bootstrap(y, groups, ranges: dict, base, n_boot: int = 1000, seed: int = 0, ref: str | None = None):
    """95% intervals for skill (and for skill differences against `ref`), resampling whole floods.

    ranges: {name: (lo, hi)}; base: (lo, hi) of the baseline. Resampling floods (not claims)
    respects the fact that claims from one flood are not independent.
    """
    codes, inv = np.unique(groups, return_inverse=True)
    G = len(codes)
    lb = np.bincount(inv, weights=range_loss_vec(y, *base), minlength=G)
    per = {k: np.bincount(inv, weights=range_loss_vec(y, lo, hi), minlength=G) for k, (lo, hi) in ranges.items()}
    rng = np.random.default_rng(seed)
    draws = {k: np.empty(n_boot) for k in per}
    for b in range(n_boot):
        w = np.bincount(rng.integers(0, G, G), minlength=G)
        base_b = w @ lb
        for k, v in per.items():
            draws[k][b] = 1 - (w @ v) / base_b
    rows = []
    for k in per:
        point = 1 - per[k].sum() / lb.sum()
        row = {"approach": k, "skill": point, "ci_low": np.quantile(draws[k], 0.025),
               "ci_high": np.quantile(draws[k], 0.975)}
        if ref is not None and k != ref:
            d = draws[k] - draws[ref]
            row.update({"diff_vs_ref": point - (1 - per[ref].sum() / lb.sum()),
                        "diff_ci_low": np.quantile(d, 0.025), "diff_ci_high": np.quantile(d, 0.975)})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- experiment log
class ExperimentLog:
    """One row per run, written to CSV after every addition (so a crash never loses results)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rows = []

    def add(self, experiment: str, approach: str, metrics: dict, config: dict | None = None, note: str = ""):
        row = {"experiment": experiment, "approach": approach, **metrics,
               "config": json.dumps(config or {}, default=str), "note": note,
               "logged_at": time.strftime("%Y-%m-%d %H:%M")}
        self.rows.append(row)
        pd.DataFrame(self.rows).to_csv(self.path, index=False)
        sk = metrics.get("skill", np.nan)
        cov = metrics.get("coverage", np.nan)
        wd = metrics.get("median_width", np.nan)
        print(f"[{experiment}] {approach:52s} skill {sk:+.3f} | inside {cov:6.1%} | width ${wd:,.0f}")
        return row

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)
