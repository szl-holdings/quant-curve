# Quant Curve

<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

Measured quantization evidence for the SZL stack — quality vs precision, admitted only from verifiable runs.

## What this is

The honest companion to quantization claims: quality-vs-precision curves and throughput numbers may be published only when they are traceable to reviewed run receipts. Unmeasured or unverifiable data stays absent rather than being rendered as measured evidence.

| Path | Role |
|---|---|
| `quant_curve/` | Pareto frontier (`pareto.py`) and promotion gates (`gates.py`) over caller-supplied measured points. Standard library only. |
| `verify/verifier.py` | Fail-closed integrity check of a receipt chain: schema, strict JSON, per-receipt SHA-256, `prev_hash` links. |
| `tools/sync_results.py` | Exports the MEASURED receipts of a verified chain to `site/results.json`; on any error it exits 1 and writes nothing. |
| `app/main.py` | Read-only FastAPI surface for that export (`/healthz`, `/api/results`). Deployment: [deploy/RUNBOOK.md](deploy/RUNBOOK.md). |
| `receipts/` | The receipt chain. Today it holds only the BLOCKED genesis receipt. |

## Guarantees

- **Measured rows only** — publication accepts actual measured-run receipts; fixtures, projections, and BLOCKED genesis records are not benchmark rows.
- **Quality and throughput together** — when a measured row is admitted, quality and tokens/sec remain bound to the same machine/date/method evidence.
- **Receipts** — every admitted point is hash-chained into the run ledger, so editing or reordering a receipt breaks verification. The chain is unsigned: tamper evidence holds against a head hash recorded elsewhere, not on its own (see [Proof boundary](#proof-boundary)).
- **Comparable frontiers only** — promotion compares the exact candidate only against points from the same weights revision and quality metric.
- **Decision-bound evidence** — gate input hashes bind the candidate, baseline, full frontier population, and thresholds that can affect promotion.
- **Fail-closed display** — unverifiable runs appear as absent.

## Install

Python 3.11 to 3.14. The `quant_curve` library has no third-party dependencies.

```bash
python -m pip install -e '.[test]'   # library + test tools (pytest, httpx2, fastapi)
python -m pip install -e '.[api]'    # library + fastapi/uvicorn to serve app/main.py
```

The container does not use these extras: it installs the hash-locked `requirements.txt`, compiled from `requirements.in`.

## Usage

Gate a candidate level against a baseline. The numbers are illustrative fixture values, not measurements of any model:

```python
from quant_curve.gates import evaluate_level
from quant_curve.pareto import QuantPoint

fp16 = QuantPoint("FP16", "rev-a", 0.700, "task_acc", 16.0)
q4 = QuantPoint("Q4_K_M", "rev-a", 0.685, "task_acc", 4.9)
r = evaluate_level(q4, fp16, [fp16, q4])
print(r.status, round(r.retention, 4), round(r.mem_reduction, 4), r.on_frontier)
# MEASURED 0.9786 0.6937 True
```

Retention 0.9786 is below the default `min_retention` of 0.98, so the level is MEASURED, not PROMOTED; with `min_retention=0.97` the same call returns PROMOTED. `evaluate_level` returns BLOCKED, INVALID, MEASURED or PROMOTED. FAILED is part of the receipt schema the verifier accepts; these gates never emit it.

Verify the committed chain, export it, and serve the export:

```bash
python verify/verifier.py receipts/*.json
# checked=1 measured=0 errors=0
python tools/sync_results.py receipts site/results.json
# published 0 measured rows -> site/results.json
uvicorn app.main:app --port 7860          # needs the api extra; then, in a second shell:
curl -s http://127.0.0.1:7860/api/results
# {"plane":"quant","state":"EMPTY_HONEST","generated_at":"...","count":0,"results":[],"served_at":"..."}
```

`/api/results` reports one of three states, always with HTTP 200 and never with invented rows:

- `MEASURED`: the export contains quant rows.
- `EMPTY_HONEST`: a valid export with no quant rows (today's state).
- `UNAVAILABLE`: the results file is missing, unreadable or malformed. No rows are served and the reason is logged.

## Tests

```bash
python -m pytest -q
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on Python 3.11 to 3.14. It first runs the stdlib-only test files with no third-party package installed, then installs the hash-locked [`requirements/ci/test.txt`](requirements/ci/test.txt) and runs the full suite, including the HTTP route. The `receipt-verification` workflow ([`bench.yml`](.github/workflows/bench.yml)) re-verifies `receipts/*.json` on every push.

## Proof boundary

What the code establishes:

- `verify/verifier.py`: each receipt is strict JSON with the schema fields, its declared `hash` equals the SHA-256 of its canonical body, and its `prev_hash` links it to the receipt before it.
- `evaluate_level`: a deterministic decision over the points it is given. `inputs_hash` binds the candidate, the baseline, the whole population and the thresholds.

What it does not establish:

- Authorship, time or hardware. Receipts are unsigned, so a chain rewritten from the start with every hash recomputed still verifies. Tamper evidence depends on a head hash recorded elsewhere, such as the revision pin in the consolidated publisher.
- That a receipt came from a real run. The verifier cannot tell a fixture from a measurement. Hardware identity and receipt authentication are checked by the consolidated publisher in frontier-bench, not here.
- Any measurement at all. Nothing in this repository runs a model, and there are zero measured rows.
- Re-verification at serve time. `/api/results` serves the file `tools/sync_results.py` exported; it does not re-check receipts.

[`evidence/eclipse-native-repaired-20260905.json`](evidence/eclipse-native-repaired-20260905.json) is a historical szl-eclipse control report: 10 of 10 local-fixture mutations caught by an earlier verifier. Its recorded `verifier_sha256` matches no committed version of `verify/verifier.py`, so it is not evidence about the current verifier.

## Public surface

The consolidated bench targets the Hugging Face Space [SZLHOLDINGS/szl-bench-suite](https://huggingface.co/spaces/SZLHOLDINGS/szl-bench-suite) (Quantization tab) — one evidence surface for engine, retrieval, and quantization claims. As of 2026-11-06 that Space is private on the Hub: anonymous requests to the link return HTTP 401, so it is not yet publicly viewable.

Hardware identity is declared by benchmark receipts and checked by the consolidated publisher's dedicated-node policy. Receipt authentication proves an operator assertion; this repository does **not** claim an independent hardware witness.

**Division of labor:** this repo owns quantization receipts and their fail-closed verifier. The single Space publisher lives in [szl-holdings/frontier-bench](https://github.com/szl-holdings/frontier-bench), which verifies and combines all three planes before one atomic Space commit. The measurement harness that produces receipted quantization runs lives in [szl-holdings/szl-quant-bench](https://github.com/szl-holdings/szl-quant-bench); the Wave 1 consolidated bakeoff report is [szl-holdings/szl-wave1-report](https://github.com/szl-holdings/szl-wave1-report).

Source admission, Hugging Face publication, product/runtime status, and proof/evaluation status are separate evidence layers. Repository CI alone is not a publication or runtime claim.

## Numeric admission

The Python gate and Pareto helpers reject malformed inputs with `ValueError`
before hashing or comparison. Numeric evidence must be finite Python integers
or floats; booleans and numeric strings are not measurements. Measured memory
must be positive, optional throughput must be nonnegative, and `measured` must
be an actual boolean. Unmeasured placeholders may use zero memory. Quality is
not restricted to a particular metric's range; baseline quality must still be
positive for a retention ratio.

Retention thresholds are finite and nonnegative (values above one can require
improvement). Memory-reduction thresholds are finite fractions from zero to
one. Validation covers the complete population bound by `inputs_hash`, including
incomparable rows. Valid inputs retain the existing evidence states; arithmetic
overflow produces `INVALID`, never a promoted point with an infinite receipt.
These functions are a library API and are not invoked by the HTTP results route.

## Status

Current source state contains only the BLOCKED genesis receipt: **zero admitted measured quantization rows**. Real benchmark execution and signed raw evidence remain the responsibility of the dedicated-node measurement producer before any measured point can be published.

## Links

- Source: [szl-holdings/quant-curve](https://github.com/szl-holdings/quant-curve) · [SECURITY.md](SECURITY.md) · [CITATION.cff](CITATION.cff)
- Publisher: [szl-holdings/frontier-bench](https://github.com/szl-holdings/frontier-bench) · measurement harness: [szl-holdings/szl-quant-bench](https://github.com/szl-holdings/szl-quant-bench)
- Hugging Face: models, datasets and Spaces are published under the [SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) org.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
