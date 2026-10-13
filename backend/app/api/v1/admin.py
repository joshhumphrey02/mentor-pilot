import asyncio
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.ai.providers.base import ProviderError
from app.ai.registry import ProviderStatus
from app.ai.service import AIService, UsageContext
from app.ai.types import ChatMessage
from app.api.deps import AdminUser
from app.core.errors import error_responses
from app.schemas.admin import ProviderStatusOut, TestChatRequest, TestChatResponse

router = APIRouter(prefix="/admin", tags=["admin"], responses=error_responses(401, 403))


def get_ai(request: Request) -> AIService:
    service: AIService = request.app.state.ai
    return service


async def _check(ai: AIService, status: ProviderStatus) -> ProviderStatusOut:
    out = ProviderStatusOut(
        name=status.name,
        active=status.active,
        configured=status.configured,
        model=status.model,
        fast_model=status.fast_model,
    )
    if not status.configured:
        out.healthy, out.detail = False, "No API key set."
        return out
    try:
        # The model id is only checked for the active provider: AI_MODEL
        # belongs to whichever vendor AI_PROVIDER names.
        out.detail = await ai.registry.get(status.name).check(status.model)
        out.healthy = True
    except ProviderError as exc:
        out.healthy, out.detail = False, f"{exc} ({exc.code})"
    return out


@router.get("/ai/providers", response_model=list[ProviderStatusOut])
async def ai_providers(
    request: Request,
    _admin: AdminUser,
    check: Annotated[bool, Query(description="Also call each provider to verify it.")] = False,
) -> list[ProviderStatusOut]:
    """Which AI providers have keys, which one is active, and (optionally) whether each works."""
    ai = get_ai(request)
    statuses = ai.registry.statuses()
    if check:
        return list(await asyncio.gather(*(_check(ai, status) for status in statuses)))
    return [
        ProviderStatusOut(
            name=s.name,
            active=s.active,
            configured=s.configured,
            model=s.model,
            fast_model=s.fast_model,
        )
        for s in statuses
    ]


@router.post("/ai/test-chat", response_model=TestChatResponse)
async def ai_test_chat(
    request: Request, body: TestChatRequest, admin: AdminUser
) -> TestChatResponse:
    """Sends one message through the active provider, end to end.

    The quickest way to confirm a provider switch worked: change AI_PROVIDER,
    restart, call this.
    """
    ai = get_ai(request)
    result = await ai.complete(
        messages=[ChatMessage(role="user", text=body.message)],
        system="You are a friendly assistant. Keep replies short.",
        task=body.task,
        max_tokens=1024,
        context=UsageContext(user_id=admin.id),
    )
    return TestChatResponse(
        provider=ai.registry.active_name,
        model=ai.model_for(body.task),
        ok=result.error is None,
        text=result.text,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost_usd=result.usage.cost_usd,
        error=result.error.code if result.error else None,
    )
