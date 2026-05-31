from datetime import datetime

from pydantic import BaseModel


class Citation(BaseModel):
    source_title: str
    source_url: str | None = None
    snippet: str = ""


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    agents_used: list[str] = []
    citations: list[Citation] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    title: str = "New Conversation"


class ChatMessageIn(BaseModel):
    content: str
    conversation_id: str | None = None
