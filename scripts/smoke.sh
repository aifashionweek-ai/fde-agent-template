#!/usr/bin/env bash
# 60-second proof the whole loop works. Run after `cp .env.example .env` and filling keys.
set -e
python update.py --check
uvicorn api.main:app --port 8080 &  PID=$!; sleep 3
curl -s localhost:8080/health
curl -s -X POST localhost:8080/run -H 'content-type: application/json' -d '{"task":"What is 17 * 23?"}'
kill $PID
python -m evals.run_evals
