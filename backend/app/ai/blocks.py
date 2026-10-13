"""Render blocks: the typed pieces an assistant message is made of.

A message is an ordered list of blocks rather than one markdown string, so the
UI can render each kind with its own component. These schemas are the single
definition: they validate what is stored and, through OpenAPI, generate the
TypeScript types the frontend renders from.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

CalloutVariant = Literal["tip", "safety", "judge_insight", "common_mistake"]


class MarkdownBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    text: str


class CalloutBlock(BaseModel):
    type: Literal["callout"] = "callout"
    variant: CalloutVariant = "tip"
    text: str


class SuggestedRepliesBlock(BaseModel):
    type: Literal["suggested_replies"] = "suggested_replies"
    replies: list[Annotated[str, Field(max_length=120)]] = Field(max_length=4)


class ErrorBlock(BaseModel):
    """A friendly failure notice, shown in place of an answer."""

    type: Literal["error"] = "error"
    code: str
    text: str
    retryable: bool = False


Block = Annotated[
    MarkdownBlock | CalloutBlock | SuggestedRepliesBlock | ErrorBlock,
    Field(discriminator="type"),
]

BLOCK_LIST: TypeAdapter[list[Block]] = TypeAdapter(list[Block])


def dump_blocks(blocks: list[Block]) -> list[dict[str, Any]]:
    return [block.model_dump(mode="json") for block in blocks]


def load_blocks(raw: list[dict[str, Any]]) -> list[Block]:
    return BLOCK_LIST.validate_python(raw)
