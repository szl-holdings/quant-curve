"""Sync verified receipts into site/results.json for the public bench surface.

Fail-closed: any verification error aborts with exit 1 and writes nothing.
Only MEASURED receipts are exported. Output is UNSIGNED-honest: integrity via
the hash chain, not signer identity. The export is strict JSON and replaces
out_path atomically, so a reader never sees a partial file.

usage: sync_results.py [receipts_dir] [out_path]
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verify"))
from verifier import load_receipt, verify  # noqa: E402


def main(receipts_dir="receipts", out="site/results.json"):
    paths = sorted(glob.glob(os.path.join(receipts_dir, "*.json")))
    errors, measured = verify(paths)
    if errors:
        for e in errors:
            print("FAIL", e)
        print("aborting: nothing published")
        return 1
    rows = []
    for p in measured:
        r = load_receipt(p)
        rows.append({
            "plane": r["plane"],
            "machine": r["machine"],
            "measured_at": r["measured_at"],
            "method": r["method"],
            "metrics": r["metrics"],
            "receipt": r["hash"],
        })
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(rows),
        "results": rows,
    }
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    parent = os.path.dirname(out)
    if parent:  # a bare filename writes to the current directory
        os.makedirs(parent, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, out)
    print(f"published {len(rows)} measured rows -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
