import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict
from dataclasses import dataclass
import uuid


@dataclass
class Question:
    id: str
    question: str
    context: Optional[str]
    status: str  # pending | answered | cancelled
    answer: Optional[str]
    created_at: datetime
    answered_at: Optional[datetime]
    telegram_message_id: Optional[int]
    event: asyncio.Event  # set when status changes from pending


# question_id -> Question
questions: Dict[str, Question] = {}

# telegram message_id -> question_id  (for reply tracking)
message_to_question: Dict[int, str] = {}

# Away mode: when True, Claude should use the bridge instead of chat
away: bool = False


def create_question(question: str, context: Optional[str] = None) -> Question:
    q = Question(
        id=str(uuid.uuid4())[:8],
        question=question,
        context=context,
        status="pending",
        answer=None,
        created_at=datetime.now(timezone.utc),
        answered_at=None,
        telegram_message_id=None,
        event=asyncio.Event(),
    )
    questions[q.id] = q
    return q


def answer_question(question_id: str, answer: str) -> Optional[Question]:
    q = questions.get(question_id)
    if q and q.status == "pending":
        q.answer = answer
        q.status = "answered"
        q.answered_at = datetime.now(timezone.utc)
        q.event.set()
        return q
    return None


def cancel_question(question_id: str) -> Optional[Question]:
    q = questions.get(question_id)
    if q and q.status == "pending":
        q.status = "cancelled"
        q.answered_at = datetime.now(timezone.utc)
        q.event.set()
        return q
    return None
