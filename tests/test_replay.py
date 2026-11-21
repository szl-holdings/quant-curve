"""Synthetic gate decisions only; no run receipts, network or filesystem writes."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from quant_curve import DEFAULT_POLICY, FRONTIER_POLICIES, record_replay, replay_from_receipt
from quant_curve.gates import evaluate_level
from quant_curve.pareto import QuantPoint, pareto_frontier


B = QuantPoint("F", "r", 1, "acc", 2)
C = QuantPoint("Q", "r", 1, "acc", 1)


def reseal(bundle):
    body = {k: v for k, v in bundle.items() if k != "sha256"}
    bundle["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return bundle


class ReplayTests(unittest.TestCase):
    def test_legacy_receipt_shape_and_ordered_hash(self):
        old = evaluate_level(C, B, [B, C]).to_dict()
        self.assertEqual(list(old), ["gate_id", "status", "candidate_level", "baseline_level", "retention",
                                     "mem_reduction", "on_frontier", "thresholds", "inputs_hash", "timestamp", "detail"])
        self.assertEqual(old["inputs_hash"], "edd4db84b7b2695a5e0614e15f887079151473e81ed94c810fbba62a43e6fc46")
        with self.assertRaises(ValueError):
            replay_from_receipt(old)

    def test_every_emittable_status_round_trips_without_time_or_randomness(self):
        for c, b, pop, expected in [
            (C, B, [B, C], "PROMOTED"), (C, B, [B], "MEASURED"),
            (C, None, [], "BLOCKED"), (replace(C, measured=False), B, [], "BLOCKED"),
            (C, replace(B, measured=False), [C], "BLOCKED"),
            (C, replace(B, model_revision="other"), [B, C], "INVALID"),
            (C, replace(B, quality_metric="other"), [C], "INVALID"),
            (C, replace(B, quality=0), [C], "INVALID"),
        ]:
            with self.subTest(c=c, b=b, pop=pop):
                legacy = evaluate_level(c, b, pop).to_dict()
                for key in ("timestamp", "gate_id"):
                    legacy.pop(key)
                with patch("quant_curve.gates.time.time", side_effect=AssertionError), \
                     patch("quant_curve.gates.uuid.uuid4", side_effect=AssertionError):
                    r = record_replay(c, b, iter(pop))
                    self.assertEqual(r, record_replay(c, b, pop))
                    self.assertEqual(r["decision"]["status"], expected)
                    wire = json.loads(json.dumps(r, allow_nan=False))
                    self.assertEqual(replay_from_receipt(wire, expected_sha256=r["sha256"]), legacy)

    def test_registry_implements_actual_dominance_and_stable_ties(self):
        c2 = replace(C, level="A")
        worse_quality = replace(C, quality=0)
        self.assertEqual(pareto_frontier([C, B, c2, worse_quality]), [C, c2])
        self.assertEqual(pareto_frontier([c2, C, B]), [c2, C])
        a, b = (record_replay(C, B, pts) for pts in ([B, C, c2], [B, c2, C]))
        self.assertEqual(a["policy"], "pareto.weak-both-one-strict.memory-asc-stable/v1")
        self.assertIn(a["policy"], FRONTIER_POLICIES)
        self.assertNotEqual(a["sha256"], b["sha256"])
        self.assertNotEqual(a["decision"]["inputs_hash"], b["decision"]["inputs_hash"])
        with self.assertRaises(TypeError):
            FRONTIER_POLICIES["other"] = FRONTIER_POLICIES[DEFAULT_POLICY]
        with self.assertRaises(ValueError):
            record_replay(C, B, [B, C], policy="unknown")

    def test_recompute_even_when_tampered_envelope_is_resealed(self):
        good = record_replay(C, B, [B, C])
        # An internally consistent checksum cannot turn changed evidence, a
        # different status or bool/int/float equivalence into a verified result.
        for path, value in [
            (("policy",), "unknown"), (("schema",), "v99"),
            (("inputs", "candidate", "quality_metric"), "other"),
            (("inputs", "all_points", 0, "throughput_tok_s"), 99),
            (("inputs", "thresholds", "min_retention"), 2),
            (("decision", "status"), "FAILED"), (("decision", "retention"), 0.75),
            (("decision", "retention"), 1), (("decision", "on_frontier"), 1),
            (("decision", "mem_reduction"), 0.25), (("decision", "inputs_hash"), "0" * 64),
            (("decision", "thresholds", "min_retention"), 0.9),
            (("decision", "extra"), None), (("decision", "detail"), "different"),
        ]:
            with self.subTest(path=path, value=value), self.assertRaises(ValueError):
                edit = deepcopy(good)
                node = edit
                for key in path[:-1]:
                    node = node[key]
                node[path[-1]] = value
                replay_from_receipt(reseal(edit))

    def test_digest_and_independent_pin_are_separate(self):
        r = record_replay(C, B, [B, C])
        with self.assertRaises(ValueError):
            replay_from_receipt({**r, "sha256": "0" * 64})
        replacement = record_replay(C, B, [B, C], min_retention=2)
        self.assertEqual(replay_from_receipt(replacement)["status"], "MEASURED")
        with self.assertRaises(ValueError):
            replay_from_receipt(replacement, expected_sha256=r["sha256"])

    def test_malformed_structures_do_not_become_a_gate_decision(self):
        r = record_replay(C, B, [B, C])
        for change in [
            lambda d: d.pop("policy"), lambda d: d["inputs"]["candidate"].pop("measured"),
            lambda d: d["inputs"]["baseline"].update(memory_gb=True),
            lambda d: d["inputs"]["candidate"].update(quality_metric=[]),
            lambda d: d["inputs"]["all_points"][0].update(extra=0),
            lambda d: d["inputs"]["thresholds"].update(min_retention="0.98"),
            lambda d: d["inputs"].update(all_points={}),
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                edit = deepcopy(r)
                change(edit)
                replay_from_receipt(reseal(edit))
        nonfinite = deepcopy(r)
        nonfinite["inputs"]["candidate"]["quality"] = float("nan")
        with self.assertRaises(ValueError):
            replay_from_receipt(nonfinite)
