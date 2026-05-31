from datetime import datetime

from pydantic import BaseModel


class AgentMetric(BaseModel):
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int

    model_config = {"from_attributes": True}


class ChatTraceOut(BaseModel):
    intent: str | None
    routing_reason: str | None
    supervisor_confidence: float | None
    selected_agents: list[str]
    rag_categories: list[str]
    retrieved_docs: list[dict]
    agent_metrics: list[AgentMetric]
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int

    model_config = {"from_attributes": True}


class AdminMessageTrace(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: datetime
    trace: ChatTraceOut | None = None

    model_config = {"from_attributes": True}


class AdminConversationTrace(BaseModel):
    conversation_id: str
    title: str
    user_email: str
    messages: list[AdminMessageTrace]


class AdminConversationSummary(BaseModel):
    id: str
    title: str
    user_id: str
    user_email: str
    message_count: int
    agents_used: list[str]
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    created_at: datetime
    updated_at: datetime


class AdminConversationPage(BaseModel):
    items: list[AdminConversationSummary]
    total: int
    page: int
    per_page: int


class AdminUserSummary(BaseModel):
    id: str
    email: str
    full_name: str | None
    created_at: datetime
    conversation_count: int
    message_count: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float


class AdminUserPage(BaseModel):
    items: list[AdminUserSummary]
    total: int
    page: int
    per_page: int


class AdminStats(BaseModel):
    total_users: int
    total_conversations: int
    total_messages: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    langsmith_enabled: bool
    langsmith_project: str | None
    langsmith_url: str | None
