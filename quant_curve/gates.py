"""
Promotion gates for quantization levels. Five-state contract, same family
as retrieval-bench: MEASURED / BLOCKED / INVALID / FAILED / PROMOTED.

A level is PROMOTED only if, against a measured FP16-class baseline of the
SAME weights revision and SAME metric:
- quality_retention >= min_retention (default 0.98)
- memory_reduction >= min_memory_reduction (default 0.25)
- the exact candidate sits on the Pareto frontier formed only from measured
  points for that same weights revision and quality metric

Missing baseline or zero measured points -> BLOCKED. Metric or revision
mismatch -> INVALID. Never fabricates a number.
"""
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from .pareto import (DEFAULT_POLICY, FRONTIER_POLICIES, QuantPoint, pareto_frontier,
                     quality_retention, memory_reduction, _finite_number,
                     _validate_point, _policy_frontier)


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, allow_nan=False).encode()


def _hash(obj) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _gate_inputs(candidate, baseline, points, thresholds):
    return {"candidate": vars(candidate).copy(),
            "baseline": vars(baseline).copy() if baseline is not None else None,
            "all_points": [vars(p).copy() for p in points],
            "thresholds": thresholds.copy()}


@dataclass
class GateReceipt:
    gate_id: str
    status: str
    candidate_level: Optional[str]
    baseline_level: Optional[str]
    retention: Optional[float]
    mem_reduction: Optional[float]
    on_frontier: Optional[bool]
    thresholds: dict
    inputs_hash: str
    timestamp: float
    detail: str = ""

    def to_dict(self):
        return self.__dict__.copy()


def evaluate_level(candidate: QuantPoint, baseline: Optional[QuantPoint],
                   all_points: List[QuantPoint],
                   min_retention: float = 0.98,
                   min_memory_reduction: float = 0.25) -> GateReceipt:
    decision = _evaluate(candidate, baseline, all_points, min_retention, min_memory_reduction,
                         FRONTIER_POLICIES[DEFAULT_POLICY])
    return GateReceipt(gate_id=str(uuid.uuid4()), timestamp=time.time(), **decision)


def _evaluate(candidate, baseline, all_points, min_retention, min_memory_reduction, policy):
    """Pure gate decision; issuance UUID/time are not computational inputs."""
    points = list(all_points)
    # Malformed inputs cannot form measured evidence or a canonical receipt.
    # Validate the entire hashed population, including incomparable points.
    _validate_point(candidate)
    if baseline is not None:
        _validate_point(baseline)
    for point in points:
        _validate_point(point)
    _finite_number(min_retention, "min_retention", nonnegative=True)
    _finite_number(min_memory_reduction, "min_memory_reduction", nonnegative=True)
    if min_memory_reduction > 1:
        raise ValueError("min_memory_reduction must not exceed 1")
    thresholds = {"min_retention": min_retention,
                  "min_memory_reduction": min_memory_reduction}
    # Bind every value that can affect the gate decision. The previous contract
    # hashed only n_points, which allowed different frontier populations of the
    # same length to share an inputs_hash even when they changed promotion.
    inputs_hash = _hash(_gate_inputs(candidate, baseline, points, thresholds))

    def result(status, baseline_level, detail, retention=None, reduction=None, frontier=None):
        return dict(status=status, candidate_level=candidate.level, baseline_level=baseline_level,
                    retention=retention, mem_reduction=reduction, on_frontier=frontier,
                    thresholds=thresholds, inputs_hash=inputs_hash, detail=detail)

    if not candidate.measured:
        return result("BLOCKED", None, "candidate is not a measured point")

    if baseline is None or not baseline.measured:
        return result("BLOCKED", None, "no measured baseline available")

    try:
        if candidate.model_revision != baseline.model_revision:
            return result("INVALID", baseline.level,
                          "weights revision mismatch — cross-revision comparison is not evidence")
        ret = quality_retention(candidate, baseline)
        red = memory_reduction(candidate, baseline)
    except ValueError as e:
        return result("INVALID", baseline.level, str(e))

    # Pareto dominance is meaningful only inside one weights revision and one
    # quality metric. Cross-revision or cross-metric points must not veto or
    # confer frontier membership. Match the exact immutable candidate rather
    # than accepting any different point that happens to share its level name.
    comparable_points = [
        p for p in points
        if p.model_revision == candidate.model_revision
        and p.quality_metric == candidate.quality_metric
    ]
    on_frontier = candidate in _policy_frontier(comparable_points, policy)
    promoted = ret >= min_retention and red >= min_memory_reduction and on_frontier
    return result("PROMOTED" if promoted else "MEASURED", baseline.level,
                  "" if promoted else "measured but did not clear all promotion thresholds", ret, red, on_frontier)
