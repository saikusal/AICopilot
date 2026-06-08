from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .llm import generate_answer
from .models import (
    AnswerRequest,
    AnswerResponse,
    KnowledgeIngestResponse,
    KnowledgeListResponse,
    KnowledgeTextRequest,
    SessionState,
)
from .question_router import (
    classify_question,
    extract_recent_question,
    is_complete_enough,
    is_question_like,
    normalize,
)
from .rag import ingest_text, list_knowledge, retrieve_context
from .transcribe import transcribe_audio


settings = get_settings()
app = FastAPI(title=settings.app_name)
sessions: dict[str, SessionState] = {}

origins = ["*"] if settings.cors_origins == "*" else [
    origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session(session_id: str) -> SessionState:
    if session_id not in sessions:
        sessions[session_id] = SessionState()
    return sessions[session_id]


async def process_text(session_id: str, text: str, force: bool, mode: str) -> AnswerResponse:
    state = get_session(session_id)
    segment = normalize(text)
    if segment:
        state.transcript = normalize(f"{state.transcript} {segment}")

    question = normalize(segment) if force else extract_recent_question(state.transcript)
    if not question:
        return AnswerResponse(
            session_id=session_id,
            transcript=state.transcript,
            message="Listening. No complete question detected yet.",
        )

    if not force and (not is_question_like(question) or not is_complete_enough(question)):
        return AnswerResponse(
            session_id=session_id,
            transcript=state.transcript,
            question=question,
            message="Possible question detected, waiting for completion.",
        )

    question_type = classify_question(question)
    try:
        context = await retrieve_context(question, settings)
        answer = await generate_answer(question, question_type, mode, settings, context)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    state.last_question = question
    state.last_answer = answer
    return AnswerResponse(
        session_id=session_id,
        transcript=state.transcript,
        question=question,
        question_type=question_type,
        answer=answer,
        should_pause=True,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/audio-chunk", response_model=AnswerResponse)
async def audio_chunk(
    session_id: str = Form(default="default"),
    mode: str = Form(default="normal"),
    force: bool = Form(default=False),
    audio: UploadFile = File(...),
) -> AnswerResponse:
    audio_bytes = await audio.read()
    try:
        transcript = await transcribe_audio(audio_bytes, audio.content_type or "audio/webm", settings)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await process_text(session_id, transcript, force, mode)


@app.post("/api/answer", response_model=AnswerResponse)
async def answer(request: AnswerRequest) -> AnswerResponse:
    return await process_text(request.session_id, request.text, request.force, request.mode)


@app.post("/api/knowledge/text", response_model=KnowledgeIngestResponse)
async def add_knowledge(request: KnowledgeTextRequest) -> KnowledgeIngestResponse:
    try:
        chunks = await ingest_text(request.title, request.text, request.source_type, settings)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return KnowledgeIngestResponse(status="ok", chunks=chunks)


@app.get("/api/knowledge", response_model=KnowledgeListResponse)
async def knowledge_items() -> KnowledgeListResponse:
    items = await list_knowledge(settings)
    return KnowledgeListResponse(items=items)


@app.post("/api/session/{session_id}/reset")
async def reset_session(session_id: str) -> dict[str, str]:
    sessions.pop(session_id, None)
    return {"status": "reset"}
