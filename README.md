# Quant Curve

Measured quantization evidence for the SZL stack — quality vs precision, drawn only from real runs.

## What this is

The honest companion to every quantization claim: quality-vs-precision curves and throughput numbers measured on named hardware, on named dates, with named methods. A curve that can't be traced to runs doesn't render.

## Guarantees

- **Measured points only** — every point on a curve is an actual run; no interpolation dressed up as data.
- **Quality and throughput together** — perplexity and tokens/sec reported from the same machine on the same day.
- **Receipts** — every point is hash-chained into the run ledger so history is tamper-evident.
- **Fail-closed display** — unverifiable runs appear as absent.

## Public surface

The consolidated public bench lives at [betterwithage/szl-bench-suite](https://huggingface.co/spaces/betterwithage/szl-bench-suite) (Quant Curve tab) — one evidence surface for engine, retrieval, and quantization claims.

Hardware truth is sourced from the published runtime witness ([szl-holdings/lutar-runtime-witness](https://github.com/szl-holdings/lutar-runtime-witness)), whose verifier recomputes every digest from source and fails closed on drift.

## Status

Foundation (2026-09-03): honest-results contract, curve schema, and verifier in place. Measured points land here from the dedicated GPU node as runs complete.
