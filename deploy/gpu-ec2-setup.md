# GPU EC2 Setup

Target instance:

```text
g6.xlarge
Ubuntu 22.04 or 24.04
100-150 GB gp3 disk
Ports: 22, 80, 443
```

## 1. Install Docker And NVIDIA Runtime

Fast path:

```bash
git clone https://github.com/saikusal/AICopilot.git
cd AICopilot
bash scripts/setup_gpu_server.sh
```

If the script installs the NVIDIA driver, reboot once and rerun it.

Manual path:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

Log out and SSH back in, then install NVIDIA container toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify GPU:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 2. Configure App

Edit `.env`:

```env
STT_PROVIDER=local_whisper
WHISPER_MODEL=small.en
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
```

When running backend outside Docker, use:

```env
OLLAMA_BASE_URL=http://localhost:11434
```

## 3. Start Services

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

Test Qwen:

```bash
docker compose exec ollama ollama run qwen2.5:7b-instruct "Give one sentence about AWS VPC."
```

Test backend:

```bash
curl http://localhost/health
curl -X POST http://localhost/api/answer \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"test","text":"What is AWS VPC?","force":true}'
```

Warm RAG embeddings:

```bash
curl -X POST http://localhost/api/knowledge/text \
  -H 'Content-Type: application/json' \
  -d '{"title":"Warmup","source_type":"profile","text":"AIOps platform, AWS, Python, automation, incident response, observability."}'
```

## 4. HTTPS

Phone microphone needs HTTPS. For the free `sslip.io` path:

```bash
bash scripts/setup_sslip_https.sh
```

The script detects the EC2 public IP, requests a Let's Encrypt certificate, switches Nginx to HTTPS, and prints the phone URL.

## Latency Notes

Expected MVP latency on `g6.xlarge`:

```text
5 second audio chunk
0.5-2 sec Faster Whisper
2-8 sec Qwen answer
8-15 sec total typical MVP latency
```

Lower latency needs streaming transcription and shorter chunks.
