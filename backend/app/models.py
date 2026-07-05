"""Pydantic request/response schemas for the public API.

The client ``ChatRequest`` deliberately exposes only conversation messages.
Any extra keys a browser might send (model, max_tokens, tools, temperature, ...)
are ignored by pydantic and never reach the provider payload.
"""
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login_code: str


class LoginResponse(BaseModel):
    token: str
    participant_id: str
    display_name: str


class ClientMessage(BaseModel):
    # Role is accepted as a free string; build_payload keeps only user/assistant
    # and drops any client-supplied system/tool messages (defense in depth).
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ClientMessage] = Field(default_factory=list)


class Usage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: str


class ChatLimits(BaseModel):
    max_output_tokens: int


class ChatResponse(BaseModel):
    message: AssistantMessage
    usage: Usage
    limits: ChatLimits


class ChangeCodeRequest(BaseModel):
    new_code: str


class SavedChat(BaseModel):
    id: str
    messages: list[ClientMessage] = Field(default_factory=list)
    updated_at: int = 0


class SaveChatsRequest(BaseModel):
    chats: list[SavedChat] = Field(default_factory=list)


class MeResponse(BaseModel):
    participant_id: str
    display_name: str
    team_id: Optional[str] = None
    remaining_requests: int
