from app.ai.blocks import MentorHandoffBlock
from app.ai.tools.base import Tool, ToolContext, ToolOutcome


async def _handoff(_context: ToolContext, args: MentorHandoffBlock) -> ToolOutcome:
    return ToolOutcome(
        result="The learner now sees a card offering to connect them with a vetted human "
        "mentor, with a button to make the request. Nothing has been sent: they decide. "
        "Carry on helping with whatever can be done without hands-on work.",
        blocks=[args],
        record=f"offered a human mentor for: {', '.join(args.help_types)}",
    )


request_human_mentor = Tool(
    name="request_human_mentor",
    description=(
        "Offer to connect the learner with a vetted human mentor for hands-on help: building "
        "hardware, lab access, finding materials, coding in person, or expo coaching. Use it "
        "at the Design and Prototyping stage once the design and materials list are ready, "
        "and at any stage when the learner needs physical help or supervision you cannot "
        "give, especially for anything with a safety risk. It shows a card; the learner "
        "chooses whether to send the request."
    ),
    args=MentorHandoffBlock,
    run=_handoff,
    status=lambda _args: "Looking into human mentors…",
)
