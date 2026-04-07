# QuestionBridge — Agent Usage Guide

This service lets you ask the owner a question and block until they reply.
Use it for authorization requests, confirmations, or any time you need human input.

## Prerequisites

The service must be running. Check first:

```bash
curl -sf http://localhost:8000/health || echo "NOT RUNNING — start with: python main.py"
```

## Core pattern: ask → wait → act

```python
import httpx

client = httpx.Client(base_url="http://localhost:8000", timeout=None)

# 1. Send the question (returns immediately)
resp = client.post("/api/ask", json={
    "question": "About to delete 47 files in /tmp/build. Proceed?",
    "context": "Command: rm -rf /tmp/build\nAffected: 47 files, 1.2 GB"  # optional
})
resp.raise_for_status()
qid = resp.json()["id"]

# 2. Block until answered (default timeout: 300 s)
resp = client.get(f"/api/questions/{qid}/wait", params={"timeout": 300})
result = resp.json()

if result["status"] == "answered":
    answer = result["answer"]          # e.g. "yes", "no", or free text
    if answer.lower() in ("yes", "y"):
        # proceed
    else:
        # abort
elif result["status"] == "cancelled":
    # owner dismissed the request — abort
else:
    # status == "pending": timed out without a reply — decide how to handle
```

## Async variant (preferred inside async tasks)

```python
import httpx
import asyncio

async def ask_owner(question: str, context: str | None = None, timeout: int = 300) -> str | None:
    """Returns the answer string, or None if cancelled/timed-out."""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=None) as client:
        resp = await client.post("/api/ask", json={"question": question, "context": context})
        resp.raise_for_status()
        qid = resp.json()["id"]

        resp = await client.get(f"/api/questions/{qid}/wait", params={"timeout": timeout})
        result = resp.json()

    if result["status"] == "answered":
        return result["answer"]
    return None  # cancelled or timed out
```

## API reference

### POST /api/ask
Create a question and send it to the owner via Telegram.

Request body:
```json
{ "question": "string (required)", "context": "string (optional)" }
```
Response `201`:
```json
{ "id": "a3f9c12b", "status": "pending", "answer": null, ... }
```

### GET /api/questions/{id}/wait?timeout=300
Long-poll until answered, cancelled, or timeout (seconds). Safe to call with large timeouts.

Response — same shape as above, check `status`:
- `"answered"` → read `answer`
- `"cancelled"` → owner dismissed it
- `"pending"` → timed out

### GET /api/questions/{id}
Non-blocking snapshot of a question's current state.

### GET /api/questions/{id}/stream
SSE endpoint — fires one `data:` event immediately (current state) and another when resolved.

### GET /api/questions?status=pending
List all questions, optionally filtered by status (`pending` / `answered` / `cancelled`).

### POST /api/questions/{id}/answer
```json
{ "answer": "string" }
```
Programmatically answer a question (e.g. in tests).

### POST /api/questions/{id}/cancel
Mark a question cancelled without an answer.

### GET /health
```json
{ "status": "ok", "pending_questions": 2 }
```

## Writing good questions

- Be specific — include what will happen, not just what you want to do.
- Use `context` for command output, file lists, diffs, or other supporting detail.
- Keep `question` to one clear sentence ending with `?`

```python
# Good
await ask_owner(
    question="Push force to origin/main, overwriting 3 remote commits?",
    context=f"Local HEAD: {local_sha}\nRemote HEAD: {remote_sha}\nCommits to overwrite:\n{log}"
)

# Too vague
await ask_owner(question="Ok to continue?")
```

## Notes

- Questions are stored in memory only — they are lost if the service restarts.
- The owner can answer from Telegram (reply to the message or tap Yes/No) or from the web dashboard at `http://localhost:8000`.
- Multiple agents can have questions in flight simultaneously — each gets its own ID.
- `asyncio.shield` is used internally so long-poll connections don't block event resolution if the HTTP request drops.
