"""Models used in the Phase 2 experiments.

All range models predict quantiles of log(1 + payout); predictions are converted back to dollars
(quantiles survive monotone transforms) and held between $0 and the policy's coverage limit.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from .features import check_inputs

HGB_DEFAULT = dict(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=200)


def to_dollars(log_pred, cap):
    return np.clip(np.expm1(log_pred), 0, cap)


# ---------------------------------------------------------------- gradient-boosted quantiles
def hgb_quantile(q, params=None, monotone=None, seed=0):
    p = {**HGB_DEFAULT, **(params or {})}
    return HistGradientBoostingRegressor(loss="quantile", quantile=q, categorical_features="from_dtype",
                                         monotonic_cst=monotone, random_state=seed, **p)


def oof_quantiles(data: pd.DataFrame, features, y, cap, folds, quantiles=(0.25, 0.75), params=None,
                  monotone=None, sample_weight=None, train_mask=None, per_fold_cols=None,
                  cache: Path | None = None, keep_models: bool = False, seed: int = 0):
    """Out-of-fold quantile predictions in dollars, one model per fold and quantile.

    train_mask restricts which rows may be used for training (e.g. recent years only, or a
    subsample for a learning curve); every row of the held-out fold is still predicted.
    per_fold_cols: {column: array (n_folds x n_rows)} for features that must be rebuilt inside
    each fold (target encodings), so the held-out floods never inform their own feature.
    """
    check_inputs(features)
    if cache is not None and Path(cache).exists() and not keep_models:
        z = np.load(cache)
        return {float(k): z[k] for k in z.files}
    ylog = np.log1p(y)
    out = {q: np.zeros(len(y)) for q in quantiles}
    models = {}
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        if train_mask is not None:
            tr = tr & train_mask
        X = data[features]
        if per_fold_cols:
            X = X.copy()
            for c, mat in per_fold_cols.items():
                X[c] = mat[k]
        for q in quantiles:
            m = hgb_quantile(q, params, monotone, seed)
            m.fit(X.loc[tr], ylog[tr], sample_weight=None if sample_weight is None else sample_weight[tr])
            out[q][te] = to_dollars(m.predict(X.loc[te]), cap[te])
            if keep_models:
                models[(int(k), q)] = m
    if cache is not None:
        np.savez_compressed(cache, **{str(q): v for q, v in out.items()})
    return (out, models) if keep_models else out


# ---------------------------------------------------------------- calibration (cross-fitted)
def fit_calibrator(y, lo, hi, method: str, strata=None) -> dict:
    """Learn a correction of the range from out-of-fold predictions of past/other floods."""
    if method == "none":
        return {"method": method}
    if method == "scale":                                   # Phase 1: multiplicative stretch factors
        return {"method": method,
                "lo": min(np.quantile(y / np.maximum(lo, 1), 0.25), 1.0),
                "hi": max(np.quantile(y / np.maximum(hi, 1), 0.75), 1.0)}
    ly, llo, lhi = np.log1p(y), np.log1p(lo), np.log1p(hi)
    if method == "cqr_sym":                                 # conformalised QR, one shift for both ends
        e = np.maximum(llo - ly, ly - lhi)
        return {"method": method, "delta": float(np.quantile(e, 0.5))}
    if method == "cqr_asym":                                # one shift per end: 25% below, 25% above
        return {"method": method, "d_lo": float(np.quantile(ly - llo, 0.25)),
                "d_hi": float(np.quantile(ly - lhi, 0.75))}
    if method == "cqr_asym_strata":                         # separate shifts per stratum (Mondrian)
        s = np.asarray(strata)
        return {"method": method, "per": {str(v): fit_calibrator(y[s == v], lo[s == v], hi[s == v], "cqr_asym")
                                          for v in np.unique(s)}}
    raise ValueError(method)


def apply_calibrator(lo, hi, cap, params: dict, strata=None):
    m = params["method"]
    if m == "none":
        return lo.copy(), hi.copy()
    if m == "scale":
        return np.clip(lo * params["lo"], 0, cap), np.clip(hi * params["hi"], 0, cap)
    if m == "cqr_sym":
        d = params["delta"]
        return to_dollars(np.log1p(lo) - d, cap), to_dollars(np.log1p(hi) + d, cap)
    if m == "cqr_asym":
        return to_dollars(np.log1p(lo) + params["d_lo"], cap), to_dollars(np.log1p(hi) + params["d_hi"], cap)
    if m == "cqr_asym_strata":
        s = np.asarray(strata).astype(str)
        lo_c, hi_c = lo.copy(), hi.copy()
        for v, p in params["per"].items():
            sel = s == v
            lo_c[sel], hi_c[sel] = apply_calibrator(lo[sel], hi[sel], cap[sel], p)
        return lo_c, hi_c
    raise ValueError(m)


def crossfit_calibration(y, lo, hi, cap, folds, method, strata=None):
    """Calibrate fold k with a correction learned only on the other folds (honest check)."""
    lo_c, hi_c = np.zeros(len(y)), np.zeros(len(y))
    params = []
    for k in np.unique(folds):
        o, t = folds != k, folds == k
        p = fit_calibrator(y[o], lo[o], hi[o], method, None if strata is None else np.asarray(strata)[o])
        params.append(p)
        lo_c[t], hi_c[t] = apply_calibrator(lo[t], hi[t], cap[t], p, None if strata is None else np.asarray(strata)[t])
    return lo_c, hi_c, params


# ---------------------------------------------------------------- two-part (hurdle) model
HURDLE_GRID = (0.03, 0.1, 0.2, 0.3, 0.45, 0.6, 0.7, 0.8, 0.9)


def combine_hurdle(p_zero, pos_logq, taus, cap, grid=HURDLE_GRID):
    """Quantiles of a mixture: $0 with probability p_zero, else the positive-payout distribution.

    The tau-quantile is $0 when tau <= p_zero; otherwise it is the positive part's quantile at
    level (tau - p_zero) / (1 - p_zero), interpolated on the predicted grid of levels.
    """
    grid = np.asarray(grid)
    pos_logq = np.sort(pos_logq, axis=1)                     # remove any quantile crossing
    out = {}
    for tau in taus:
        u = np.clip((tau - p_zero) / np.maximum(1 - p_zero, 1e-9), 0, 1)
        j = np.clip(np.searchsorted(grid, u) - 1, 0, len(grid) - 2)
        w = np.clip((u - grid[j]) / (grid[j + 1] - grid[j]), 0, 1)
        rows = np.arange(len(u))
        lq = pos_logq[rows, j] * (1 - w) + pos_logq[rows, j + 1] * w
        val = to_dollars(lq, cap)
        out[tau] = np.where(tau <= p_zero, 0.0, val)
    return out


def oof_hurdle(data, features, y, cap, folds, taus=(0.25, 0.5, 0.75), params=None, grid=HURDLE_GRID,
               cache: Path | None = None, seed=0):
    check_inputs(features)
    if cache is not None and Path(cache).exists():
        z = np.load(cache)
        return {**{float(k): z[k] for k in z.files if k not in ("p_zero",)}, "p_zero": z["p_zero"]}
    pos = y > 0
    p_zero = np.zeros(len(y))
    pos_logq = np.zeros((len(y), len(grid)))
    X = data[features]
    ylog = np.log1p(y)
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        clf = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=seed,
                                             **{**HGB_DEFAULT, **(params or {})})
        clf.fit(X.loc[tr], pos[tr].astype(int))
        p_zero[te] = clf.predict_proba(X.loc[te])[:, 0]
        for j, g in enumerate(grid):
            m = hgb_quantile(g, params, seed=seed).fit(X.loc[tr & pos], ylog[tr & pos])
            pos_logq[te, j] = m.predict(X.loc[te])
    out = combine_hurdle(p_zero, pos_logq, taus, cap, grid)
    out["p_zero"] = p_zero
    if cache is not None:
        np.savez_compressed(cache, **{str(k): v for k, v in out.items()})
    return out


# ---------------------------------------------------------------- payout-band classifier
def oof_band_classifier(data, features, band, folds, params=None, cache: Path | None = None, seed=0):
    check_inputs(features)
    if cache is not None and Path(cache).exists():
        return np.load(cache)["proba"]
    proba = np.zeros((len(band), 5))
    X = data[features]
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        clf = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=seed,
                                             **{**HGB_DEFAULT, **(params or {})})
        clf.fit(X.loc[tr], band[tr])
        proba[np.ix_(te, clf.classes_)] = clf.predict_proba(X.loc[te])
    if cache is not None:
        np.savez_compressed(cache, proba=proba)
    return proba


# ---------------------------------------------------------------- quantile regression forest
class QuantileForest:
    """Quantile regression forest (Meinshausen 2006) on a fixed grid of log-payout values.

    Each leaf stores the empirical CDF of the training targets that fall in it; the conditional
    CDF of a new claim is the average of its leaves' CDFs over all trees, then inverted.
    """

    def __init__(self, n_estimators=60, min_samples_leaf=100, max_features=0.6, max_samples=0.3,
                 n_grid=200, seed=0, n_jobs=2):
        self.rf = RandomForestRegressor(n_estimators=n_estimators, min_samples_leaf=min_samples_leaf,
                                        max_features=max_features, max_samples=max_samples, n_jobs=n_jobs,
                                        random_state=seed)
        self.n_grid = n_grid

    @staticmethod
    def encode(X: pd.DataFrame) -> np.ndarray:
        cols = []
        for c in X.columns:
            s = X[c]
            if isinstance(s.dtype, pd.CategoricalDtype):
                codes = s.cat.codes.to_numpy().astype(float)
                codes[codes < 0] = np.nan
                cols.append(codes)
            else:
                cols.append(s.to_numpy(dtype=float))
        return np.column_stack(cols).astype(np.float32)

    def fit(self, X, ylog):
        A = self.encode(X)
        self.rf.fit(A, ylog)
        self.grid = np.linspace(0, ylog.max() + 1e-6, self.n_grid)
        yb = np.clip(np.searchsorted(self.grid, ylog, side="left"), 0, self.n_grid - 1)
        leaves = self.rf.apply(A)                                   # n_train x n_trees
        self.cdfs = []
        for t in range(leaves.shape[1]):
            n_nodes = self.rf.estimators_[t].tree_.node_count
            counts = np.bincount(leaves[:, t].astype(np.int64) * self.n_grid + yb,
                                 minlength=n_nodes * self.n_grid).reshape(n_nodes, self.n_grid)
            cdf = np.cumsum(counts, axis=1).astype(np.float32)
            tot = cdf[:, -1:]
            self.cdfs.append(np.divide(cdf, tot, out=np.zeros_like(cdf), where=tot > 0))
        return self

    def predict_quantiles(self, X, taus):
        A = self.encode(X)
        leaves = self.rf.apply(A)
        out = {tau: np.zeros(len(A)) for tau in taus}
        for s in range(0, len(A), 50_000):                          # chunks keep memory small
            sl = slice(s, s + 50_000)
            F = np.zeros((leaves[sl].shape[0], self.n_grid), dtype=np.float32)
            for t, cdf in enumerate(self.cdfs):
                F += cdf[leaves[sl, t]]
            F /= len(self.cdfs)
            for tau in taus:
                idx = np.argmax(F >= tau - 1e-6, axis=1)
                out[tau][sl] = self.grid[idx]
        return out


def oof_qrf(data, features, y, cap, folds, taus=(0.25, 0.5, 0.75), cache: Path | None = None, **kw):
    check_inputs(features)
    if cache is not None and Path(cache).exists():
        z = np.load(cache)
        return {float(k): z[k] for k in z.files}
    out = {t: np.zeros(len(y)) for t in taus}
    ylog = np.log1p(y)
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        f = QuantileForest(**kw).fit(data.loc[tr, features], ylog[tr])
        pq = f.predict_quantiles(data.loc[te, features], taus)
        for t in taus:
            out[t][te] = to_dollars(pq[t], cap[te])
        del f
    if cache is not None:
        np.savez_compressed(cache, **{str(t): v for t, v in out.items()})
    return out


# ---------------------------------------------------------------- linear quantile regression
def linear_design(features, categorical, splines: bool):
    num = [f for f in features if f not in categorical]
    spline_cols = [c for c in num if c in ("depth_rule_in", "year_built")] if splines else []
    plain = [c for c in num if c not in spline_cols]
    steps = [("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50, sparse_output=False),
              [c for c in features if c in categorical]),
             ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), plain)]
    if spline_cols:
        steps.append(("spl", make_pipeline(SimpleImputer(strategy="median"), SplineTransformer(n_knots=6, degree=3)),
                      spline_cols))
        steps.append(("spl_missing", MissingIndicator(features="all"), spline_cols))
    return ColumnTransformer(steps, sparse_threshold=0)


def fit_linear_quantile(A, ylog, tau, eps=0.05, l2=1e-4):
    """Linear quantile regression by minimising a smoothed pinball loss with L-BFGS.

    The softplus-smoothed check loss converges to the exact pinball loss as eps -> 0; with
    eps = 0.05 on the log scale the fitted quantiles match exact linear programming closely
    while scaling to hundreds of thousands of rows.
    """
    A1 = np.hstack([A, np.ones((len(A), 1), dtype=A.dtype)])
    n = len(A1)

    def fg(beta):
        r = ylog - A1 @ beta
        z = -r / eps
        loss = np.mean(tau * r + eps * np.logaddexp(0, z)) + l2 * beta[:-1] @ beta[:-1]
        g_r = tau - 1 / (1 + np.exp(-z))                       # d loss / d r
        grad = -(A1.T @ g_r) / n
        grad[:-1] += 2 * l2 * beta[:-1]
        return loss, grad

    beta0 = np.zeros(A1.shape[1])
    beta0[-1] = np.quantile(ylog, tau)
    res = minimize(fg, beta0, jac=True, method="L-BFGS-B", options={"maxiter": 500})
    return res.x


def oof_linear_quantile(data, features, categorical, y, cap, folds, taus=(0.25, 0.5, 0.75), splines=False,
                        cache: Path | None = None):
    check_inputs(features)
    if cache is not None and Path(cache).exists():
        z = np.load(cache)
        return {float(k): z[k] for k in z.files}
    out = {t: np.zeros(len(y)) for t in taus}
    ylog = np.log1p(y)
    X = data[features].copy()
    for c in categorical:
        if c in X:
            X[c] = X[c].astype(object).where(X[c].notna(), "missing")
    for k in np.unique(folds):
        tr, te = folds != k, folds == k
        ct = linear_design(features, categorical, splines).fit(X.loc[tr])
        A_tr, A_te = ct.transform(X.loc[tr]).astype(np.float32), ct.transform(X.loc[te]).astype(np.float32)
        for t in taus:
            beta = fit_linear_quantile(A_tr, ylog[tr], t)
            out[t][te] = to_dollars(np.hstack([A_te, np.ones((len(A_te), 1))]) @ beta, cap[te])
    if cache is not None:
        np.savez_compressed(cache, **{str(t): v for t, v in out.items()})
    return out


# ---------------------------------------------------------------- neighbourhood payout history
def county_history(county, state, ylog, folds, groups, m: float = 50.0, inner_splits: int = 5):
    """Smoothed mean log-payout of past claims in the same county, rebuilt inside every fold.

    Returns a (n_folds x n_rows) array: row k holds the feature as seen by the model trained for
    fold k. Held-out rows use only training-fold claims; training rows use an inner, flood-grouped
    out-of-fold estimate so a claim never sees its own payout (or its own flood's).
    """
    county = pd.Series(np.asarray(county, dtype=object)).fillna("unknown").to_numpy()
    state = np.asarray(state, dtype=object)
    K = len(np.unique(folds))
    mat = np.full((K, len(ylog)), np.nan)

    def encode(fit_idx, apply_idx):
        f = pd.DataFrame({"c": county[fit_idx], "s": state[fit_idx], "y": ylog[fit_idx]})
        cs = f.groupby("c")["y"].agg(["sum", "count"])
        ss = f.groupby("s")["y"].mean()
        prior = pd.Series(state[apply_idx]).map(ss).fillna(f["y"].mean()).to_numpy()
        s_ = pd.Series(county[apply_idx]).map(cs["sum"]).fillna(0).to_numpy()
        n_ = pd.Series(county[apply_idx]).map(cs["count"]).fillna(0).to_numpy()
        return (s_ + m * prior) / (n_ + m)

    for k in range(K):
        tr, te = np.where(folds != k)[0], np.where(folds == k)[0]
        mat[k, te] = encode(tr, te)
        inner = GroupKFold(n_splits=inner_splits)
        for itr, ite in inner.split(tr, groups=np.asarray(groups)[tr]):
            mat[k, tr[ite]] = encode(tr[itr], tr[ite])
    return mat


def save_models(models: dict, path: Path):
    joblib.dump(models, path, compress=3)


def load_models(path: Path):
    return joblib.load(path)
