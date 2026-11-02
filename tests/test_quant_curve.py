import sys, os
from dataclasses import replace
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quant_curve.pareto import (QuantPoint, pareto_frontier,
                                quality_retention, memory_reduction)
from quant_curve.gates import evaluate_level

REV = "weights-sha-abc123"

# Realistic-shaped measured set for a hypothetical 8B model (fixture values,
# clearly labeled test fixtures — NOT benchmark claims about any real model).
FP16 = QuantPoint("FP16", REV, 0.700, "task_acc", 16.0, 40.0)
Q8   = QuantPoint("Q8_0", REV, 0.699, "task_acc", 8.5, 55.0)
Q6   = QuantPoint("Q6_K", REV, 0.695, "task_acc", 6.6, 70.0)
Q4   = QuantPoint("Q4_K_M", REV, 0.685, "task_acc", 4.9, 95.0)
Q2   = QuantPoint("Q2_K", REV, 0.590, "task_acc", 3.1, 120.0)   # heavy quality loss
ALL = [FP16, Q8, Q6, Q4, Q2]


def test_frontier_excludes_dominated_point():
    # A strictly-worse point (higher memory AND lower quality than another) drops off.
    dominated = QuantPoint("Q5_BAD", REV, 0.680, "task_acc", 7.0, 80.0)  # worse than Q6 on both axes
    frontier = pareto_frontier(ALL + [dominated])
    assert all(p.level != "Q5_BAD" for p in frontier)


def test_frontier_keeps_tradeoff_chain():
    frontier = pareto_frontier(ALL)
    levels = [p.level for p in frontier]
    assert "Q2_K" in levels  # lowest memory — frontier despite low quality


def test_retention_and_reduction_math():
    assert abs(quality_retention(Q4, FP16) - 0.685/0.700) < 1e-12
    assert abs(memory_reduction(Q4, FP16) - (1 - 4.9/16.0)) < 1e-12


def test_metric_mismatch_raises():
    other = QuantPoint("X", REV, 0.9, "different_metric", 1.0)
    try:
        quality_retention(other, FP16)
        assert False, "should have raised"
    except ValueError:
        pass


def test_gate_promotes_clean_candidate():
    r = evaluate_level(Q4, FP16, ALL, min_retention=0.97, min_memory_reduction=0.25)
    assert r.status == "PROMOTED"
    assert r.on_frontier is True
    assert r.retention > 0.97 and r.mem_reduction > 0.25


def test_gate_blocks_without_baseline():
    r = evaluate_level(Q4, None, ALL)
    assert r.status == "BLOCKED"


def test_gate_blocks_unmeasured_candidate():
    ghost = QuantPoint("Q3_K_L", REV, 0.0, "task_acc", 4.0, measured=False)
    r = evaluate_level(ghost, FP16, ALL)
    assert r.status == "BLOCKED"


def test_gate_invalid_on_revision_mismatch():
    other_rev = QuantPoint("FP16", "weights-sha-DIFFERENT", 0.700, "task_acc", 16.0)
    r = evaluate_level(Q4, other_rev, ALL)
    assert r.status == "INVALID"


def test_gate_measured_but_not_promoted_when_retention_fails():
    r = evaluate_level(Q2, FP16, ALL, min_retention=0.98)
    assert r.status == "MEASURED"
    assert r.detail


def test_gate_frontier_ignores_other_revision_and_metric():
    # Numerically dominant points are not comparable evidence when they come
    # from different weights or a different quality metric.
    other_revision = QuantPoint("Q1_OTHER_REV", "weights-sha-other", 0.99,
                                "task_acc", 1.0, 200.0)
    other_metric = QuantPoint("Q1_OTHER_METRIC", REV, 0.99,
                              "different_metric", 1.0, 200.0)
    r = evaluate_level(Q4, FP16, ALL + [other_revision, other_metric],
                       min_retention=0.97, min_memory_reduction=0.25)
    assert r.status == "PROMOTED"
    assert r.on_frontier is True


def test_gate_requires_exact_candidate_frontier_membership():
    # A different point with the same level label must not confer frontier
    # membership on a candidate that was not part of the measured population.
    same_label_alias = QuantPoint("Q4_K_M", REV, 0.690, "task_acc", 4.0, 100.0)
    r = evaluate_level(Q4, FP16, [FP16, same_label_alias],
                       min_retention=0.97, min_memory_reduction=0.25)
    assert r.status == "MEASURED"
    assert r.on_frontier is False


