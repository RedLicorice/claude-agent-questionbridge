import asyncio
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import store
from .bot import send_question

app = FastAPI(title="QuestionBridge API", version="1.0.0")


# ── Serialization ─────────────────────────────────────────────────────────────

def _serialize(q: store.Question) -> dict:
    return {
        "id": q.id,
        "question": q.question,
        "context": q.context,
        "status": q.status,
        "answer": q.answer,
        "created_at": q.created_at.isoformat(),
        "answered_at": q.answered_at.isoformat() if q.answered_at else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    pending = sum(1 for q in store.questions.values() if q.status == "pending")
    return {"status": "ok", "pending_questions": pending}


@app.get("/api/status")
async def get_status():
    return {"away": store.away}


@app.post("/api/status")
async def set_status(body: dict):
    if "away" in body:
        store.away = bool(body["away"])
    return {"away": store.away}


class AskRequest(BaseModel):
    question: str
    context: Optional[str] = None


@app.post("/api/ask", status_code=201)
async def ask(req: AskRequest):
    """
    Send a question to the owner via Telegram.
    Returns immediately with the question ID and status='pending'.
    Poll /api/questions/{id}/wait to block until answered.
    """
    q = store.create_question(req.question, req.context)
    await send_question(q)
    return _serialize(q)


@app.get("/api/questions")
async def list_questions(status: Optional[str] = None):
    qs = list(store.questions.values())
    if status:
        qs = [q for q in qs if q.status == status]
    return [_serialize(q) for q in qs]


@app.get("/api/questions/{question_id}")
async def get_question(question_id: str):
    q = store.questions.get(question_id)
    if not q:
        raise HTTPException(404, f"Question '{question_id}' not found")
    return _serialize(q)


@app.get("/api/questions/{question_id}/wait")
async def wait_for_answer(question_id: str, timeout: int = 300):
    """
    Long-poll: blocks until the question is answered/cancelled or timeout expires.
    Check response.status to determine if it was answered in time.
    """
    q = store.questions.get(question_id)
    if not q:
        raise HTTPException(404, f"Question '{question_id}' not found")
    if q.status != "pending":
        return _serialize(q)
    try:
        await asyncio.wait_for(asyncio.shield(q.event.wait()), timeout=float(timeout))
    except asyncio.TimeoutError:
        pass
    return _serialize(q)


@app.get("/api/questions/{question_id}/stream")
async def stream_question(question_id: str):
    """SSE stream — fires once when the question is answered/cancelled."""
    q = store.questions.get(question_id)
    if not q:
        raise HTTPException(404, f"Question '{question_id}' not found")

    async def _generate():
        yield f"data: {json.dumps(_serialize(q))}\n\n"
        if q.status != "pending":
            return
        await q.event.wait()
        yield f"data: {json.dumps(_serialize(q))}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


class AnswerRequest(BaseModel):
    answer: str


@app.post("/api/questions/{question_id}/answer")
async def answer_question_endpoint(question_id: str, body: AnswerRequest):
    """Manually answer a question (used by the dashboard)."""
    q = store.answer_question(question_id, body.answer)
    if not q:
        raise HTTPException(404, "Question not found or already answered")
    return _serialize(q)


@app.post("/api/questions/{question_id}/cancel")
async def cancel_question_endpoint(question_id: str):
    q = store.cancel_question(question_id)
    if not q:
        raise HTTPException(404, "Question not found or already resolved")
    return _serialize(q)


# ── MCP Streamable HTTP transport ─────────────────────────────────────────────
# Claude Code connects here directly — no subprocess, no HTTP round-trip.
# Register in ~/.claude/mcp.json:  { "mcpServers": { "questionbridge": { "url": "http://localhost:8000/mcp" } } }

_MCP_TOOL = {
    "name": "ask_owner",
    "description": (
        "Send a question to the owner via Telegram and wait for their reply. "
        "Use this instead of asking in the chat for any authorization, confirmation, "
        "or human decision. Returns the owner's answer, 'CANCELLED', or 'TIMEOUT'."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "One clear question ending with '?'",
            },
            "context": {
                "type": "string",
                "description": "Optional supporting detail: command output, file lists, diffs…",
            },
        },
        "required": ["question"],
    },
}


def _mcp_ok(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _mcp_err(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


@app.post("/mcp")
async def mcp_handler(request: Request):
    body = await request.json()
    method: str = body.get("method", "")
    msg_id = body.get("id")  # None for notifications (fire-and-forget)

    if method.startswith("notifications/"):
        return Response(status_code=204)

    if method == "initialize":
        return JSONResponse(_mcp_ok(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "questionbridge", "version": "1.0.0"},
        }))

    if method == "tools/list":
        return JSONResponse(_mcp_ok(msg_id, {"tools": [_MCP_TOOL]}))

    if method == "tools/call":
        params = body.get("params", {})
        if params.get("name") != "ask_owner":
            return JSONResponse(_mcp_err(msg_id, -32601, "Unknown tool"), status_code=404)

        args = params.get("arguments", {})
        question_text = (args.get("question") or "").strip()
        if not question_text:
            return JSONResponse(_mcp_err(msg_id, -32602, "'question' is required"), status_code=400)

        async def _stream():
            q = store.create_question(question_text, args.get("context"))
            await send_question(q)
            try:
                await asyncio.wait_for(asyncio.shield(q.event.wait()), timeout=300.0)
            except asyncio.TimeoutError:
                pass

            if q.status == "answered":
                text, is_error = q.answer, False
            elif q.status == "cancelled":
                text, is_error = "CANCELLED", True
            else:
                text, is_error = "TIMEOUT: no reply within 5 minutes", True

            yield f"data: {json.dumps(_mcp_ok(msg_id, {'content': [{'type': 'text', 'text': text}], 'isError': is_error}))}\n\n"

        return StreamingResponse(_stream(), media_type="text/event-stream")

    return JSONResponse(_mcp_err(msg_id, -32601, f"Method not found: {method}"), status_code=404)
