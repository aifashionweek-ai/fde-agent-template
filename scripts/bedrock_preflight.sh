#!/usr/bin/env bash
# Bedrock preflight (D-015): burn the enablement gates BEFORE the clock starts. Exit 0 = Bedrock is a live option.
# Gates it proves: credentials+account, region, model access granted, inference-profile id, IAM invoke perms, Guardrail (optional).
set -u
REGION="${AWS_REGION:-us-west-2}"
MODEL="${BEDROCK_MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"
echo "== 1/5 identity";  aws sts get-caller-identity --query 'Account' --output text || { echo "no AWS creds"; exit 1; }
echo "== 2/5 model access in $REGION (ACTIVE = enabled; missing = enable in console → Model access)"
aws bedrock list-foundation-models --region "$REGION" --query "modelSummaries[?contains(modelId,'claude')].[modelId,modelLifecycle.status]" --output table | head -20
echo "== 3/5 inference profiles (newer Claude REQUIRES a us.* / eu.* profile id, not the bare model id)"
aws bedrock list-inference-profiles --region "$REGION" --query "inferenceProfileSummaries[?contains(inferenceProfileId,'claude')].inferenceProfileId" --output text | tr '\t' '\n' | head -10
echo "== 4/5 invoke test with $MODEL"
aws bedrock-runtime converse --region "$REGION" --model-id "$MODEL" \
  --messages '[{"role":"user","content":[{"text":"Reply with the single word OK."}]}]' \
  --inference-config '{"maxTokens":5}' --query 'output.message.content[0].text' --output text \
  && echo "   invoke OK" || { echo "   invoke FAILED — if AccessDenied: IAM bedrock:InvokeModel; if ValidationException: use a us.* profile id; if ResourceNotFound: enable model access"; exit 1; }
if [ -n "${BEDROCK_GUARDRAIL_ID:-}" ]; then
  echo "== 5/5 guardrail $BEDROCK_GUARDRAIL_ID"
  aws bedrock get-guardrail --region "$REGION" --guardrail-identifier "$BEDROCK_GUARDRAIL_ID" --query 'status' --output text || exit 1
else echo "== 5/5 no BEDROCK_GUARDRAIL_ID set (optional; see docs/02-bedrock.md §4)"; fi
echo "PREFLIGHT PASS → export LLM_PROVIDER=bedrock MODEL_PROFILE=claude-sonnet-bedrock BEDROCK_MODEL_ID=$MODEL"
