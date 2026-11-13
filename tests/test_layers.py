"""Tests for the layers on their own: settings, model loading and the service, without HTTP.

Run with `pytest` from the repository root (needs requirements-dev.txt).
"""
import ast
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import model
from app.config import ROOT, Settings
from app.main import create_app
from app.service import EstimateService, InputError

HOUSE = dict(flood_zone="A", year_built=1985, floors="1", foundation="slab", basement="none", elevated=False,
             primary_residence=True, coverage_building=250_000, deductible_building=1_250, water_depth_inches=12)


@pytest.fixture()
def service():
    return EstimateService(model.load_bundle(Settings().model_path))


# ---------------------------------------------------------------- infrastructure: settings
def test_settings_defaults_point_at_the_shipped_model_and_page():
    s = Settings()
    assert s.model_path == ROOT / "models" / "flood_payout_v2.joblib" and s.model_path.is_file()
    assert s.static_dir == ROOT / "frontend" / "dist"
    assert s.rate_limit == "30/minute"


def test_settings_read_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "other.joblib"))
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("RATE_LIMIT", "5/minute")
    assert Settings.from_env() == Settings(model_path=tmp_path / "other.joblib", static_dir=tmp_path,
                                           rate_limit="5/minute")


def test_environment_is_read_in_one_place_only():
    """No file in app/ except config.py reads environment variables."""
    for path in (ROOT / "app").glob("*.py"):
        if path.name != "config.py":
            assert "os.environ" not in path.read_text() and "getenv" not in path.read_text(), path.name


# ---------------------------------------------------------------- infrastructure: model loading
def test_model_file_is_read_once_and_shared():
    path = Settings().model_path
    assert model.load_bundle(path) is model.load_bundle(path)
    assert create_app(static_dir=None).state.service.bundle is model.load_bundle(path)


def test_a_missing_model_file_stops_the_app_at_start(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(model_path=tmp_path / "missing.joblib", static_dir=None)


# ---------------------------------------------------------------- service layer, no HTTP
def test_service_answers_without_http(service):
    r = service.estimate(dict(HOUSE))
    assert (r["low"], r["middle"], r["high"]) == (38_600.0, 88_500.0, 138_600.0)
    assert r["model_version"] == service.info()["model_version"]


def test_service_counts_requests_invalid_forms_and_unknown_depth(service):
    service.estimate(dict(HOUSE))
    service.estimate({**HOUSE, "water_depth_inches": None})
    with pytest.raises(InputError) as rejected:
        service.estimate({**HOUSE, "coverage_building": 999})
    assert "coverage_building" in rejected.value.errors
    assert service.counts == {"requests": 3, "invalid": 1, "no_depth": 1}


# ---------------------------------------------------------------- the layers stay apart
def imported_modules(path: Path) -> set[str]:
    """Top-level names of every module a file imports (read from the syntax tree, not by text search)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    return names


def test_api_and_service_layers_do_not_import_the_ml_libraries():
    """Only the model layer (src/flood_payout) may use scikit-learn, pandas, numpy or joblib."""
    for path in (ROOT / "app").glob("*.py"):
        tops = {name.split(".")[0] for name in imported_modules(path)}
        assert not tops & {"sklearn", "pandas", "numpy", "joblib"}, path.name


def test_model_layer_does_not_know_about_the_web():
    for path in (ROOT / "src" / "flood_payout").glob("*.py"):
        tops = {name.split(".")[0] for name in imported_modules(path)}
        assert not tops & {"fastapi", "starlette", "slowapi", "pydantic", "app"}, path.name


def test_inference_and_preprocessing_do_not_import_training_code():
    """The service answers requests through these two files, which must not pull in the training module."""
    for name in ("inference.py", "preprocessing.py"):
        modules = imported_modules(ROOT / "src" / "flood_payout" / name)
        assert ".training" not in modules and "sklearn.ensemble" not in modules, name


def test_app_factory_accepts_a_settings_object(tmp_path):
    (tmp_path / "index.html").write_text("<div id='root'></div>")
    app = create_app(Settings(static_dir=tmp_path, rate_limit="2/minute"))
    assert app.state.settings.rate_limit == "2/minute"
    client = TestClient(app)
    assert "root" in client.get("/").text and client.get("/health").json()["status"] == "ok"
    assert "app.main" in sys.modules and Path(app.state.settings.model_path).is_file()
