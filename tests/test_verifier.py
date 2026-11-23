"""Native receipt API controls, using stdlib unittest only."""
import json
import hashlib
from pathlib import Path
import sys
import subprocess
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify.verifier import GENESIS, check_receipt, digest, verify


class NativeVerifierTests(unittest.TestCase):
    def test_recorded_native_repair_report_recomputes(self):
        path = Path(__file__).resolve().parents[1] / "evidence/eclipse-native-repaired-20260905.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        receipt = report.pop("receipt")
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.assertEqual(hashlib.sha256(encoded.encode()).hexdigest(), receipt)
        self.assertEqual(report["sensitivity"], "10/10")
        self.assertEqual(report["blind_spots"], [])
        self.assertTrue(report["baseline"]["valid"])
        self.assertEqual(report["baseline"]["detail"]["measured_count"], 3)

    def test_empty_collection_and_iterator_fail_closed(self):
        for paths in ([], (), iter(())):
            errors, measured = verify(paths)
            self.assertTrue(errors)
            self.assertEqual(measured, [])

    def test_missing_collection_fails_closed(self):
        errors, measured = verify(None)
        self.assertTrue(errors)
        self.assertEqual(measured, [])

    def test_nonobject_json_returns_validation_errors(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            for value in (None, [], ["plane"], "MEASURED", 42, True):
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    errors, measured = verify([str(path)])
                    self.assertTrue(errors)
                    self.assertIn("JSON object", errors[0])
                    self.assertEqual(measured, [])

    def test_enum_containers_return_validation_errors(self):
        receipt = {"plane": "retrieval", "status": "BLOCKED",
                   "machine": {"cpu": "fixture", "ram_gb": 1, "gpu": "none"},
                   "measured_at": "2000-01-01T00:00:00Z", "method": "fixture",
                   "metrics": {}, "prev_hash": GENESIS}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            for field in ("plane", "status"):
                for value in ([], {}):
                    with self.subTest(field=field, value=value):
                        malformed = dict(receipt, **{field: value})
                        malformed["hash"] = digest(malformed)
                        path.write_text(json.dumps(malformed), encoding="utf-8")
                        errors, measured = verify([str(path)])
                        self.assertTrue(any(f"unknown {field}:" in e for e in errors))
                        self.assertEqual(measured, [])

    def test_nonfinite_numbers_fail_closed(self):
        # The stdlib parser reads NaN/Infinity tokens and overflows 1e400 to
        # inf by default. Such a receipt used to verify (its hash recomputes)
        # and was then exported as non-standard JSON.
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            for token in ("NaN", "Infinity", "-Infinity", "1e400"):
                with self.subTest(token=token):
                    receipt = {"plane": "quant", "status": "MEASURED",
                               "machine": {"cpu": "unit-fixture", "ram_gb": 1, "gpu": "none"},
                               "measured_at": "2000-01-01T00:00:00Z", "method": "fixture",
                               "metrics": {"perplexity": "TOKEN"}, "prev_hash": GENESIS}
                    permissive = json.loads(json.dumps(receipt).replace('"TOKEN"', token))
                    receipt["hash"] = digest(permissive)
                    text = json.dumps(receipt).replace('"TOKEN"', token)
                    # Control: apart from the token the receipt is valid.
                    self.assertEqual(check_receipt(json.loads(text), 0), [])
                    path.write_text(text, encoding="utf-8")
                    errors, measured = verify([str(path)])
                    self.assertEqual(len(errors), 1)
                    self.assertIn("unreadable JSON", errors[0])
                    self.assertEqual(measured, [])

    def test_duplicate_json_members_fail_closed_at_every_depth(self):
        # A last-key-wins parser can accept these, with a matching canonical
        # digest, while a first-key-wins consumer sees a different result.
        receipt = {"plane": "quant", "status": "MEASURED",
                   "machine": {"cpu": "unit-fixture", "ram_gb": 1, "gpu": "none"},
                   "measured_at": "2000-01-01T00:00:00Z",
                   "method": "fixture", "metrics": {"score": 0.5},
                   "prev_hash": GENESIS}
        receipt["hash"] = digest(receipt)
        canonical = json.dumps(receipt)
        variants = (
            canonical.replace('"status": "MEASURED"',
                              '"status": "BLOCKED", "status": "MEASURED"'),
            canonical.replace('"score": 0.5',
                              '"score": 0.1, "score": 0.5'),
            canonical.replace('"cpu": "unit-fixture"',
                              '"cpu": "false-source", "cpu": "unit-fixture"'),
            canonical.replace('"hash": "' + receipt["hash"] + '"',
                              '"hash": "' + "f" * 64 + '", "hash": "' + receipt["hash"] + '"'),
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            for raw in variants:
                with self.subTest(raw_sha256=hashlib.sha256(raw.encode()).hexdigest()):
                    self.assertNotEqual(raw, canonical)
                    # Negative control: last-key-wins maps to the same payload.
                    self.assertEqual(json.loads(raw), receipt)
                    path.write_text(raw, encoding="utf-8")
                    errors, measured = verify([str(path)])
                    self.assertEqual(measured, [])
                    self.assertEqual(len(errors), 1)
                    self.assertIn("duplicate JSON member", errors[0])
                    self.assertNotIn("false-source", errors[0])

            # Distinct keys at multiple nesting levels remain admissible.
            path.write_text(canonical, encoding="utf-8")
            errors, measured = verify([str(path)])
            self.assertEqual(errors, [])
            self.assertEqual(measured, [str(path)])

    def test_cli_reports_malformed_receipt_without_traceback(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text("null", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] /
                                     "verify/verifier.py"), str(path)],
                capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("FAIL", result.stdout)
            self.assertIn("checked=1 measured=0 errors=1", result.stdout)
            self.assertEqual(result.stderr, "")

    def test_valid_nonempty_control_and_changed_payload(self):
        receipt = {"plane": "retrieval", "status": "MEASURED",
                   "machine": {"cpu": "unit-fixture", "ram_gb": 1, "gpu": "none"},
                   "measured_at": "2000-01-01T00:00:00Z", "method": "fixture-control",
                   "metrics": {"score": 0.5}, "prev_hash": GENESIS}
        receipt["hash"] = digest(receipt)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(receipt), encoding="utf-8")
            errors, measured = verify([str(path)])
            self.assertEqual(errors, [])
            self.assertEqual(measured, [str(path)])
            receipt["metrics"]["score"] = 0.9
            path.write_text(json.dumps(receipt), encoding="utf-8")
            errors, _ = verify([str(path)])
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
