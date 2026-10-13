from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, MailerDep, SessionDep, SettingsDep
from app.core.cookies import clear_auth_cookies
from app.core.errors import error_responses
from app.core.rate_limit import limiter
from app.schemas.user import DeleteAccountRequest, OnboardingRequest, UserOut, UserUpdate
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])

ERRORS = error_responses(400, 401, 403)


@router.get("/me", response_model=UserOut, responses=ERRORS)
async def get_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut, responses=ERRORS)
async def update_me(body: UserUpdate, user: CurrentUser, session: SessionDep) -> UserOut:
    return UserOut.model_validate(await user_service.update_profile(session, user, body))


@router.post("/me/onboarding", response_model=UserOut, responses=ERRORS)
async def complete_onboarding(
    body: OnboardingRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    mailer: MailerDep,
) -> UserOut:
    """Saves the learner's profile. Can be called again later to edit it."""
    updated = await user_service.complete_onboarding(session, settings, mailer, user, body)
    return UserOut.model_validate(updated)


@router.get("/me/export", responses=ERRORS)
@limiter.limit("10/hour")
async def export_my_data(request: Request, user: CurrentUser, session: SessionDep) -> JSONResponse:
    """Downloads everything we hold about you as a JSON file (POPIA right of access)."""
    data: dict[str, Any] = await user_service.export_data(session, user)
    return JSONResponse(
        data,
        headers={"Content-Disposition": 'attachment; filename="mentor-pilot-my-data.json"'},
    )


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
@limiter.limit("10/hour")
async def delete_my_account(
    request: Request,
    body: DeleteAccountRequest,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> Response:
    """Permanently erases your personal data and closes the account (POPIA right to deletion).

    A POST rather than DELETE because it needs a body (the confirmation and
    password), which proxies are free to drop from DELETE requests.
    """
    await user_service.delete_account(
        session, user, password=body.password, storage=request.app.state.storage
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response
