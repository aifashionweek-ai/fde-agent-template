"""Create / reuse a Hugging Face Inference Endpoint for an open-weights model (docs/07-huggingface-deploy.md).
Usage: HF_TOKEN=… python deploy/hf_endpoint.py meta-llama/Llama-3.1-8B-Instruct --gpu nvidia-l4
Prints HF_ENDPOINT_URL to export; agent/models.py uses it when set."""
import argparse, os, time
from huggingface_hub import create_inference_endpoint, get_inference_endpoint

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("repo"); ap.add_argument("--name", default="fde-agent-llm")
    ap.add_argument("--vendor", default="aws"); ap.add_argument("--region", default="us-west-2")
    ap.add_argument("--gpu", default="nvidia-l4")   # l4 (24GB) fits 8B fp16/bf16; a10g/a100 for 70B (quantized)
    ap.add_argument("--instance-size", default="x1"); ap.add_argument("--min", type=int, default=0)  # scale-to-zero
    a = ap.parse_args()
    try:
        ep = get_inference_endpoint(a.name); print("reusing", ep.name)
    except Exception:
        ep = create_inference_endpoint(a.name, repository=a.repo, framework="pytorch", task="text-generation",
            accelerator="gpu", vendor=a.vendor, region=a.region, type="protected",
            instance_size=a.instance_size, instance_type=a.gpu, min_replica=a.min, max_replica=1,
            custom_image={"health_route": "/health", "env": {"MAX_INPUT_LENGTH": "8192", "MAX_TOTAL_TOKENS": "12288",
                          "MODEL_ID": "/repository"}, "url": "ghcr.io/huggingface/text-generation-inference:latest"})
    ep.wait(timeout=900); print("HF_ENDPOINT_URL=" + ep.url)

if __name__ == "__main__": main()
