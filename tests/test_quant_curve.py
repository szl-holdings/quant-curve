import sys, os
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

def test_receipt_hashes_inputs():
    r = evaluate_level(Q4, FP16, ALL)
    assert len(r.inputs_hash) == 64


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"ALL {len(fns)} QUANT-CURVE TESTS PASSED")
