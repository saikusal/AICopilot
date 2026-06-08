import httpx
from .config import Settings
from .models import QuestionType
from .prompts import build_prompt


async def generate_answer(
    question: str,
    question_type: QuestionType,
    mode: str,
    settings: Settings,
) -> str:
    provider = settings.llm_provider.lower().strip()
    prompt = build_prompt(question, question_type, mode)
    if provider == "ollama":
        return await _ollama(prompt, settings)
    if provider == "anthropic":
        return await _anthropic(prompt, settings)
    return await _openai(prompt, settings)


async def _openai(prompt: str, settings: Settings) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    payload = {
        "model": settings.openai_model,
        "input": prompt,
        "max_output_tokens": settings.answer_max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            json=payload,
            headers=headers,
        )
        if response.is_error:
            raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text}")
        data = response.json()

    text = data.get("output_text")
    if text:
        return text.strip()

    parts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    return "\n".join(part for part in parts if part).strip()


async def _anthropic(prompt: str, settings: Settings) -> str:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": settings.answer_max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )
        if response.is_error:
            raise RuntimeError(f"Anthropic API error {response.status_code}: {response.text}")
        data = response.json()

    return "\n".join(
        item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"
    ).strip()


async def _ollama(prompt: str, settings: Settings) -> str:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.25,
            "num_predict": settings.answer_max_tokens,
        },
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json=payload,
        )
        if response.is_error:
            raise RuntimeError(f"Ollama API error {response.status_code}: {response.text}")
        data = response.json()
    return data.get("response", "").strip()
