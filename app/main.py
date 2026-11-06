"""quant-curve API — honest quantization-bench surface.

Serves rows from the results file exported by tools/sync_results.py, which
exports only MEASURED receipts from a hash-chain-verified receipt directory
(integrity only: the chain is unsigned). This API does not re-verify receipts.

States: MEASURED (a valid export with quant rows), EMPTY_HONEST (a valid export
with no quant rows), UNAVAILABLE (the results file is missing, unreadable or
malformed, so no rows are served). Never an error page, never fabricated data.
"""
import json
import logging
import math
import os
import time

from fastapi import FastAPI

PLANE = "quant"
PLANES = ("engine", "retrieval", "quant", "calibration")  # verify/verifier.py schema
RESULTS = os.environ.get("RESULTS_PATH", "site/results.json")

app = FastAPI(title="quant-curve", version="0.1.0")
log = logging.getLogger("quant_curve.api")


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _reject_constant(token):
    raise ValueError(f"non-finite number {token}")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite number {text}")
    return value


def load_rows():
    """Return (rows, generated_at, state) for the configured results file."""
    try:
        with open(RESULTS, encoding="utf-8") as f:
            data = json.load(f, parse_constant=_reject_constant, parse_float=_finite_float)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("invalid result collection")
        if type(data.get("count")) is not int or data["count"] != len(data["results"]):
            raise ValueError("result count mismatch")
        if not isinstance(data.get("generated_at"), str) or not data["generated_at"].strip():
            raise ValueError("missing generation time")
        if any(not isinstance(row, dict) or row.get("plane") not in PLANES
               for row in data["results"]):
            raise ValueError("invalid result row")
    except (OSError, ValueError) as exc:
        # Missing or malformed evidence is reported as such, never as "empty".
        log.warning("results unavailable from %s: %s", RESULTS, exc)
        return [], None, "UNAVAILABLE"
    rows = [row for row in data["results"] if row["plane"] == PLANE]
    return rows, data["generated_at"], "MEASURED" if rows else "EMPTY_HONEST"


@app.get("/healthz")
def healthz():
    return {"status": "ok", "plane": PLANE, "ts": _now()}


@app.get("/api/results")
def results():
    rows, generated_at, state = load_rows()
    return {
        "plane": PLANE,
        "state": state,
        "generated_at": generated_at,
        "count": len(rows),
        "results": rows,
        "served_at": _now(),
    }
