# Model card: flood payout range calculator v2.0.0

**What it does.** For an NFIP-insured single-family home that has just been flooded, returns a range in which about
half of similar past claims' building payouts fell (25th–75th percentile), a middle guess, the chance of a $0 building
payment, the chance of each payout band, and the policy's coverage limit as the hard maximum. It is a planning aid,
not a promise: the adjuster decides the payment.

**Inputs (the form).** State, flood zone, year built, number of floors, foundation type, basement/crawlspace type,
raised building, primary residence, building coverage, building deductible, and the water depth inside the house in
inches above the floor (optional; "I don't know" uses a separate model trained without depth). State is accepted but
not used: it identified big floods rather than describing the house and hurt on unseen floods.

**Training data.** 774,990 NFIP single-family claims, losses 2010-2024 (FEMA OpenFEMA NFIP Redacted Claims v3, single-family homes, condos excluded).
Trained 2026-10-27T16:45:14 with scikit-learn 1.9.1.

**Model.** Gradient-boosted quantile regression (scikit-learn HistGradientBoostingRegressor) on log(1 + payout) for
the 25th, 50th and 75th percentile, with depth = FEMA's interior water-mark depth (the quantity the form asks for); conformalised calibration of each end learned on out-of-fold predictions of unseen
floods; a gradient-boosted classifier for the payout bands (its first class is the chance of $0). Inputs:
flood_zone, year_built, floors, foundation, basement, elevated, primary_residence, coverage_building, deductible_building, depth_interior_clean. Hyperparameters: {"max_iter": 300, "learning_rate": 0.08, "max_leaf_nodes": 31, "min_samples_leaf": 200}.

**Evaluation.** Flood-grouped 5-fold cross-validation on 2010–2024 (every score on floods the model never saw):
skill 0.163 vs one range for everyone, 50.3% of payouts inside the range,
24.7% paid less than the low end, median width $44,310.
Claims with an interior depth (what a real request looks like): skill 0.274.
Locked test set, 2025 losses (scored once, 2026-10-27 16:49): skill 0.084,
44.2% inside, 27.3% below the low end,
median width $37,211 (n = 9,985).

**Known limits.** Only insured homes that filed a claim are in the data. The range rarely contains a $0 payout (shown
separately as a probability) and misses many very large payouts. Whole floods can be paid well above or below similar
houses elsewhere, so the share inside varies a lot from flood to flood. The training depth is the adjuster's
measurement; homeowners' own estimates are less exact (a 12-inch error costs part of the skill). Coding and payouts
drift over time; retrain and recalibrate after each flood season. Do not use it for uninsured homes, condominiums,
commercial buildings, or contents.

**Privacy.** No personal data are needed or stored.
