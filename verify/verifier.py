"""Receipt verifier for the SZL bench planes.

Schema (v1):
  plane        str   one of "engine" | "retrieval" | "quant" | "calibration"
  status       str   one of MEASURED | BLOCKED | INVALID | FAILED | PROMOTED
  machine      obj   {cpu: str, ram_gb: number, gpu: str}
  measured_at  str   ISO-8601 date or datetime (UTC)
  method       str   free text naming harness + version
  metrics      obj   plane-specific measured values (empty for non-MEASURED)
  prev_hash    str   sha256 hex of previous receipt, or 64 zeros for genesis
  hash         str   sha256 of canonical JSON of this receipt without "hash"

Rules: fail closed. Any malformed receipt, bad hash, or broken chain exits 1.
Receipts must be strict JSON: NaN/Infinity tokens and floats that overflow to
infinity are rejected rather than hashed into the chain or exported.
Only MEASURED receipts are publishable; other states are reported, never published.
Integrity only (UNSIGNED-honest): proves chain continuity, not signer identity.
"""
import hashlib
import json
import math
import sys

STATUSES = {"MEASURED", "BLOCKED", "INVALID", "FAILED", "PROMOTED"}
PLANES = {"engine", "retrieval", "quant", "calibration"}
GENESIS = "0" * 64
REQUIRED = ("plane", "status", "machine", "measured_at", "method", "metrics", "prev_hash", "hash")


def digest(receipt):
    body = {k: v for k, v in receipt.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _reject_constant(token):
    raise ValueError(f"non-finite number {token} is not valid receipt JSON")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"number {text} is not finite")
    return value


def load_receipt(path):
    """Parse one receipt file as strict JSON.

    The stdlib parser accepts NaN/Infinity and turns 1e400 into inf by default;
    such values would verify, then reach results.json as non-standard JSON.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f, parse_constant=_reject_constant, parse_float=_finite_float)


def check_receipt(r, i):
    if not isinstance(r, dict):
        return [f"[{i}] receipt must be a JSON object"]
    errs = [f"[{i}] missing field: {f}" for f in REQUIRED if f not in r]
    if errs:
        return errs
    if not isinstance(r["plane"], str) or r["plane"] not in PLANES:
        errs.append(f"[{i}] unknown plane: {r['plane']}")
    if not isinstance(r["status"], str) or r["status"] not in STATUSES:
        errs.append(f"[{i}] unknown status: {r['status']}")
    m = r["machine"]
    if not isinstance(m, dict) or not all(k in m for k in ("cpu", "ram_gb", "gpu")):
        errs.append(f"[{i}] machine must name cpu, ram_gb, gpu")
    if r["status"] == "MEASURED" and not r["metrics"]:
        errs.append(f"[{i}] MEASURED with empty metrics")
    if digest(r) != r["hash"]:
        errs.append(f"[{i}] hash mismatch (recomputed != declared)")
    return errs


def verify(paths):
    try:
        paths = list(paths)
    except TypeError:
        return ["receipt paths must be an iterable collection"], []
    if not paths:
        return ["empty receipt chain"], []
    all_errs, measured, prev = [], [], GENESIS
    for i, p in enumerate(paths):
        try:
            r = load_receipt(p)
        except Exception as e:
            all_errs.append(f"[{i}] {p}: unreadable JSON: {e}")
            continue
        all_errs += check_receipt(r, i)
        if not isinstance(r, dict):
            continue
        if r.get("prev_hash", prev) != prev:
            all_errs.append(f"[{i}] {p}: chain break (prev_hash mismatch)")
        prev = r.get("hash", prev)
        if r.get("status") == "MEASURED":
            measured.append(p)
    return all_errs, measured


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("usage: verifier.py <receipt.json> [...]")
        sys.exit(2)
    errors, ok = verify(args)
    for e in errors:
        print("FAIL", e)
    print(f"checked={len(args)} measured={len(ok)} errors={len(errors)}")
    sys.exit(1 if errors else 0)
