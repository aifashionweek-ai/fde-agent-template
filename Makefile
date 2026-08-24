.PHONY: setup check evals evals-braintrust gate run demo demo-all deploy preflight hf smoke bakeoff harness audit problem mcp
setup:     ; pip install -r requirements.txt && cp -n .env.example .env || true
demo:      ; bash demo.sh
demo-all:  ; bash scripts/run_all.sh $(ARGS)
check:     ; python update.py --check
evals:     ; python -m evals.runner                 # harness C: invariant gate + quality thresholds (offline)
evals-braintrust: ; python -m evals.run_evals       # legacy row-per-run golden set → Braintrust
gate:      ; python -m evals.gate $(EXP) $(BASE)
run:       ; uvicorn api.main:app --reload --port 8080
deploy:    ; cd deploy && sam build && sam deploy --guided
preflight: ; bash scripts/bedrock_preflight.sh
hf:        ; python deploy/hf_endpoint.py $(REPO) --gpu $(GPU)
smoke:     ; bash scripts/smoke.sh
bakeoff:   ; bash scripts/model_bakeoff.sh $(PROFILES)
harness:   ; EXPERIMENT=$(EXP) python -m evals.harness
audit:     ; python -m evals.audit_report
problem:   ; python -m evals.problem_report
mcp:       ; python -m agent.mcp_server --manifest
