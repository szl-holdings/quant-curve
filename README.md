# Quant Curve — Quantization Quality-vs-Resource Gates

The third leg of the SZL bench suite. `frontier-bench` measures engines,
`retrieval-bench` measures retrieval — `quant-curve` answers the deployment
question: which quantization level keeps quality while cutting memory,
proven on a Pareto frontier with receipts.

## Contract

- Pure math over measured inputs only. The package never invents a
  measurement; points arrive from real harness runs (e.g. frontier-bench).
- Five-state gates: MEASURED / BLOCKED / INVALID / FAILED / PROMOTED.
- UNMEASURED placeholder points are never frontier-eligible.
- Cross-revision or cross-metric comparisons return INVALID — they are
  not evidence.
- Every gate evaluation emits a SHA-256 receipt over its exact inputs.

## Promotion rule (defaults)

A candidate level is PROMOTED against the measured FP16-class baseline of
the same weights revision and metric only when all hold:

1. quality_retention >= 0.98
2. memory_reduction >= 0.25
3. the candidate sits on the Pareto frontier (quality up, memory down)

## Usage

```python
from quant_curve.pareto import QuantPoint
from quant_curve.gates import evaluate_level

fp16 = QuantPoint("FP16", "weights-rev-abc", 0.700, "task_acc", 16.0, 40.0)
q4   = QuantPoint("Q4_K_M", "weights-rev-abc", 0.685, "task_acc", 4.9, 95.0)

receipt = evaluate_level(q4, fp16, [fp16, q4])
print(receipt.status)     # PROMOTED | MEASURED | BLOCKED | INVALID
```

## Tests

```bash
python tests/test_quant_curve.py   # 10 tests, stdlib only
```

CI runs the suite on Python 3.11 and 3.12 on every push and PR.

## Files

- quant_curve/pareto.py — Pareto frontier, retention/reduction math
- quant_curve/gates.py — five-state promotion gate + receipts
- tests/test_quant_curve.py — 10 tests over labeled fixtures
- .github/workflows/ci.yml — CI on push/PR

Doctrine v11. Apache-2.0. Λ = Conjecture 1 (advisory).
