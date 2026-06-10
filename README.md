# AI Interview Copilot

Mobile-first web MVP for a phone-based interview copilot.

## What Works In This MVP

- Phone microphone capture from the browser
- Hold-to-listen capture: hold the button while the interviewer speaks, release to send the clip
- Deepgram transcription
- Question detection and classification
- OpenAI or Anthropic answer generation
- Auto-pause after an answer appears, so your spoken response is not captured
- Resume-driven skill profile: the coding language is chosen from your resume, not a fixed default
- Manual text test box
- Docker Compose deployment for a basic EC2 instance
- Local no-API mode with Faster Whisper and Ollama/Qwen on a GPU EC2 instance
- Local RAG with Qdrant and sentence-transformers for resume/project context

## Local Run

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

For phone microphone testing, use HTTPS. On EC2, attach a domain and use Let's Encrypt.

## EC2 Deployment

Use Ubuntu 22.04 or 24.04, open ports `22`, `80`, and `443`.

```bash
git clone <your-repo-url>
cd interview-copilot
cp .env.example .env
nano .env
docker compose up -d --build
```

The app will be available on:

```text
http://EC2_PUBLIC_IP
```

For phone mic access, configure HTTPS:

```bash
sudo certbot --nginx -d copilot.example.com
```

Then update `nginx/default.conf` using `nginx/https.conf.example`, replacing `copilot.example.com` with your domain, and restart:

```bash
docker compose restart nginx
```

## Environment

```env
DEEPGRAM_API_KEY=...

LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.2

ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-6
```

Switch providers by changing `LLM_PROVIDER`.

## No API Key Mode

Use this on the `g6.xlarge` GPU instance:

```env
STT_PROVIDER=local_whisper
WHISPER_MODEL=small.en
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
```

Then:

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

RAG runs through Qdrant:

```env
RAG_ENABLED=true
QDRANT_URL=http://qdrant:6333
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RAG_TOP_K=4
```

Paste resume/project context in the app's `Knowledge` section, or ingest from the server:

```bash
curl -X POST http://localhost/api/knowledge/text \
  -H 'Content-Type: application/json' \
  -d '{"title":"Resume","source_type":"resume","text":"Paste resume text here"}'
```

## Resume-Driven Language

When you save a resume in the `Knowledge` panel (or POST with `source_type` set to
`resume` or `profile`), the backend runs one LLM pass to extract a skill profile:

```json
{
  "primary_language": "Python",
  "secondary_languages": ["SQL", "Bash"],
  "frameworks": ["Django", "FastAPI"],
  "domains": ["AIOps", "AWS"],
  "seniority": "senior"
}
```

The profile is stored in a Qdrant `interview_profile` collection and injected into every
coding prompt. With the language selector set to `Auto`, a question like "write code to
reverse a string" is answered in your strongest language, in a style matching your
seniority and frameworks. Picking a specific language in the selector overrides the profile,
and a question that names a language always wins.

Inspect or correct the detected profile:

```bash
curl http://localhost/api/profile

curl -X PUT http://localhost/api/profile \
  -H 'Content-Type: application/json' \
  -d '{"primary_language":"Python","secondary_languages":["Go"],"frameworks":["FastAPI"],"domains":["AIOps"],"seniority":"senior"}'
```

Profile extraction is best-effort: if it fails, the resume is still ingested for RAG and the
selector default is used.

Full GPU EC2 instructions:

```text
deploy/gpu-ec2-setup.md
```

Fast path on a fresh `g6.xlarge`:

```bash
git clone https://github.com/saikusal/AICopilot.git
cd AICopilot
bash scripts/setup_gpu_server.sh
```

If the script installs the NVIDIA driver, reboot once and rerun the same script.

## HTTPS With sslip.io

Phone microphone access needs HTTPS. On EC2, after the app is running and ports `80`/`443` are open:

```bash
bash scripts/setup_sslip_https.sh
```

The script detects your public IP and creates a free `sslip.io` hostname, for example:

```text
https://13-201-10-25.sslip.io
```

## Usage

1. Open the site on your phone.
2. Paste your resume into the `Knowledge` panel and save, so the profile is set.
3. Hold `Listen` while the interviewer asks the question.
4. Release to send the clip; the answer appears and the mic auto-pauses.
5. Speak your answer verbally.
6. Hold `Listen` again for the next question.
