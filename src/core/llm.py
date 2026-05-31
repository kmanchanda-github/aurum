from langchain_core.language_models.chat_models import BaseChatModel

from src.core.config import settings


def get_llm(temperature: float | None = None, streaming: bool = False) -> BaseChatModel:
    temp = temperature if temperature is not None else settings.llm_temperature
    provider = settings.llm_provider.lower()
    model = settings.llm_model

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        key = settings.anthropic_api_key
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return ChatAnthropic(
            model=model,
            api_key=key.get_secret_value(),
            temperature=temp,
            max_tokens=settings.llm_max_tokens,
            streaming=streaming,
        )

    if provider == "openai":
        key = settings.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=key.get_secret_value(),
            temperature=temp,
            max_tokens=settings.llm_max_tokens,
            streaming=streaming,
        )

    if provider == "google":
        key = settings.google_api_key
        if not key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=key.get_secret_value(),
            temperature=temp,
            max_output_tokens=settings.llm_max_tokens,
            streaming=streaming,
        )

    if provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=model,
            region_name=settings.aws_region,
            model_kwargs={"temperature": temp, "max_tokens": settings.llm_max_tokens},
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Choose from: anthropic, openai, google, bedrock"
    )
