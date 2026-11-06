"""HTTP results route: honest states over the file tools/sync_results.py exports.

Needs the ``test`` extra (fastapi + httpx). Fixture receipts are unit fixtures,
not measurements.
"""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from app import main  # noqa: E402
import sync_results  # noqa: E402
from verify.verifier import GENESIS, digest  # noqa: E402

VALID = {"generated_at": "2000-01-01T00:00:00Z", "count": 1,
         "results": [{"plane": "quant", "metrics": {"x": 1.5}, "receipt": "0" * 64}]}


class ResultsRouteTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.client = TestClient(main.app, raise_server_exceptions=False)

    def get_results(self, path):
        with mock.patch.object(main, "RESULTS", str(path)):
            response = self.client.get("/api/results")
        self.assertEqual(response.status_code, 200, response.text)  # never an error page
        body = response.json()
        self.assertEqual(body["plane"], "quant")
        self.assertEqual(body["count"], len(body["results"]))
        return body

    def export(self, receipts_dir):
        out = self.dir / "site" / "results.json"
        self.assertEqual(sync_results.main(str(receipts_dir), str(out)), 0)
        return out

    def test_healthz(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["status"], response.json()["plane"]), ("ok", "quant"))

    def test_missing_results_file_is_unavailable(self):
        body = self.get_results(self.dir / "absent.json")
        self.assertEqual((body["state"], body["results"], body["generated_at"]),
                         ("UNAVAILABLE", [], None))

    def test_export_of_committed_genesis_chain_is_empty_honest(self):
        body = self.get_results(self.export(ROOT / "receipts"))
        self.assertEqual((body["state"], body["results"]), ("EMPTY_HONEST", []))
        self.assertIsInstance(body["generated_at"], str)

    def test_export_with_measured_rows_serves_only_quant_rows(self):
        receipts = self.dir / "receipts"
        receipts.mkdir()
        prev = GENESIS
        for i, (plane, score) in enumerate([("quant", 0.5), ("engine", 0.7), ("quant", 0.6)]):
            receipt = {"plane": plane, "status": "MEASURED",
                       "machine": {"cpu": "unit-fixture", "ram_gb": 1, "gpu": "none"},
                       "measured_at": "2000-01-01T00:00:00Z", "method": "fixture-control",
                       "metrics": {"score": score}, "prev_hash": prev}
            receipt["hash"] = prev = digest(receipt)
            (receipts / f"{i:03d}.json").write_text(json.dumps(receipt), encoding="utf-8")
        out = self.export(receipts)
        exported = json.loads(out.read_text(encoding="utf-8"))["results"]
        body = self.get_results(out)
        self.assertEqual(body["state"], "MEASURED")
        self.assertEqual(body["results"], [row for row in exported if row["plane"] == "quant"])
        self.assertEqual([row["metrics"]["score"] for row in body["results"]], [0.5, 0.6])

    def test_malformed_results_are_unavailable_not_empty(self):
        path = self.dir / "results.json"
        path.write_text(json.dumps(VALID), encoding="utf-8")
        self.assertEqual(self.get_results(path)["state"], "MEASURED")  # control
        valid_text = json.dumps(VALID)
        cases = {
            "truncated JSON": '{"results": [',
            "top-level list": "[]",
            "missing results": json.dumps({"generated_at": "x", "count": 0}),
            "count mismatch": json.dumps(dict(VALID, count=2)),
            "boolean count": json.dumps(dict(VALID, count=True)),
            "missing generated_at": json.dumps({"count": 1, "results": VALID["results"]}),
            "non-object row": json.dumps(dict(VALID, results=[1])),
            "unknown plane": json.dumps(dict(VALID, results=[{"plane": "other"}])),
            "NaN metric": valid_text.replace("1.5", "NaN"),
            "overflowing float": valid_text.replace("1.5", "1e400"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                path.write_text(text, encoding="utf-8")
                with self.assertLogs("quant_curve.api", "WARNING"):
                    body = self.get_results(path)
                self.assertEqual((body["state"], body["results"], body["generated_at"]),
                                 ("UNAVAILABLE", [], None))
        with self.subTest("invalid UTF-8"):
            path.write_bytes(b"\xff\xfe{}")
            self.assertEqual(self.get_results(path)["state"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
