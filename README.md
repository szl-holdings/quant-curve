# Quant Curve

Measured quantization evidence for the SZL stack — quality vs precision, admitted only from verifiable runs.

## What this is

The honest companion to quantization claims: quality-vs-precision curves and throughput numbers may be published only when they are traceable to reviewed run receipts. Unmeasured or unverifiable data stays absent rather than being rendered as measured evidence.

## Guarantees

- **Measured rows only** — publication accepts actual measured-run receipts; fixtures, projections, and BLOCKED genesis records are not benchmark rows.
- **Quality and throughput together** — when a measured row is admitted, quality and tokens/sec remain bound to the same machine/date/method evidence.
- **Receipts** — every admitted point is hash-chained into the run ledger so history is tamper-evident.
- **Comparable frontiers only** — promotion compares the exact candidate only against points from the same weights revision and quality metric.
- **Decision-bound evidence** — gate input hashes bind the candidate, baseline, full frontier population, and thresholds that can affect promotion.
- **Fail-closed display** — unverifiable runs appear as absent.

## Public surface

The consolidated public bench lives at [betterwithage/szl-bench-suite](https://huggingface.co/spaces/betterwithage/szl-bench-suite) (Quant Curve tab) — one evidence surface for engine, retrieval, and quantization claims.

Hardware identity is declared by benchmark receipts and checked by the consolidated publisher's dedicated-node policy. Receipt authentication proves an operator assertion; this repository does **not** claim an independent hardware witness.

**Division of labor:** this repo owns quantization receipts and their fail-closed verifier. The single Space publisher lives in [szl-holdings/frontier-bench](https://github.com/szl-holdings/frontier-bench), which verifies and combines all three planes before one atomic Space commit. The measurement harness that produces receipted quantization runs lives in [szl-holdings/szl-quant-bench](https://github.com/szl-holdings/szl-quant-bench); the Wave 1 consolidated bakeoff report is [szl-holdings/szl-wave1-report](https://github.com/szl-holdings/szl-wave1-report).

Source admission, Hugging Face publication, product/runtime status, and proof/evaluation status are separate evidence layers. Repository CI alone is not a publication or runtime claim.

## Status

Current source state contains only the BLOCKED genesis receipt: **zero admitted measured quantization rows**. Real benchmark execution and signed raw evidence remain the responsibility of the dedicated-node measurement producer before any measured point can be published.
