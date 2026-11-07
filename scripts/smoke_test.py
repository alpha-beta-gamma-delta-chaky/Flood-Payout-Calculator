#!/usr/bin/env python3
"""Smoke test for a running Flood Payout Calculator. Standard library only.

    python3 scripts/smoke_test.py http://localhost:8000
    python3 scripts/smoke_test.py https://flood-payout-alpha.duckdns.org --wait 120

It makes four requests (the rate limit is 30 a minute for each client):
  1. GET  /health        status is "ok" and the model version is reported
  2. GET  /              the React page is served
  3. POST /api/estimate  the 12-inch example house gives the recorded low / middle / high
                         (tests/expected_examples.json, within $1)
  4. POST /api/estimate  a house with a coverage that is too low is rejected with 422

--wait N keeps trying /health for up to N seconds first (start-up, or the first HTTPS certificate).
Exit code 0 means every check passed, 1 means something failed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EXAMPLES_FILE = Path(__file__).resolve().parent.parent / "tests" / "expected_examples.json"
TOLERANCE = 1.0          # dollars: the model is deterministic, so a different answer means a different model file
DEFAULT_HOUSE = dict(flood_zone="A", year_built=1985, floors="1", foundation="slab", basement="none", elevated=False,
                     primary_residence=True, coverage_building=250_000, deductible_building=1_250,
                     water_depth_inches=12)


def call(method, url, body=None, timeout=15):
    """Return (status code, body bytes). HTTP errors come back as a status; network errors are raised."""
    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def load_example():
    """The recorded 12-inch example: (house, expected low/middle/high). Without the file: default house, no numbers."""
    try:
        examples = json.loads(EXAMPLES_FILE.read_text())
        example = next(e for e in examples if e["form"].get("water_depth_inches") == 12)
    except (OSError, ValueError, StopIteration):
        return dict(DEFAULT_HOUSE), None
    house = {k: v for k, v in example["form"].items() if k != "state"}      # the API does not take a state
    return house, example["expected"]


def wait_for_health(base, seconds):
    """Return (status, body) once /health answers 200, or the last problem as a string after `seconds`."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            status, raw = call("GET", base + "/health")
            if status == 200:
                return status, raw
            problem = f"HTTP {status}"
        except OSError as err:                                   # connection refused, timeout, TLS not ready yet
            problem = repr(err)
        if time.monotonic() >= deadline:
            return None, problem
        time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base_url", help="for example http://localhost:8000 or https://yourname.duckdns.org")
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                        help="keep trying /health for this long before giving up (default: one try)")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    failures = []

    def check(name, ok, detail=""):
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
        if not ok:
            failures.append(name)

    print(f"Smoke test: {base}")

    # 1. /health
    status, raw = wait_for_health(base, args.wait)
    if status is None:
        check("GET /health answers", False, raw)
        print("Stopping: the service does not answer.")
        return 1
    health = json.loads(raw)
    check("GET /health", health.get("status") == "ok" and bool(health.get("model_version")),
          f"model {health.get('model_version')}, scikit-learn {health.get('sklearn_version')}")

    # 2. the web page
    status, raw = call("GET", base + "/")
    check("GET / serves the web page", status == 200 and b'id="root"' in raw, f"HTTP {status}")

    # 3. one recorded example house
    house, expected = load_example()
    status, raw = call("POST", base + "/api/estimate", house)
    if status != 200:
        check("POST /api/estimate (example house)", False, f"HTTP {status} {raw[:200]!r}")
    else:
        answer = json.loads(raw)
        ordered = 0 <= answer["low"] <= answer["middle"] <= answer["high"] <= answer["coverage_limit"]
        check("estimate is ordered: low <= middle <= high <= coverage", ordered,
              f"{answer['low']:,.0f} / {answer['middle']:,.0f} / {answer['high']:,.0f}")
        check("estimate reports the same model version as /health",
              answer.get("model_version") == health["model_version"])
        if expected is None:
            print("  skip  recorded numbers (tests/expected_examples.json not found)")
        else:
            off = {k: (answer[k], v) for k, v in expected.items() if abs(answer[k] - v) > TOLERANCE}
            check("estimate matches the recorded example", not off,
                  f"differences (got, expected): {off}" if off else "")

    # 4. bad input is rejected
    status, _ = call("POST", base + "/api/estimate", {**house, "coverage_building": 999})
    check("a coverage of 999 is rejected with 422", status == 422, f"HTTP {status}")

    print("PASSED" if not failures else f"FAILED: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
