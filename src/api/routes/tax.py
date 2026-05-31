from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.deps import get_current_user
from src.models.user import User

router = APIRouter(prefix="/api/tax", tags=["tax"])

TOPICS = [
    {"id": "capital_gains", "label": "Capital Gains Tax", "category": "tax"},
    {"id": "roth_ira", "label": "Roth IRA", "category": "accounts"},
    {"id": "traditional_ira", "label": "Traditional IRA", "category": "accounts"},
    {"id": "401k", "label": "401(k) Plans", "category": "accounts"},
    {"id": "hsa", "label": "Health Savings Account (HSA)", "category": "accounts"},
    {"id": "tax_loss_harvesting", "label": "Tax-Loss Harvesting", "category": "strategy"},
    {"id": "dividend_tax", "label": "Dividend Taxation", "category": "tax"},
    {"id": "wash_sale", "label": "Wash Sale Rule", "category": "rules"},
    {"id": "step_up_basis", "label": "Step-Up in Basis", "category": "rules"},
    {"id": "required_minimum", "label": "Required Minimum Distributions (RMDs)", "category": "rules"},
]


class TaxExplainRequest(BaseModel):
    topic: str
    user_context: str | None = None


class TaxExplainResponse(BaseModel):
    topic: str
    explanation: str
    disclaimer: str


@router.get("/topics")
async def list_topics(user: User = Depends(get_current_user)) -> list[dict]:
    return TOPICS


@router.post("/explain", response_model=TaxExplainResponse)
async def explain_topic(
    body: TaxExplainRequest,
    request: Request,
    user: User = Depends(get_current_user),
) -> TaxExplainResponse:
    from src.core.config import settings
    from src.core.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(temperature=0.2)
    system = (
        "You are a financial education expert. Explain tax concepts clearly and accurately "
        "for beginners. Always be educational, never provide personalized tax advice. "
        "Keep explanations concise (3-5 paragraphs)."
    )
    user_msg = f"Explain: {body.topic}"
    if body.user_context:
        user_msg += f"\nContext: {body.user_context}"

    response = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user_msg)])
    return TaxExplainResponse(
        topic=body.topic,
        explanation=response.content,
        disclaimer=settings.disclaimer_text,
    )
