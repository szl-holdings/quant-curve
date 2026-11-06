# Sovereign deploy — quant-curve API

Runs on owned hardware (the RTX 4000 Ada bench node). No third-party hosting tier required.

## Prerequisites

- Docker with the compose plugin on the bench node
- Receipts present under `receipts/` (genesis BLOCKED receipt ships with the repo)

## Steps

1. Export verified results (fail-closed; aborts on any bad receipt):

   python tools/sync_results.py receipts site/results.json

2. Build and run:

   docker compose -f deploy/docker-compose.yml up -d --build

3. Verify:

   curl http://127.0.0.1:7863/healthz
   curl http://127.0.0.1:7863/api/results

   Expect state EMPTY_HONEST until the first MEASURED receipt lands. That is correct behavior, not an error.
   State UNAVAILABLE means the results file is missing, unreadable or malformed: re-run step 1 and read the API log.

## Updating data

After new receipts arrive: re-run step 1, then `docker compose -f deploy/docker-compose.yml restart`. The site mount is read-only; the API never mutates results.

## Honesty contract

- /api/results serves only rows from the step 1 export: MEASURED receipts from a hash-chain-verified (unsigned) chain. The API does not re-verify receipts; it serves the read-only export as-is.
- A valid export with no quant rows returns EMPTY_HONEST; a missing, unreadable or malformed results file returns UNAVAILABLE. Both return count 0 — never an error page, never fabricated numbers.
- The image installs the hash-locked `requirements.txt` (`pip install --require-hashes`); edit ranges in `requirements.in` and recompile with the command in the lock's header.
