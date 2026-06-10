import json
import re

import httpx

from .config import Settings
from .llm import generate_text
from .models import SkillProfile


# Fixed point id so the profile is a single, overwritable record in Qdrant.
_PROFILE_POINT_ID = "00000000-0000-0000-0000-0000000000a1"


EXTRACT_PROMPT = """You analyze a candidate's resume and extract their technical profile.
Return ONLY a JSON object, no prose, no markdown fences, with exactly these keys:
- primary_language: the single programming language the candidate is strongest in (string)
- secondary_languages: other languages they know (array of strings)
- frameworks: notable frameworks, libraries, and tools (array of strings)
- domains: areas of expertise such as AIOps, AWS, data engineering (array of strings)
- seniority: one of "junior", "mid", "senior", "staff"

Infer primary_language from emphasis, recency, and depth, not just first mention.
If the resume is empty or unclear, default primary_language to "Python".

Resume:
{resume}
"""


def _parse_profile(raw: str) -> SkillProfile:
    text = raw.strip()
    # Strip ```json ... ``` fences if the model added them.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Otherwise grab the first {...} block.
    if not text.startswith("{"):
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    data = json.loads(text)
    return SkillProfile(**data)


async def extract_profile(resume_text: str, settings: Settings) -> SkillProfile:
    prompt = EXTRACT_PROMPT.format(resume=resume_text.strip()[:8000])
    raw = await generate_text(prompt, settings)
    return _parse_profile(raw)


async def save_profile(profile: SkillProfile, settings: Settings) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        check = await client.get(
            f"{settings.qdrant_url}/collections/{settings.profile_collection}"
        )
        if check.status_code == 404:
            create = await client.put(
                f"{settings.qdrant_url}/collections/{settings.profile_collection}",
                json={"vectors": {"size": 1, "distance": "Cosine"}},
            )
            if create.is_error:
                raise RuntimeError(f"Qdrant profile collection create failed: {create.text}")
        elif check.is_error:
            raise RuntimeError(f"Qdrant profile collection check failed: {check.text}")

        upsert = await client.put(
            f"{settings.qdrant_url}/collections/{settings.profile_collection}/points",
            json={
                "points": [
                    {
                        "id": _PROFILE_POINT_ID,
                        "vector": [0.0],
                        "payload": profile.model_dump(),
                    }
                ]
            },
        )
        if upsert.is_error:
            raise RuntimeError(f"Qdrant profile upsert failed: {upsert.text}")


async def load_profile(settings: Settings) -> SkillProfile | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.qdrant_url}/collections/{settings.profile_collection}"
                f"/points/{_PROFILE_POINT_ID}"
            )
            if response.status_code != 200:
                return None
            payload = response.json().get("result", {}).get("payload")
    except Exception:
        return None
    if not payload:
        return None
    try:
        return SkillProfile(**payload)
    except Exception:
        return None
