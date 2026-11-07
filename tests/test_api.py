"""API tests: run with `pytest` from the repository root (needs requirements-dev.txt)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import model
from app.main import create_app

HOUSE = dict(flood_zone="A", year_built=1985, floors="1", foundation="slab", basement="none", elevated=False,
             primary_residence=True, coverage_building=250_000, deductible_building=1_250, water_depth_inches=12)
EXAMPLES = json.loads((Path(__file__).parent / "expected_examples.json").read_text())


@pytest.fixture()
def client():
    return TestClient(create_app(rate_limit="1000/minute", static_dir=None))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["model_version"] == model.info()["model_version"]


def test_docs_available(client):
    assert client.get("/docs").status_code == 200


def test_estimate_returns_ordered_range(client):
    r = client.post("/api/estimate", json=HOUSE)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["low"] <= body["middle"] <= body["high"] <= body["coverage_limit"]
    assert body["depth_used"] is True
    assert abs(sum(body["band_probabilities"].values()) - 1) < 0.01
    assert 0 <= body["chance_of_zero"] <= 1


@pytest.mark.parametrize("ex", EXAMPLES, ids=[e["name"] for e in EXAMPLES])
def test_estimate_matches_recorded_examples(client, ex):
    form = {k: v for k, v in ex["form"].items() if k != "state"}      # state is no longer accepted
    body = client.post("/api/estimate", json=form).json()
    for k in ("low", "middle", "high"):
        assert body[k] == pytest.approx(ex["expected"][k], abs=max(200, 0.02 * ex["expected"][k]))


@pytest.mark.parametrize("depth", [None, "missing"])
def test_unknown_depth_uses_no_depth_model(client, depth):
    form = {k: v for k, v in HOUSE.items() if k != "water_depth_inches"}
    if depth is None:
        form["water_depth_inches"] = None
    r = client.post("/api/estimate", json=form)
    assert r.status_code == 200
    assert r.json()["depth_used"] is False


@pytest.mark.parametrize("extra", ["post_damage_building", "paid_building", "state", "id"])
def test_unknown_and_adjuster_fields_rejected(client, extra):
    r = client.post("/api/estimate", json={**HOUSE, extra: 5})
    assert r.status_code == 422


def test_missing_required_field(client):
    form = {k: v for k, v in HOUSE.items() if k != "coverage_building"}
    r = client.post("/api/estimate", json=form)
    assert r.status_code == 422
    assert any(e["loc"][-1] == "coverage_building" for e in r.json()["detail"])


@pytest.mark.parametrize("field,value", [("coverage_building", 900_000), ("water_depth_inches", -3),
                                         ("floors", "seven"), ("year_built", 1700), ("elevated", "maybe"),
                                         ("flood_zone", "Z")])
def test_bad_values_rejected(client, field, value):
    assert client.post("/api/estimate", json={**HOUSE, field: value}).status_code == 422


def test_rate_limit_per_client():
    c = TestClient(create_app(rate_limit="3/minute", static_dir=None))
    codes = [c.post("/api/estimate", json=HOUSE).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_serves_built_frontend(tmp_path):
    (tmp_path / "index.html").write_text("<h1>web page</h1>")
    c = TestClient(create_app(rate_limit="1000/minute", static_dir=tmp_path))
    assert "web page" in c.get("/").text
    assert c.get("/health").status_code == 200          # API routes still win over the static mount


def test_root_without_frontend_points_to_docs(client):
    assert "docs" in client.get("/").json()["message"]


# ---- contract tests: what the web page, the smoke test and the daily health check rely on --------------------

REQUIRED_ONLY = {k: HOUSE[k] for k in ("elevated", "primary_residence", "coverage_building", "deductible_building")}


def test_response_has_exactly_the_documented_fields(client):
    body = client.post("/api/estimate", json=HOUSE).json()
    assert set(body) == {"low", "middle", "high", "coverage_limit", "chance_of_zero", "band_probabilities",
                         "depth_used", "model_version", "message"}


def test_only_the_four_required_answers_are_enough(client):
    r = client.post("/api/estimate", json=REQUIRED_ONLY)
    assert r.status_code == 200
    assert r.json()["depth_used"] is False


def test_not_sure_answers_are_accepted(client):
    form = {**REQUIRED_ONLY, "flood_zone": "unknown", "floors": "unknown", "foundation": "unknown",
            "basement": "unknown", "year_built": None, "water_depth_inches": None}
    assert client.post("/api/estimate", json=form).status_code == 200


@pytest.mark.parametrize("field,value", [("coverage_building", 1_000), ("coverage_building", 250_000),
                                         ("deductible_building", 0), ("deductible_building", 50_000),
                                         ("water_depth_inches", 0), ("water_depth_inches", 240)])
def test_edges_of_the_allowed_ranges_are_accepted(client, field, value):
    assert client.post("/api/estimate", json={**HOUSE, field: value}).status_code == 200


@pytest.mark.parametrize("field,value", [("coverage_building", 999), ("coverage_building", 250_001),
                                         ("deductible_building", -1), ("deductible_building", 50_001),
                                         ("water_depth_inches", -0.1), ("water_depth_inches", 240.1),
                                         ("year_built", 2999)])
def test_just_outside_the_allowed_ranges_is_rejected(client, field, value):
    assert client.post("/api/estimate", json={**HOUSE, field: value}).status_code == 422


def test_empty_or_non_json_body_is_rejected(client):
    assert client.post("/api/estimate").status_code == 422
    r = client.post("/api/estimate", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_wrong_method_and_unknown_route(client):
    assert client.get("/api/estimate").status_code == 405
    assert client.get("/api/nothing").status_code == 404


def test_rate_limit_answer_tells_the_page_what_happened():
    c = TestClient(create_app(rate_limit="1/minute", static_dir=None))
    c.post("/api/estimate", json=HOUSE)
    r = c.post("/api/estimate", json=HOUSE)
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
    assert r.json()["error"] == "rate limit"


def test_health_is_not_rate_limited():
    c = TestClient(create_app(rate_limit="1/minute", static_dir=None))      # the deploy smoke test calls /health
    assert [c.get("/health").status_code for _ in range(5)] == [200] * 5


def test_health_reports_the_model_in_use(client):
    body = client.get("/health").json()
    assert {"status", "model_version", "trained_on", "sklearn_version"} <= set(body)


def test_installed_scikit_learn_matches_the_one_that_saved_the_model():
    import sklearn
    assert model.info()["sklearn_version"] == sklearn.__version__
