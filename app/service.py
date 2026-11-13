"""Service layer: the "estimate a payout" use case. No HTTP in here.

It takes a checked form, asks the model layer (src/flood_payout) for the answer, and keeps the anonymous
counters and timing log. app/main.py turns HTTP into calls to this class and its results back into HTTP.
"""
from __future__ import annotations

import logging
import time

from flood_payout import bundle as B

from app import model

log = logging.getLogger("flood_payout")

InputError = B.InputError          # raised when the model's own checks reject a form


class EstimateService:
    def __init__(self, bundle: dict):
        self.bundle = bundle
        self.counts = {"requests": 0, "invalid": 0, "no_depth": 0}    # anonymous counts only, no form data

    def info(self) -> dict:
        """Model version details for /health and the API title."""
        return model.info(self.bundle)

    def estimate(self, form: dict) -> dict:
        """One form in, the homeowner-facing result out (range, middle guess, chance of $0, bands).

        Raises InputError if the model's own checks reject the form (a second line behind Pydantic).
        """
        started = time.perf_counter()
        self.counts["requests"] += 1
        try:
            result = B.predict(self.bundle, [form])[0]
        except InputError:
            self.counts["invalid"] += 1
            raise
        self.counts["no_depth"] += int(not result["depth_used"])
        log.info("estimate ok in %.0f ms | counts %s", 1000 * (time.perf_counter() - started), self.counts)
        return result
