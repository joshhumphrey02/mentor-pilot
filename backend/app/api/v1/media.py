from typing import get_args

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.ai.blocks import ComponentType, GalleryImage
from app.ai.circuits import COMPONENTS
from app.ai.tools.media import find_images
from app.api.deps import CurrentUser, SettingsDep
from app.core.errors import NotFoundError, error_responses

router = APIRouter(prefix="/media", tags=["media"], responses=error_responses(401, 404))
logger = structlog.get_logger(__name__)

# The photo for "an LED" does not change from one learner to the next, so it
# is looked up once per process rather than on every tap.
_photo_cache: dict[str, GalleryImage | None] = {}


class ComponentPhoto(BaseModel):
    component: str
    label: str
    image: GalleryImage | None


@router.get("/component-photo/{component}", response_model=ComponentPhoto)
async def component_photo(
    component: str, request: Request, _user: CurrentUser, settings: SettingsDep
) -> ComponentPhoto:
    """A real photo of an electronic component, from Wikimedia Commons, with its credit."""
    if component not in get_args(ComponentType):
        raise NotFoundError("We don't know that component.", code="component_not_found")
    spec = COMPONENTS[component]
    if component not in _photo_cache:
        # The same search and filtering the mentor's photo tool uses.
        found = await find_images(
            request.app.state.chat.http, settings.contact_email, spec.photo_query, limit=1
        )
        if found is None:
            # Wikimedia could not be reached: answer without a photo, and do
            # not cache the miss, so the next tap tries again.
            return ComponentPhoto(component=component, label=spec.label, image=None)
        _photo_cache[component] = found[0] if found else None
    return ComponentPhoto(component=component, label=spec.label, image=_photo_cache[component])
