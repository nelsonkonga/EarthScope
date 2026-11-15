from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.assistant import create_session, get_session, post_message

router = APIRouter()


class MessageBody(BaseModel):
    text: str
    clientContext: dict | None = None


@router.post("/assistant/sessions")
def open_session():
    return create_session()


@router.get("/assistant/sessions/{session_id}")
def read_session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Conversation introuvable."})
    return session


@router.post("/assistant/sessions/{session_id}/messages")
def write_message(session_id: str, body: MessageBody):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Le message est vide."})
    message = post_message(session_id, body.text.strip(), body.clientContext or {})
    if message is None:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND", "message": "Conversation introuvable."})
    return {"message": message}
