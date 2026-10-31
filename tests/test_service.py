"""Tests run by CI on every pull request (plain unittest, so they also run under pytest).

    python -m unittest discover -s tests -v          (from the repository root)

They check the leakage guard, input validation, the shape and sanity of every answer, the
"I don't know the depth" path, and that three fixed example houses still get the ranges recorded
when the model was built (regression test: catches a broken model file or library mismatch).
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flood_payout import bundle as B  # noqa: E402
from flood_payout.features import LeakageError, check_inputs  # noqa: E402

BUNDLE = B.load(ROOT / "models" / "flood_payout_v2.joblib")
EXAMPLES = json.loads((ROOT / "tests" / "expected_examples.json").read_text())
HOUSE = dict(state="TX", flood_zone="A", year_built=1985, floors="1", foundation="slab", basement="none",
             elevated=False, primary_residence=True, coverage_building=250_000, deductible_building=1_250,
             water_depth_inches=12)


class LeakageGuard(unittest.TestCase):
    def test_adjuster_fields_rejected(self):
        for bad in ["post_damage_building", "paid_building", "post_building_value", "damage_estimate", "id"]:
            with self.assertRaises(LeakageError):
                check_inputs(["state", bad])

    def test_bundle_uses_only_allowed_inputs(self):
        for path in ("with_depth", "no_depth"):
            check_inputs(BUNDLE["features"][path])


class Validation(unittest.TestCase):
    def test_missing_required(self):
        with self.assertRaises(B.InputError) as ctx:
            B.validate({k: v for k, v in HOUSE.items() if k != "coverage_building"})
        self.assertIn("coverage_building", ctx.exception.errors)

    def test_bad_values(self):
        for field, value in [("state", "ZZ"), ("coverage_building", 900_000), ("water_depth_inches", -3),
                             ("floors", "seven"), ("year_built", 1700), ("elevated", "maybe")]:
            with self.assertRaises(B.InputError, msg=field):
                B.validate({**HOUSE, field: value})

    def test_unknown_field_rejected(self):
        with self.assertRaises(B.InputError):
            B.validate({**HOUSE, "building_damage": 50_000})

    def test_optional_fields_default(self):
        clean = B.validate({k: HOUSE[k] for k in ("state", "elevated", "primary_residence", "coverage_building",
                                                  "deductible_building")})
        self.assertEqual(clean["foundation"], "unknown")
        self.assertIsNone(clean["water_depth_inches"])


class Answers(unittest.TestCase):
    def test_range_is_ordered_and_capped(self):
        for depth in [0, 6, 12, 24, 48, None]:
            for cov in [50_000, 150_000, 250_000]:
                r = B.predict(BUNDLE, [{**HOUSE, "water_depth_inches": depth, "coverage_building": cov}])[0]
                self.assertLessEqual(0, r["low"])
                self.assertLessEqual(r["low"], r["middle"])
                self.assertLessEqual(r["middle"], r["high"])
                self.assertLessEqual(r["high"], cov)
                self.assertAlmostEqual(sum(r["band_probabilities"].values()), 1.0, places=2)
                self.assertTrue(0 <= r["chance_of_zero"] <= 1)

    def test_unknown_depth_uses_no_depth_model(self):
        r = B.predict(BUNDLE, [{**HOUSE, "water_depth_inches": None}])[0]
        self.assertFalse(r["depth_used"])

    def test_deeper_water_raises_middle_guess(self):
        mids = [B.predict(BUNDLE, [{**HOUSE, "water_depth_inches": d}])[0]["middle"] for d in (0, 12, 36)]
        self.assertLess(mids[0], mids[-1])

    def test_batch_equals_single(self):
        forms = [{**HOUSE, "water_depth_inches": d} for d in (0, None, 30)]
        batch = B.predict(BUNDLE, forms)
        single = [B.predict(BUNDLE, [f])[0] for f in forms]
        self.assertEqual(batch, single)


class Regression(unittest.TestCase):
    def test_example_houses_unchanged(self):
        for ex in EXAMPLES:
            r = B.predict(BUNDLE, [ex["form"]])[0]
            for k in ("low", "middle", "high"):
                self.assertAlmostEqual(r[k], ex["expected"][k], delta=max(200, 0.02 * ex["expected"][k]),
                                       msg=f"{ex['name']} {k}")


if __name__ == "__main__":
    unittest.main()
