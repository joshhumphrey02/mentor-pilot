"""The agent-tool framework.

A tool is a Pydantic model for its arguments plus an async function. The model
is what the AI is shown (as JSON Schema) and what its call is validated against,
so a malformed call is caught before any code runs and reported back to the AI
to correct.
"""

import copy
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.blocks import Block
from app.ai.types import ToolSpec
from app.core.config import Settings
from app.models import Project


@dataclass
class ToolContext:
    session: AsyncSession
    project: Project
    settings: Settings
    http: httpx.AsyncClient


@dataclass
class ToolOutcome:
    # What the model is told happened. Tool results are data the model reads,
    # so keep it factual and short.
    result: str
    # What the learner sees.
    blocks: list[Block] = field(default_factory=list)
    # A one-line note kept in the conversation history, so in later turns the
    # model knows what it showed. Empty for tools with nothing worth recalling.
    record: str = ""
    is_error: bool = False


@dataclass(frozen=True)
class Tool[ArgsT: BaseModel]:
    name: str
    description: str
    args: type[ArgsT]
    run: Callable[[ToolContext, ArgsT], Awaitable[ToolOutcome]]
    # Shown to the learner while the tool runs, e.g. "Finding photos of an LDR…".
    status: Callable[[ArgsT], str]
    # Lets a tool hide itself when it cannot work (no API key configured).
    available: Callable[[Settings], bool] = lambda _settings: True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description, parameters=json_schema(self.args)
        )

    def status_for(self, raw_arguments: dict[str, Any]) -> str | None:
        """The progress note for a call, or None if its arguments are invalid."""
        try:
            return self.status(self.args.model_validate(raw_arguments))
        except ValidationError:
            return None

    async def call(self, context: ToolContext, raw_arguments: dict[str, Any]) -> ToolOutcome:
        try:
            arguments = self.args.model_validate(raw_arguments)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'input'}: {error['msg']}"
                for error in exc.errors()[:8]
            )
            return ToolOutcome(
                result=f"The call was rejected because its arguments were invalid. {problems}. "
                "Correct them and call the tool again.",
                is_error=True,
            )
        return await self.run(context, arguments)


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """A self-contained JSON Schema for a tool's arguments.

    Pydantic emits shared definitions under `$defs` with `$ref` pointers, which
    not every provider accepts in tool parameters. They are inlined here, and
    the redundant `title` keys dropped, so one schema works for all of them.
    """
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].rsplit("/", 1)[-1]
                merged = {
                    **copy.deepcopy(definitions[name]),
                    **{k: v for k, v in node.items() if k != "$ref"},
                }
                return resolve(merged)
            return {
                key: resolve(value)
                for key, value in node.items()
                # A property may itself be called "title"; only drop the
                # annotation, which is always a string.
                if not (key == "title" and isinstance(value, str)) and key != "discriminator"
            }
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved
