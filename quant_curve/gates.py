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

from .pareto import QuantPoint, pareto_frontier, quality_retention, memory_reduction


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


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
    points = list(all_points)
    thresholds = {"min_retention": min_retention,
                  "min_memory_reduction": min_memory_reduction}
    # Bind every value that can affect the gate decision. The previous contract
    # hashed only n_points, which allowed different frontier populations of the
    # same length to share an inputs_hash even when they changed promotion.
    inputs_hash = _hash({
        "candidate": candidate.__dict__,
        "baseline": baseline.__dict__ if baseline else None,
        "all_points": [p.__dict__ for p in points],
        "thresholds": thresholds,
    })
    ts = time.time()

    if not candidate.measured:
        return GateReceipt(gate_id=str(uuid.uuid4()), status="BLOCKED",
                           candidate_level=candidate.level, baseline_level=None,
                           retention=None, mem_reduction=None, on_frontier=None,
                           thresholds=thresholds, inputs_hash=inputs_hash,
                           timestamp=ts, detail="candidate is not a measured point")

    if baseline is None or not baseline.measured:
        return GateReceipt(gate_id=str(uuid.uuid4()), status="BLOCKED",
                           candidate_level=candidate.level, baseline_level=None,
                           retention=None, mem_reduction=None, on_frontier=None,
                           thresholds=thresholds, inputs_hash=inputs_hash,
                           timestamp=ts, detail="no measured baseline available")

    try:
        if candidate.model_revision != baseline.model_revision:
            return GateReceipt(gate_id=str(uuid.uuid4()), status="INVALID",
                               candidate_level=candidate.level, baseline_level=baseline.level,
                               retention=None, mem_reduction=None, on_frontier=None,
                               thresholds=thresholds, inputs_hash=inputs_hash,
                               timestamp=ts,
                               detail="weights revision mismatch — cross-revision comparison is not evidence")
        ret = quality_retention(candidate, baseline)
        red = memory_reduction(candidate, baseline)
    except ValueError as e:
        return GateReceipt(gate_id=str(uuid.uuid4()), status="INVALID",
                           candidate_level=candidate.level, baseline_level=baseline.level,
                           retention=None, mem_reduction=None, on_frontier=None,
                           thresholds=thresholds, inputs_hash=inputs_hash,
                           timestamp=ts, detail=str(e))

    # Pareto dominance is meaningful only inside one weights revision and one
    # quality metric. Cross-revision or cross-metric points must not veto or
    # confer frontier membership. Match the exact immutable candidate rather
    # than accepting any different point that happens to share its level name.
    comparable_points = [
        p for p in points
        if p.model_revision == candidate.model_revision
        and p.quality_metric == candidate.quality_metric
    ]
    on_frontier = candidate in pareto_frontier(comparable_points)
    promoted = ret >= min_retention and red >= min_memory_reduction and on_frontier
    return GateReceipt(
        gate_id=str(uuid.uuid4()),
        status="PROMOTED" if promoted else "MEASURED",
        candidate_level=candidate.level, baseline_level=baseline.level,
        retention=ret, mem_reduction=red, on_frontier=on_frontier,
        thresholds=thresholds, inputs_hash=inputs_hash, timestamp=ts,
        detail="" if promoted else "measured but did not clear all promotion thresholds",
    )
