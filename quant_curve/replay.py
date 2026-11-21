"""Opt-in replay of a gate calculation, not authentication of measurements."""
from dataclasses import fields

from .gates import _canonical, _evaluate, _gate_inputs, _hash
from .pareto import DEFAULT_POLICY, FRONTIER_POLICIES, QuantPoint


SCHEMA = "quant-curve/gate-replay/v1"
_POINT_KEYS = {f.name for f in fields(QuantPoint)}
_INPUT_KEYS = {"candidate", "baseline", "all_points", "thresholds"}
_THRESHOLD_KEYS = {"min_retention", "min_memory_reduction"}


def _fields(obj, expected, name):
    if type(obj) is not dict or obj.keys() != expected:
        raise ValueError(f"invalid {name} fields")


def _point(row):
    _fields(row, _POINT_KEYS, "point")
    if any(type(row[k]) is not str for k in ("level", "model_revision", "quality_metric")):
        raise ValueError("point identifiers must be strings")
    return QuantPoint(**row)


def _decision(inputs, policy):
    if type(policy) is not str or policy not in FRONTIER_POLICIES:
        raise ValueError("unregistered frontier policy")
    _fields(inputs, _INPUT_KEYS, "gate inputs")
    _fields(inputs["thresholds"], _THRESHOLD_KEYS, "threshold")
    if type(inputs["all_points"]) is not list:
        raise ValueError("ordered point list required")
    base = inputs["baseline"]
    return _evaluate(_point(inputs["candidate"]), None if base is None else _point(base),
                     [_point(p) for p in inputs["all_points"]], **inputs["thresholds"],
                     policy=FRONTIER_POLICIES[policy])


def record_replay(candidate, baseline, all_points, min_retention=0.98,
                  min_memory_reduction=0.25, *, policy=DEFAULT_POLICY) -> dict:
    """Make a deterministic JSON-compatible envelope; do not issue an authority receipt."""
    points = list(all_points)
    if (not isinstance(candidate, QuantPoint) or
            (baseline is not None and not isinstance(baseline, QuantPoint)) or
            any(not isinstance(p, QuantPoint) for p in points)):
        raise ValueError("each point must be a QuantPoint")
    thresholds = {"min_retention": min_retention, "min_memory_reduction": min_memory_reduction}
    inputs = _gate_inputs(candidate, baseline, points, thresholds)
    body = {"schema": SCHEMA, "policy": policy, "inputs": inputs, "decision": _decision(inputs, policy)}
    return {**body, "sha256": _hash(body)}


def replay_from_receipt(receipt, *, expected_sha256=None) -> dict:
    """Recompute the deterministic decision from a decoded v1 envelope or raise ValueError.

    Supply a digest from independent trusted storage to detect complete coherent
    replacement. Neither an embedded checksum nor a matching pin proves a run occurred.
    """
    _fields(receipt, {"schema", "policy", "inputs", "decision", "sha256"}, "replay envelope")
    if receipt["schema"] != SCHEMA:
        raise ValueError("unsupported replay schema")
    body = {k: v for k, v in receipt.items() if k != "sha256"}
    try:
        digest = _hash(body)
        if receipt["sha256"] != digest or (expected_sha256 is not None and expected_sha256 != digest):
            raise ValueError("replay digest mismatch")
        decision = _decision(body["inputs"], body["policy"])
        # Python equality collapses False/0, 1/1.0 and signed zero. Compare
        # canonical JSON bytes of the complete decision, not selected fields.
        if _canonical(body["decision"]) != _canonical(decision):
            raise ValueError("recorded decision differs from recomputation")
    except (TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("invalid replay data") from exc
    return decision
