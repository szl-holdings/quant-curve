"""
Pareto frontier for quantization quality-vs-resource trade-offs.

A point is Pareto-optimal if no other point has both strictly-better quality
AND strictly-lower memory. Pure math over measured inputs only — the module
never invents a measurement.
"""
from dataclasses import dataclass
import math
from typing import List, Optional


@dataclass(frozen=True)
class QuantPoint:
    level: str              # e.g. "FP16", "Q8_0", "Q6_K", "Q4_K_M"
    model_revision: str     # exact weights revision measured
    quality: float          # quality metric value (higher = better), e.g. task accuracy
    quality_metric: str     # name of the metric, e.g. "mmlu_acc", "winogrande_acc"
    memory_gb: float        # measured resident memory (lower = better)
    throughput_tok_s: Optional[float] = None
    measured: bool = True   # False marks an UNMEASURED placeholder — never frontier-eligible


def _finite_number(value, name: str, *, positive: bool = False,
                   nonnegative: bool = False) -> None:
    """Reject coercions and non-finite values before they influence evidence."""
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean or string")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _validate_point(point: QuantPoint) -> None:
    if not isinstance(point, QuantPoint):
        raise ValueError("each point must be a QuantPoint")
    if type(point.measured) is not bool:
        raise ValueError("measured must be a boolean")
    _finite_number(point.quality, "quality")
    _finite_number(point.memory_gb, "memory_gb", positive=point.measured,
                   nonnegative=True)
    if point.throughput_tok_s is not None:
        _finite_number(point.throughput_tok_s, "throughput_tok_s", nonnegative=True)


def pareto_frontier(points: List[QuantPoint]) -> List[QuantPoint]:
    """Return the subset of measured points that are Pareto-optimal
    (maximize quality, minimize memory), sorted by memory ascending."""
    points = list(points)
    for point in points:
        _validate_point(point)
    measured = [p for p in points if p.measured]
    frontier = []
    for p in measured:
        dominated = any(
            q is not p and q.quality >= p.quality and q.memory_gb <= p.memory_gb
            and (q.quality > p.quality or q.memory_gb < p.memory_gb)
            for q in measured
        )
        if not dominated:
            frontier.append(p)
    return sorted(frontier, key=lambda p: p.memory_gb)


def quality_retention(candidate: QuantPoint, baseline: QuantPoint) -> float:
    """candidate.quality / baseline.quality. Caller guarantees same metric."""
    _validate_point(candidate)
    _validate_point(baseline)
    if candidate.quality_metric != baseline.quality_metric:
        raise ValueError("cannot compare different quality metrics")
    if baseline.quality <= 0:
        raise ValueError("baseline quality must be positive")
    retention = candidate.quality / baseline.quality
    _finite_number(retention, "quality retention")
    return retention


def memory_reduction(candidate: QuantPoint, baseline: QuantPoint) -> float:
    """1 - candidate.memory/baseline.memory (0.75 = candidate uses 75% less)."""
    _validate_point(candidate)
    _validate_point(baseline)
    if baseline.memory_gb <= 0:
        raise ValueError("baseline memory must be positive")
    reduction = 1 - candidate.memory_gb / baseline.memory_gb
    if not math.isfinite(reduction):
        raise ValueError("memory reduction must be finite")
    return reduction
