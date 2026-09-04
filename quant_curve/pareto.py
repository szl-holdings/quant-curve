"""
Pareto frontier for quantization quality-vs-resource trade-offs.

A point is Pareto-optimal if no other point has both strictly-better quality
AND strictly-lower memory. Pure math over measured inputs only — the module
never invents a measurement.
"""
from dataclasses import dataclass
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


def pareto_frontier(points: List[QuantPoint]) -> List[QuantPoint]:
    """Return the subset of measured points that are Pareto-optimal
    (maximize quality, minimize memory), sorted by memory ascending."""
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
    if candidate.quality_metric != baseline.quality_metric:
        raise ValueError("cannot compare different quality metrics")
    if baseline.quality <= 0:
        raise ValueError("baseline quality must be positive")
    return candidate.quality / baseline.quality


def memory_reduction(candidate: QuantPoint, baseline: QuantPoint) -> float:
    """1 - candidate.memory/baseline.memory (0.75 = candidate uses 75% less)."""
    if baseline.memory_gb <= 0:
        raise ValueError("baseline memory must be positive")
    return 1 - candidate.memory_gb / baseline.memory_gb
