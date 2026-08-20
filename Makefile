.PHONY: setup check evals gate run deploy preflight hf smoke
setup:     ; pip install -r requirements.txt && cp -n .env.example .env || true
check:     ; python update.py --check
evals:     ; python -m evals.run_evals
gate:      ; python -m evals.gate $(EXP) $(BASE)
run:       ; uvicorn api.main:app --reload --port 8080
deploy:    ; cd deploy && sam build && sam deploy --guided
preflight: ; bash scripts/bedrock_preflight.sh
hf:        ; python deploy/hf_endpoint.py $(REPO) --gpu $(GPU)
smoke:     ; bash scripts/smoke.sh
bakeoff:   ; bash scripts/model_bakeoff.sh $(PROFILES)
harness:   ; EXPERIMENT=$(EXP) python -m evals.harness
audit:     ; python -m evals.audit_report
