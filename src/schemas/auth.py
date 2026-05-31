from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    risk_tolerance: str = "moderate"
    knowledge_level: str = "beginner"

    @field_validator("risk_tolerance")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in {"conservative", "moderate", "aggressive"}:
            raise ValueError("risk_tolerance must be conservative, moderate, or aggressive")
        return v

    @field_validator("knowledge_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in {"beginner", "intermediate", "advanced"}:
            raise ValueError("knowledge_level must be beginner, intermediate, or advanced")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str | None
    risk_tolerance: str
    knowledge_level: str
    is_admin: bool = False

    model_config = {"from_attributes": True}
