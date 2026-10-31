"""Request and response shapes (Pydantic v2).

`extra="forbid"` rejects any field that is not listed here, so an adjuster-only column such as a `post_` field
can never reach the model. Allowed values and ranges come from the model code (flood_payout.bundle.SCHEMA), so
the API and the model cannot disagree.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from flood_payout.bundle import SCHEMA
from flood_payout.features import CATEGORIES

FloodZone = Literal[tuple(CATEGORIES["flood_zone"])]
Floors = Literal[tuple(CATEGORIES["floors"])]
Foundation = Literal[tuple(CATEGORIES["foundation"])]
Basement = Literal[tuple(CATEGORIES["basement"])]


def _range(name: str) -> dict:
    return {"ge": SCHEMA[name]["min"], "le": SCHEMA[name]["max"]}


class EstimateRequest(BaseModel):
    """The ten form questions plus the water depth (inches above the floor, inside the building)."""

    model_config = ConfigDict(extra="forbid")

    flood_zone: FloodZone = "unknown"
    year_built: int | None = Field(default=None, **_range("year_built"))
    floors: Floors = "unknown"
    foundation: Foundation = "unknown"
    basement: Basement = "unknown"
    elevated: bool
    primary_residence: bool
    coverage_building: float = Field(**_range("coverage_building"))
    deductible_building: float = Field(**_range("deductible_building"))
    water_depth_inches: float | None = Field(default=None, **_range("water_depth_inches"))  # None = not sure


class EstimateResponse(BaseModel):
    low: float
    middle: float
    high: float
    coverage_limit: float
    chance_of_zero: float
    band_probabilities: dict[str, float]
    depth_used: bool
    model_version: str
    message: str
