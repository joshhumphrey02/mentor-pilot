import random

import pytest

from app.ai.blocks import CalloutBlock, MarkdownBlock, SuggestedRepliesBlock
from app.ai.stream_parser import (
    BlockComplete,
    BlockDelta,
    BlockStart,
    BlockStreamParser,
    ParserEvent,
)

REPLY = """Great question! An LED only lets current flow **one way**.

:::callout safety
Never connect an LED straight to a 9V battery. Always use a resistor.
:::

Here is why:

1. The long leg is the anode.
2. The short leg is the cathode.

:::replies
Show me a diagram
Why do I need a resistor?
- What is an anode?
:::
"""


def parse(
    text: str, chunk_sizes: list[int] | None = None
) -> tuple[BlockStreamParser, list[ParserEvent]]:
    parser = BlockStreamParser()
    events: list[ParserEvent] = []
    if chunk_sizes is None:
        events += parser.feed(text)
    else:
        position, sizes = 0, iter(chunk_sizes)
        while position < len(text):
            size = next(sizes, 7)
            events += parser.feed(text[position : position + size])
            position += size
    events += parser.finish()
    return parser, events


def test_text_and_directives_become_ordered_blocks() -> None:
    parser, _ = parse(REPLY)

    assert [type(block) for block in parser.blocks] == [
        MarkdownBlock,
        CalloutBlock,
        MarkdownBlock,
        SuggestedRepliesBlock,
    ]
    intro, callout, body, replies = parser.blocks
    assert isinstance(intro, MarkdownBlock) and intro.text.startswith("Great question!")
    assert isinstance(callout, CalloutBlock)
    assert callout.variant == "safety"
    assert callout.text.startswith("Never connect an LED")
    assert isinstance(body, MarkdownBlock) and "1. The long leg" in body.text
    assert isinstance(replies, SuggestedRepliesBlock)
    assert replies.replies == [
        "Show me a diagram",
        "Why do I need a resistor?",
        "What is an anode?",
    ]


@pytest.mark.parametrize("seed", range(25))
def test_result_does_not_depend_on_how_the_stream_is_chunked(seed: int) -> None:
    """Tokens can split anywhere, including in the middle of a ':::' fence."""
    expected, _ = parse(REPLY)
    rng = random.Random(seed)  # noqa: S311  (not security-sensitive)
    sizes = [rng.randint(1, 9) for _ in range(len(REPLY))]

    chunked, _ = parse(REPLY, sizes)

    assert chunked.blocks == expected.blocks


def test_one_character_at_a_time() -> None:
    expected, _ = parse(REPLY)
    chunked, _ = parse(REPLY, [1] * len(REPLY))

    assert chunked.blocks == expected.blocks


def test_markdown_streams_as_it_arrives() -> None:
    parser = BlockStreamParser()

    events = parser.feed("Hello the")

    assert events == [BlockStart(0, "markdown"), BlockDelta(0, "Hello the")]
    assert parser.feed("re") == [BlockDelta(0, "re")]


def test_directive_syntax_is_never_streamed_as_text() -> None:
    _, events = parse(REPLY, [3] * len(REPLY))

    streamed = "".join(event.text for event in events if isinstance(event, BlockDelta))
    assert ":::" not in streamed
    assert "callout" not in streamed
    assert "Never connect" not in streamed, "directive bodies arrive whole, in block_complete"


def test_deltas_rebuild_each_markdown_block_exactly() -> None:
    parser, events = parse(REPLY, [4] * len(REPLY))

    for index, block in enumerate(parser.blocks):
        if isinstance(block, MarkdownBlock):
            streamed = "".join(
                event.text
                for event in events
                if isinstance(event, BlockDelta) and event.index == index
            )
            assert streamed.strip() == block.text


def test_every_block_starts_before_it_completes() -> None:
    parser, events = parse(REPLY, [5] * len(REPLY))

    for index in range(len(parser.blocks)):
        kinds = [type(event) for event in events if event.index == index]
        assert kinds[0] is BlockStart
        assert kinds[-1] is BlockComplete
        assert kinds.count(BlockStart) == kinds.count(BlockComplete) == 1


def test_unknown_callout_variant_falls_back_to_tip() -> None:
    parser, _ = parse(":::callout sparkly\nNice work.\n:::\n")

    assert parser.blocks == [CalloutBlock(variant="tip", text="Nice work.")]


def test_variant_names_are_forgiving() -> None:
    parser, _ = parse(":::callout Judge-Insight\nJudges love a logbook.\n:::\n")

    assert parser.blocks == [CalloutBlock(variant="judge_insight", text="Judges love a logbook.")]


def test_unknown_directive_is_left_as_text() -> None:
    parser, _ = parse(":::spoiler\nhidden\n:::\n")

    assert len(parser.blocks) == 1
    assert isinstance(parser.blocks[0], MarkdownBlock)
    assert ":::spoiler" in parser.blocks[0].text


def test_fences_inside_code_blocks_are_code() -> None:
    text = "Example:\n\n```\n:::callout tip\nnot a callout\n:::\n```\n"

    parser, _ = parse(text, [2] * len(text))

    assert len(parser.blocks) == 1
    assert isinstance(parser.blocks[0], MarkdownBlock)
    assert ":::callout tip" in parser.blocks[0].text


def test_colons_mid_line_are_ordinary_text() -> None:
    parser, _ = parse("The ratio is 3:::1 here.\nNext line.")

    assert parser.blocks == [MarkdownBlock(text="The ratio is 3:::1 here.\nNext line.")]


def test_stream_cut_off_inside_a_directive_keeps_what_arrived() -> None:
    parser, _ = parse("Careful.\n\n:::callout safety\nWear eye protec")

    assert parser.blocks[-1] == CalloutBlock(variant="safety", text="Wear eye protec")


def test_empty_directives_produce_no_block() -> None:
    parser, _ = parse("Hi.\n\n:::replies\n:::\n\n:::callout tip\n\n:::\n")

    assert parser.blocks == [MarkdownBlock(text="Hi.")]


def test_replies_are_capped_at_four() -> None:
    parser, _ = parse(":::replies\na\nb\nc\nd\ne\nf\n:::\n")

    block = parser.blocks[0]
    assert isinstance(block, SuggestedRepliesBlock)
    assert block.replies == ["a", "b", "c", "d"]


def test_empty_stream_yields_nothing() -> None:
    parser, events = parse("")

    assert parser.blocks == [] and events == []


def test_whitespace_only_stream_yields_nothing() -> None:
    parser, _ = parse("\n\n   \n")

    assert parser.blocks == []
