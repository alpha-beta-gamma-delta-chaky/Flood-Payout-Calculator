"""Seasonal retraining: rebuild the model bundle from a fresh claims table, promote it only if not worse.

    python retrain.py --table ../Phase_1_Proposal/data/model_table.csv.gz --out models/flood_payout_candidate.joblib

Steps
1. Hold-out year H = the most recent complete loss year (default: latest year in the table minus one,
   because the latest year still has many open claims).
2. Fit the final configuration on losses before H, calibrate it with flood-grouped CV, and score it on H
   exactly as the service answers (no-depth model when no depth is recorded).
3. Score the current bundle on H the same way.
4. If the candidate's range loss is not more than 2% worse, refit on all losses up to H and save it.
   --update-fixtures also rewrites tests/expected_examples.json for the new bundle.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from flood_payout import bundle as Bn, evaluation as E, features as F, models as Mo  # noqa: E402
from flood_payout.final_config import CAL_METHOD, FINAL_FEATS, NODEPTH_FEATS, PARAMS  # noqa: E402

DTYPES = {"countyCode": str, "censusGeoid": str, "flood_group": str, "post_cause_of_damage": str}


def build(data: pd.DataFrame) -> dict:
    """Calibration from flood-grouped CV, then the bundle fitted on all of `data`."""
    y = data.paid_building.to_numpy(float)
    cap = data.coverage_building.fillna(250_000).to_numpy(float)
    folds = E.flood_folds(data.flood_group.to_numpy(), 5)
    cal = {}
    for path, feats in (("with_depth", FINAL_FEATS), ("no_depth", NODEPTH_FEATS)):
        p = Mo.oof_quantiles(data, feats, y, cap, folds, (0.25, 0.5, 0.75), params=PARAMS)
        cal[path] = {"range": Mo.fit_calibrator(y, p[0.25], p[0.75], CAL_METHOD),
                     "d_mid": float(np.median(np.log1p(y) - np.log1p(p[0.5])))}
        print(f"  calibrated {path}: {cal[path]}", flush=True)
    return Bn.train_bundle(data, y, F.payout_band(y), FINAL_FEATS, NODEPTH_FEATS, PARAMS, cal,
                           metrics={}, notes=f"retrained on losses {data.loss_year.min()}-{data.loss_year.max()}")


def score(bundle: dict, data: pd.DataFrame, base: tuple) -> dict:
    y = data.paid_building.to_numpy(float)
    has_d = data["depth_interior_clean"].notna().to_numpy()  # the depth a homeowner can report (placeholders removed)
    lo, hi = np.zeros(len(y)), np.zeros(len(y))
    for path, m in (("with_depth", has_d), ("no_depth", ~has_d)):
        if m.any():
            r = Bn.predict_frame(bundle, data[m], path)
            lo[m], hi[m] = r["low"], r["high"]
    b_lo, b_hi = (np.full(len(y), v) for v in base)
    return E.summarize(y, lo, hi, b_lo, b_hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--current", default=str(ROOT / "models" / "flood_payout_v2.joblib"))
    ap.add_argument("--out", default=str(ROOT / "models" / "flood_payout_candidate.joblib"))
    ap.add_argument("--holdout-year", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None, help="use a random subset (for a quick test only)")
    ap.add_argument("--update-fixtures", action="store_true")
    a = ap.parse_args()

    df = pd.read_csv(a.table, low_memory=False, dtype=DTYPES)
    df = df[df.loss_year >= 2010]
    H = a.holdout_year or int(df.loss_year.max()) - 1
    if a.sample:
        df = df.sample(n=min(a.sample, len(df)), random_state=0)
    df = F.prepare(df.reset_index(drop=True))
    past, hold = df[df.loss_year < H].reset_index(drop=True), df[df.loss_year == H].reset_index(drop=True)
    print(f"training on {len(past):,} claims before {H}, holding out {len(hold):,} claims from {H}", flush=True)
    base = tuple(np.quantile(past.paid_building, [0.25, 0.75]))

    candidate = build(past)
    s_new = score(candidate, hold, base)
    s_cur = score(Bn.load(a.current), hold, base)
    print(f"hold-out {H}: candidate skill {s_new['skill']:.3f} inside {s_new['coverage']:.1%} | "
          f"current skill {s_cur['skill']:.3f} inside {s_cur['coverage']:.1%}")
    # range loss is proportional to (1 - skill) for the same baseline
    if (1 - s_new["skill"]) > 1.02 * (1 - s_cur["skill"]):
        print("candidate is worse than the current model: not promoted")
        sys.exit(1)
    print(f"promoted: refitting on all {len(past) + len(hold):,} claims up to {H}", flush=True)
    final = build(pd.concat([past, hold], ignore_index=True))
    final["metrics"] = {"holdout_year": H, "candidate_on_holdout": s_new, "previous_on_holdout": s_cur}
    Bn.save(final, Path(a.out))
    print(f"saved {a.out}")
    if a.update_fixtures:
        fx_path = ROOT / "tests" / "expected_examples.json"
        fixtures = json.loads(fx_path.read_text())
        answers = Bn.predict(final, [f["form"] for f in fixtures])
        for f, ans in zip(fixtures, answers):
            f["expected"] = {k: ans[k] for k in ("low", "middle", "high")}
        fx_path.write_text(json.dumps(fixtures, indent=2))
        print(f"updated {fx_path}")


if __name__ == "__main__":
    main()
