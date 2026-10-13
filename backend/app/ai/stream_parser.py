"""Turns the model's streamed text into render blocks as it arrives.

Plain text becomes markdown blocks, streamed token by token. Two lightweight
block kinds are written by the model inline, as fenced directives:

    :::callout safety
    Never connect an LED straight to a 9V battery.
    :::

    :::replies
    Show me an example
    Why does that happen?
    :::

Directives are buffered and emitted whole when they close, so the learner
never sees half-written syntax. The only text ever held back is a line that
might still turn out to be the start of a directive.
"""

from dataclasses import dataclass
from typing import get_args

from app.ai.blocks import (
    Block,
    CalloutBlock,
    CalloutVariant,
    MarkdownBlock,
    SuggestedRepliesBlock,
)

FENCE = ":::"
CODE_FENCE = "```"
MAX_REPLIES = 4
_VARIANTS: tuple[str, ...] = get_args(CalloutVariant)


@dataclass(frozen=True)
class BlockStart:
    index: int
    block_type: str


@dataclass(frozen=True)
class BlockDelta:
    index: int
    text: str


@dataclass(frozen=True)
class BlockComplete:
    index: int
    block: Block


ParserEvent = BlockStart | BlockDelta | BlockComplete


class BlockStreamParser:
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self._events: list[ParserEvent] = []
        # The line currently being received (no newline yet).
        self._line = ""
        # How much of that line has already been streamed out as markdown.
        self._flushed = 0
        self._markdown: list[str] | None = None
        self._directive: tuple[str, str, list[str]] | None = None  # (kind, argument, body lines)
        self._in_code = False

    # --- public ---------------------------------------------------------------

    def feed(self, text: str) -> list[ParserEvent]:
        while text:
            head, newline, text = text.partition("\n")
            self._line += head
            if newline:
                self._end_line()
            else:
                self._flush_partial()
        return self._drain()

    def add(self, block: Block) -> list[ParserEvent]:
        """Appends a block that did not come from the text stream (a tool made it)."""
        self._close_markdown()
        self._events.append(BlockComplete(self._next_index, block))
        self.blocks.append(block)
        return self._drain()

    def finish(self) -> list[ParserEvent]:
        """Closes whatever is still open. Call at the end of each model response;
        the parser can then be fed again, continuing the same list of blocks."""
        if self._line:
            self._end_line(final=True)
        if self._directive is not None:
            # The model stopped mid-directive (token limit): keep what arrived.
            self._close_directive()
        self._close_markdown()
        self._in_code = False
        return self._drain()

    # --- internals ------------------------------------------------------------

    def _drain(self) -> list[ParserEvent]:
        events, self._events = self._events, []
        return events

    @property
    def _next_index(self) -> int:
        return len(self.blocks)

    def _could_be_fence(self) -> bool:
        """Whether the current partial line might still become a directive line.

        Only a line we have sent nothing of can be held back; once any of it
        has streamed out it is committed as text.
        """
        if self._in_code or self._flushed > 0:
            return False
        stripped = self._line.lstrip(" ")
        return FENCE.startswith(stripped) or stripped.startswith(FENCE)

    def _flush_partial(self) -> None:
        """Streams the unsent part of the current line, unless it must be held."""
        if self._directive is not None or self._could_be_fence():
            return
        self._emit_markdown(self._line[self._flushed :])
        self._flushed = len(self._line)

    def _emit_markdown(self, text: str) -> None:
        if not text:
            return
        if self._markdown is None:
            if not text.strip():
                return  # no block for leading blank lines
            self._markdown = []
            self._events.append(BlockStart(self._next_index, "markdown"))
        self._markdown.append(text)
        self._events.append(BlockDelta(self._next_index, text))

    def _end_line(self, *, final: bool = False) -> None:
        line, flushed = self._line, self._flushed
        self._line, self._flushed = "", 0
        stripped = line.strip()

        if self._directive is not None:
            if stripped == FENCE:
                self._close_directive()
            else:
                self._directive[2].append(line)
            return

        if stripped.startswith(CODE_FENCE):
            # Inside a code block, ":::" is just code.
            self._in_code = not self._in_code

        if flushed == 0 and not self._in_code and stripped.startswith(FENCE):
            header = stripped[len(FENCE) :].strip()
            kind, _, argument = header.partition(" ")
            if kind in ("callout", "replies"):
                self._close_markdown()
                self._directive = (kind, argument.strip(), [])
                self._events.append(
                    BlockStart(
                        self._next_index, "callout" if kind == "callout" else "suggested_replies"
                    )
                )
                return
            # Not one of ours: it is ordinary text after all.

        self._emit_markdown(line[flushed:] + ("" if final else "\n"))

    def _close_markdown(self) -> None:
        if self._markdown is None:
            return
        text = "".join(self._markdown).strip()
        index = self._next_index
        self._markdown = None
        if text:
            block = MarkdownBlock(text=text)
            self.blocks.append(block)
            self._events.append(BlockComplete(index, block))

    def _close_directive(self) -> None:
        assert self._directive is not None  # noqa: S101
        kind, argument, lines = self._directive
        self._directive = None
        index = self._next_index
        block: Block
        if kind == "callout":
            variant = argument.lower().replace("-", "_")
            block = CalloutBlock.model_validate(
                {
                    "variant": variant if variant in _VARIANTS else "tip",
                    "text": "\n".join(lines).strip(),
                }
            )
            if not block.text:
                return
        else:
            replies = [
                reply[:120]
                for reply in (line.strip().lstrip("-*•").strip() for line in lines)
                if reply
            ][:MAX_REPLIES]
            if not replies:
                return
            block = SuggestedRepliesBlock(replies=replies)
        self.blocks.append(block)
        self._events.append(BlockComplete(index, block))
