"""The final model configuration, chosen in notebooks 04-05 and fixed by the deployment check in notebook 06.

Adopted:
  * no state field: it identifies big floods rather than describing the house            (E1, ladder, drift)
  * water depth = FEMA's interior water-mark depth only (inches above the floor inside the house). This is the
    quantity the form asks the homeowner for. The ladder's best inputs (both adjuster depth columns + source
    flag, E2) need a second adjuster measurement the homeowner cannot give: fed one homeowner depth they score
    0.256 on claims with a usable interior depth, against 0.270 for the final model (deployment check, nb 06).
  * interior depth 0 recorded with a positive waterDepth is a placeholder and treated as "not recorded"
    (found when the example house with 0 inches got a flooded-house range; see features.clean_interior_depth)
  * calibration: conformalised quantile regression, one shift per end of the range        (E6)
Tested, not kept: harmonised foundation (real alone, +0.003, but +0.001 with an interval including zero on
top of the two changes above), tuned hyperparameters (gain not distinguishable from chance), quantile
regression forest and two-part model (small or uncertain gains; the two-part range over-covers), month of the
flood (no gain on future years), NOAA / county features (hurt), flood weights (hurt), monotone depth (hurts).
"""
from .features import FORM10
from .models import HGB_DEFAULT

DEPTH3 = ["depth_rule_in", "depth_interior_in", "depth_source"]
_NO_STATE = [c for c in FORM10 if c != "state"]
_HARM = [c for c in _NO_STATE if c not in ("foundation", "basement")] + ["foundation_h"]

FINAL_FEATS = _NO_STATE + ["depth_interior_clean"]   # 10 columns = 10 form questions
NODEPTH_FEATS = _NO_STATE                   # the "I don't know the depth" model
PARAMS = dict(HGB_DEFAULT)                  # Phase 1 settings (tuning gain not significant)
CAL_METHOD = "cqr_asym"

# Combination ladder (notebook 06): (label, cache key, inputs, hyperparameters).
# The last step is tested but not kept: its gain on top of the step before is not distinguishable from zero.
# The deployment check in notebook 06 then replaces the two depth columns by the interior depth alone.
DEPLOY_CANDIDATES = [
    ("M2 (Phase 1): 10 fields + unit-rule waterDepth", "M2", FORM10 + ["depth_rule_in"]),
    ("Ladder result: both depth columns + flag, no state", "ladder_nostate", _NO_STATE + DEPTH3),
    ("Combined depth (interior, else unit rule) + flag, no state", "cand_best_flag",
     _NO_STATE + ["depth_best_in", "depth_source"]),
    ("Combined depth, no flag, no state", "cand_best", _NO_STATE + ["depth_best_in"]),
    ("Interior depth only (zeros as recorded), no state", "cand_interior", _NO_STATE + ["depth_interior_in"]),
    ("Interior depth, placeholder zeros removed, no state (FINAL)", "cand_interior_clean",
     _NO_STATE + ["depth_interior_clean"]),
]
LADDER = [
    ("M2 reference: 10 fields + unit-rule depth", "M2", FORM10 + ["depth_rule_in"], None),
    ("+ both depth columns and source flag", "depth_two", FORM10 + DEPTH3, None),
    ("+ state field removed", "ladder_nostate", _NO_STATE + DEPTH3, None),
    ("+ harmonised foundation (tested, not kept)", "ladder_final", _HARM + DEPTH3, None),
]
