"""tools/sync_results.py: fail-closed export of verified MEASURED receipts.

Stdlib unittest only, so CI can run it as ``python tests/test_sync_results.py``
before any third-party package is installed. Fixture receipts below are unit
fixtures, not measurements.
"""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "tools" / "sync_results.py"
sys.path.insert(0, str(ROOT))
from verify.verifier import GENESIS, digest  # noqa: E402


def write_chain(directory, rows):
    """Write a valid MEASURED chain; rows are (plane, metrics) pairs."""
    prev, hashes = GENESIS, []
    for i, (plane, metrics) in enumerate(rows):
        receipt = {"plane": plane, "status": "MEASURED",
                   "machine": {"cpu": "unit-fixture", "ram_gb": 1, "gpu": "none"},
                   "measured_at": "2000-01-01T00:00:00Z", "method": "fixture-control",
                   "metrics": metrics, "prev_hash": prev}
        receipt["hash"] = prev = digest(receipt)
        (Path(directory) / f"{i:03d}.json").write_text(json.dumps(receipt), encoding="utf-8")
        hashes.append(prev)
    return hashes


def run_sync(*args, cwd=None):
    return subprocess.run([sys.executable, str(SYNC), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd, check=False)


class SyncResultsTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.receipts = self.dir / "receipts"
        self.receipts.mkdir()

    def test_committed_genesis_chain_exports_zero_rows(self):
        out = self.dir / "site" / "results.json"
        result = run_sync(ROOT / "receipts", out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("published 0 measured rows", result.stdout)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual((payload["count"], payload["results"]), (0, []))
        self.assertIsInstance(payload["generated_at"], str)

    def test_bare_output_filename_writes_to_working_directory(self):
        # Regression: os.makedirs("") raised FileNotFoundError with a traceback.
        result = run_sync(ROOT / "receipts", "results.json", cwd=self.dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertTrue((self.dir / "results.json").is_file())
        self.assertFalse((self.dir / "results.json.tmp").exists())

    def test_measured_rows_are_bound_to_their_receipt_hashes(self):
        hashes = write_chain(self.receipts, [("quant", {"score": 0.5}),
                                             ("quant", {"score": 0.6})])
        out = self.dir / "results.json"
        result = run_sync(self.receipts, out)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 2)
        self.assertEqual([row["receipt"] for row in payload["results"]], hashes)
        self.assertEqual([row["metrics"] for row in payload["results"]],
                         [{"score": 0.5}, {"score": 0.6}])

    def assert_aborts_without_writing(self):
        out = self.dir / "site" / "results.json"
        result = run_sync(self.receipts, out)
        self.assertEqual(result.returncode, 1)
        self.assertIn("aborting: nothing published", result.stdout)
        self.assertEqual(result.stderr, "")
        self.assertFalse(out.parent.exists())

    def test_tampered_receipt_aborts_and_writes_nothing(self):
        write_chain(self.receipts, [("quant", {"score": 0.5}), ("quant", {"score": 0.6})])
        first = self.receipts / "000.json"
        receipt = json.loads(first.read_text(encoding="utf-8"))
        receipt["metrics"]["score"] = 0.9  # changed without re-hashing
        first.write_text(json.dumps(receipt), encoding="utf-8")
        self.assert_aborts_without_writing()

    def test_nonfinite_metric_aborts_and_writes_nothing(self):
        # Regression: a hashed NaN metric used to verify and be exported as NaN.
        write_chain(self.receipts, [("quant", {"perplexity": float("nan")})])
        self.assertIn("NaN", (self.receipts / "000.json").read_text(encoding="utf-8"))
        self.assert_aborts_without_writing()

    def test_empty_receipt_directory_aborts_and_writes_nothing(self):
        self.assert_aborts_without_writing()


if __name__ == "__main__":
    unittest.main()