def test_receipt_hashes_inputs():
    r = evaluate_level(Q4, FP16, ALL)
    assert len(r.inputs_hash) == 64


def test_receipt_hash_binds_frontier_population_and_thresholds():
    changed_q2 = QuantPoint("Q2_K", REV, 0.610, "task_acc", 3.1, 120.0)
    r1 = evaluate_level(Q4, FP16, ALL)
    r2 = evaluate_level(Q4, FP16, [FP16, Q8, Q6, Q4, changed_q2])
    r3 = evaluate_level(Q4, FP16, ALL, min_retention=0.97)
    assert r1.inputs_hash != r2.inputs_hash
    assert r1.inputs_hash != r3.inputs_hash


def _rejects(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError("malformed evidence must raise ValueError")


def test_gate_rejects_false_promotion_inputs():
    for field, values in {
        "quality": [float("inf"), float("-inf"), float("nan"), True, "0.7", 10 ** 400],
        "memory_gb": [-1.0, 0.0, float("inf"), float("nan"), False, "4.0"],
        "throughput_tok_s": [-1.0, float("inf"), float("nan"), True, "40.0"],
        "measured": ["false", "true", 1, 0, None],
    }.items():
        for value in values:
            malformed = replace(Q4, **{field: value})
            _rejects(lambda: evaluate_level(malformed, FP16, [FP16, malformed]))
            _rejects(lambda: pareto_frontier([malformed]))


def test_gate_validates_baseline_and_whole_hashed_population():
    malformed = replace(FP16, memory_gb=float("inf"))
    _rejects(lambda: evaluate_level(Q4, malformed, ALL))
    # Incomparable rows remain in inputs_hash and must also be canonical.
    unrelated = replace(Q2, model_revision="different", quality=float("nan"))
    _rejects(lambda: evaluate_level(Q4, FP16, ALL + [unrelated]))
    _rejects(lambda: quality_retention(Q4, malformed))
    _rejects(lambda: memory_reduction(Q4, malformed))


def test_gate_rejects_malformed_policy_thresholds():
    for value in [float("nan"), float("inf"), float("-inf"), -1, True, "0.98"]:
        _rejects(lambda: evaluate_level(Q4, FP16, ALL, min_retention=value))
        _rejects(lambda: evaluate_level(Q4, FP16, ALL, min_memory_reduction=value))
    _rejects(lambda: evaluate_level(Q4, FP16, ALL, min_memory_reduction=1.01))


def test_valid_numeric_boundaries_keep_evidence_states():
    zero_quality = replace(Q4, quality=0, throughput_tok_s=0)
    result = evaluate_level(zero_quality, FP16, [FP16, zero_quality], min_retention=0)
    assert result.status == "PROMOTED"
    json.dumps(result.to_dict(), allow_nan=False)
    assert evaluate_level(Q4, FP16, ALL, min_retention=1.01).status == "MEASURED"
    assert evaluate_level(Q4, FP16, ALL, min_memory_reduction=1).status == "MEASURED"
    negative_quality = replace(Q4, quality=-0.1)
    assert evaluate_level(negative_quality, FP16, [FP16, negative_quality]).status == "MEASURED"
    placeholder = replace(Q4, measured=False, memory_gb=0, throughput_tok_s=0)
    assert evaluate_level(placeholder, FP16, [placeholder]).status == "BLOCKED"
    assert pareto_frontier([placeholder]) == []


def test_finite_inputs_cannot_emit_infinite_derived_receipt_values():
    huge_quality = replace(Q4, quality=1e308)
    tiny_quality = replace(FP16, quality=1e-308)
    result = evaluate_level(huge_quality, tiny_quality, [huge_quality, tiny_quality])
    assert result.status == "INVALID"
    assert result.retention is None
    json.dumps(result.to_dict(), allow_nan=False)
    huge_memory = replace(Q4, memory_gb=1e308)
    tiny_memory = replace(FP16, memory_gb=1e-308)
    result = evaluate_level(huge_memory, tiny_memory, [huge_memory, tiny_memory])
    assert result.status == "INVALID"
    assert result.mem_reduction is None
    json.dumps(result.to_dict(), allow_nan=False)


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"ALL {len(fns)} QUANT-CURVE TESTS PASSED")
