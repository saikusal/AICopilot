#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

MODEL="${OLLAMA_MODEL:-qwen2.5:7b-instruct}"

echo "Installing base packages..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl git gnupg lsb-release

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "NVIDIA driver not found. Installing nvidia-driver-550-server..."
  sudo apt-get install -y linux-headers-"$(uname -r)" ubuntu-drivers-common
  sudo apt-get install -y nvidia-driver-550-server || sudo ubuntu-drivers install --gpgpu
  echo
  echo "NVIDIA driver was installed. Reboot the instance, SSH back in, then rerun:"
  echo "  bash scripts/setup_gpu_server.sh"
  exit 0
fi

echo "Installing NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "Verifying GPU access from Docker..."
sudo docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

if [ ! -f .env ]; then
  cp .env.example .env
fi

python3 - <<'PY'
from pathlib import Path

path = Path(".env")
lines = path.read_text().splitlines()
updates = {
    "STT_PROVIDER": "local_whisper",
    "WHISPER_MODEL": "small.en",
    "WHISPER_DEVICE": "cuda",
    "WHISPER_COMPUTE_TYPE": "float16",
    "LLM_PROVIDER": "ollama",
    "OLLAMA_BASE_URL": "http://ollama:11434",
    "OLLAMA_MODEL": "qwen2.5:7b-instruct",
    "RAG_ENABLED": "true",
    "QDRANT_URL": "http://qdrant:6333",
    "QDRANT_COLLECTION": "interview_knowledge",
    "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
    "RAG_TOP_K": "4",
}
seen = set()
new_lines = []
for line in lines:
    if "=" not in line or line.strip().startswith("#"):
        new_lines.append(line)
        continue
    key = line.split("=", 1)[0].strip()
    if key in updates:
        new_lines.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        new_lines.append(line)
for key, value in updates.items():
    if key not in seen:
        new_lines.append(f"{key}={value}")
path.write_text("\n".join(new_lines) + "\n")
PY

echo "Building and starting app, Faster Whisper backend, and Ollama..."
sudo docker compose up -d --build

echo "Ensuring Ollama model is present: $MODEL"
sudo docker compose exec ollama ollama pull "$MODEL"

echo "Testing services..."
curl -fsS http://localhost/health
echo
sudo docker compose ps

cat <<'EOF'

Setup complete.

Open the app at:
  http://<EC2_PUBLIC_IP>

For phone microphone access, configure HTTPS with a domain before real phone testing.
EOF
