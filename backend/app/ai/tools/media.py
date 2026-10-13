"""Tools that fetch real photos and videos from outside services.

Everything that comes back is third-party content, so it is treated as data:
filtered, trimmed, and never passed to the model as anything it should obey.
"""

import html
import re
from typing import Annotated, Any

import httpx
import structlog
from pydantic import BaseModel, Field

from app.ai.blocks import GalleryImage, ImageGalleryBlock, VideoCard, VideoCardsBlock
from app.ai.tools.base import Tool, ToolContext, ToolOutcome

logger = structlog.get_logger(__name__)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3/search"
MAX_IMAGES = 6
MAX_VIDEOS = 4
THUMBNAIL_WIDTH = 640

_TAGS = re.compile(r"<[^>]+>")
# Wikimedia Commons is an open archive, not a children's collection. Results
# whose title or description match any of these are dropped.
_UNSUITABLE = re.compile(
    r"\b(nude|nudity|naked|erotic|porn|sex|sexual|genital|penis|vagina|breast|"
    r"corpse|cadaver|gore|autopsy|execution|suicide|swastika)\w*",
    re.IGNORECASE,
)
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/svg+xml", "image/webp", "image/gif"}


def _plain(value: Any, limit: int) -> str:
    """Metadata fields arrive as HTML snippets; reduce them to short plain text."""
    text = html.unescape(_TAGS.sub("", str(value or ""))).strip()
    return " ".join(text.split())[:limit]


class SearchImagesArgs(BaseModel):
    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=80,
            description="What to find a photo of, as a short noun phrase, e.g. "
            "'light dependent resistor' or 'breadboard'.",
        ),
    ]


async def find_images(
    http: httpx.AsyncClient, contact_email: str, query: str, *, limit: int = MAX_IMAGES
) -> list[GalleryImage] | None:
    """Suitable, credited photos for a query. None means the search itself failed."""
    if _UNSUITABLE.search(query):
        return []
    try:
        response = await http.get(
            COMMONS_API,
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f"{query} filetype:bitmap|drawing",
                "gsrnamespace": 6,  # the File: namespace
                "gsrlimit": 15,
                "prop": "imageinfo",
                "iiprop": "url|mime|size|extmetadata",
                "iiurlwidth": THUMBNAIL_WIDTH,
            },
            headers={"User-Agent": f"MentorPilot/1.0 (educational app; {contact_email})"},
        )
        response.raise_for_status()
        pages = (response.json().get("query") or {}).get("pages") or {}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("tools.image_search_failed", error=type(exc).__name__)
        return None

    images: list[GalleryImage] = []
    # The API returns pages keyed by id, unordered; `index` is the search rank.
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        title = _plain(str(page.get("title", "")).removeprefix("File:").rsplit(".", 1)[0], 120)
        description = _plain((meta.get("ImageDescription") or {}).get("value"), 300)
        if (
            info.get("mime") not in _IMAGE_TYPES
            or not info.get("thumburl")
            or _UNSUITABLE.search(f"{title} {description}")
        ):
            continue
        images.append(
            GalleryImage(
                url=info.get("url", info["thumburl"]),
                thumbnail_url=info["thumburl"],
                title=title.replace("_", " "),
                source_url=info.get("descriptionurl", ""),
                author=_plain((meta.get("Artist") or {}).get("value"), 80),
                license=_plain((meta.get("LicenseShortName") or {}).get("value"), 40),
                width=info.get("thumbwidth"),
                height=info.get("thumbheight"),
            )
        )
        if len(images) == limit:
            break
    return images


async def _search_images(context: ToolContext, args: SearchImagesArgs) -> ToolOutcome:
    if _UNSUITABLE.search(args.query):
        return ToolOutcome(result="That search is not available.", is_error=True)
    images = await find_images(context.http, context.settings.contact_email, args.query)
    if images is None:
        return ToolOutcome(
            result="The image search is unavailable right now. Carry on without photos, and "
            "describe the item in words instead.",
            is_error=True,
        )
    if not images:
        return ToolOutcome(
            result=f"No suitable photos were found for '{args.query}'. Try a simpler or more "
            "common name, or describe it in words."
        )
    return ToolOutcome(
        result=f"The learner can now see {len(images)} photos for '{args.query}', with "
        "credits. You have not seen the photos yourself, so do not describe what is in them.",
        blocks=[ImageGalleryBlock(query=args.query, images=images)],
        record=f"photos of {args.query}",
    )


search_images = Tool(
    name="search_images",
    description=(
        "Find real photos on Wikimedia Commons and show them as a gallery with credits. Use "
        "it so the learner can recognise a component, tool, material or natural phenomenon "
        "they will meet in real life. Search for one concrete thing at a time."
    ),
    args=SearchImagesArgs,
    run=_search_images,
    status=lambda args: f"Finding photos of {args.query}…",
)


class SearchVideosArgs(BaseModel):
    query: Annotated[
        str,
        Field(
            min_length=2,
            max_length=80,
            description="What the video should teach, e.g. 'how a breadboard works'.",
        ),
    ]


async def _search_videos(context: ToolContext, args: SearchVideosArgs) -> ToolOutcome:
    key = context.settings.youtube_api_key
    if key is None or _UNSUITABLE.search(args.query):
        return ToolOutcome(result="Video search is not available.", is_error=True)
    try:
        response = await context.http.get(
            YOUTUBE_API,
            params={
                "part": "snippet",
                "type": "video",
                "q": f"{args.query} explained for students",
                "maxResults": MAX_VIDEOS,
                "safeSearch": "strict",
                "videoEmbeddable": "true",
                "videoDuration": "medium",
                "relevanceLanguage": "en",
                "key": key.get_secret_value(),
            },
        )
        response.raise_for_status()
        items = response.json().get("items") or []
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("tools.video_search_failed", error=type(exc).__name__)
        return ToolOutcome(
            result="The video search is unavailable right now. Carry on without videos.",
            is_error=True,
        )

    videos = [
        VideoCard(
            video_id=item["id"]["videoId"],
            title=_plain(item["snippet"].get("title"), 120),
            channel=_plain(item["snippet"].get("channelTitle"), 60),
            thumbnail_url=((item["snippet"].get("thumbnails") or {}).get("medium") or {}).get(
                "url", ""
            ),
        )
        for item in items
        if (item.get("id") or {}).get("videoId") and item.get("snippet")
    ]
    if not videos:
        return ToolOutcome(result=f"No videos were found for '{args.query}'.")
    return ToolOutcome(
        result=f"The learner can now see {len(videos)} videos for '{args.query}'. You have "
        "not watched them, so do not claim what they contain; suggest the learner watches "
        "one and tells you what they learned.",
        blocks=[VideoCardsBlock(query=args.query, videos=videos)],
        record=f"videos about {args.query}",
    )


search_videos = Tool(
    name="search_videos",
    description=(
        "Find short educational videos and show them as cards the learner can play. Use it "
        "when watching something move or being done would teach better than reading, such as "
        "a technique, a demonstration or a process."
    ),
    args=SearchVideosArgs,
    run=_search_videos,
    status=lambda args: f"Looking for videos about {args.query}…",
    available=lambda settings: bool(settings.youtube_api_key),
)
