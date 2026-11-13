"""The deployable model bundle: one import for training, saving, input validation and prediction.

The code is split by job so each part can be read and tested on its own:

    preprocessing.py   the request schema, input checks (validate) and form -> feature columns (to_frame)
    inference.py       load a bundle and answer requests (predict, predict_frame)
    training.py        fit the models and pack a bundle (train_bundle, save)

This file re-exports all of them, so existing code keeps working unchanged:
`from flood_payout import bundle as B` in the notebooks, retrain.py, the tests and the web service.
"""
from .inference import TAUS, load, predict, predict_frame
from .preprocessing import MAX_COVERAGE, SCHEMA, InputError, to_frame, validate
from .training import _fit_path, save, train_bundle

__all__ = ["MAX_COVERAGE", "SCHEMA", "TAUS", "InputError", "validate", "to_frame", "train_bundle", "save", "load",
           "predict_frame", "predict", "_fit_path"]
