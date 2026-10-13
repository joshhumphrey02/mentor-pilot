from typing import Annotated

from pydantic import BaseModel, Field

from app.ai.blocks import ComparisonRow, ComparisonTableBlock, IdeaCard, IdeaCardsBlock
from app.ai.tools.base import Tool, ToolContext, ToolOutcome
from app.services import pathway

NEXT_STAGE_AFTER_CHOOSING = "research_question"


class ProposeIdeasArgs(BaseModel):
    ideas: Annotated[
        list[IdeaCard],
        Field(min_length=3, max_length=6, description="Three to six genuinely different ideas."),
    ]


async def _propose(_context: ToolContext, args: ProposeIdeasArgs) -> ToolOutcome:
    titles = "; ".join(f"{n}. {idea.title}" for n, idea in enumerate(args.ideas, start=1))
    return ToolOutcome(
        result=f"The learner can now see {len(args.ideas)} idea cards, each with Explore, "
        "Compare and Choose buttons. Do not repeat the cards' contents in your reply; "
        "ask which ones interest them.",
        blocks=[IdeaCardsBlock(ideas=args.ideas)],
        record=f"idea cards: {titles}",
    )


propose_project_ideas = Tool(
    name="propose_project_ideas",
    description=(
        "Show the learner three to six project ideas as swipeable cards. Use this when they "
        "have a problem in mind and need options to choose from. Tailor the ideas to their "
        "problem, grade, budget and the materials they can realistically get, and make them "
        "different in kind (an investigation, a build, a comparison). Fill every field "
        "honestly, including difficulty, cost in rand and safety level."
    ),
    args=ProposeIdeasArgs,
    run=_propose,
    status=lambda _args: "Putting together some project ideas…",
)


class CompareIdeasArgs(BaseModel):
    title: Annotated[str, Field(max_length=100)] = "Comparing your ideas"
    options: Annotated[
        list[Annotated[str, Field(max_length=80)]],
        Field(min_length=2, max_length=4, description="The idea titles being compared."),
    ]
    rows: Annotated[
        list[ComparisonRow],
        Field(
            min_length=3,
            max_length=10,
            description="One row per criterion, such as cost, difficulty, time, safety, "
            "materials and what judges would think.",
        ),
    ]


async def _compare(_context: ToolContext, args: CompareIdeasArgs) -> ToolOutcome:
    for row in args.rows:
        if len(row.values) != len(args.options):
            return ToolOutcome(
                result=f"Row '{row.criterion}' has {len(row.values)} values but there are "
                f"{len(args.options)} options. Give exactly one value per option, in order.",
                is_error=True,
            )
    return ToolOutcome(
        result="The learner can now see the comparison table. Do not repeat it; help them "
        "think about which trade-offs matter most to them.",
        blocks=[ComparisonTableBlock(title=args.title, options=args.options, rows=args.rows)],
        record=f"comparison table of: {', '.join(args.options)}",
    )


compare_ideas = Tool(
    name="compare_ideas",
    description=(
        "Show a side-by-side comparison table of two to four shortlisted ideas. Use this when "
        "the learner is deciding between ideas. Keep each cell to a few words."
    ),
    args=CompareIdeasArgs,
    run=_compare,
    status=lambda _args: "Comparing the ideas side by side…",
)


class SelectIdeaArgs(BaseModel):
    idea: Annotated[IdeaCard, Field(description="The idea the learner chose, as it was proposed.")]
    reason: Annotated[
        str, Field(max_length=300, description="Why the learner chose it, in their words if given.")
    ] = ""


async def _select(context: ToolContext, args: SelectIdeaArgs) -> ToolOutcome:
    project = context.project
    project.idea = {**args.idea.model_dump(mode="json"), "reason": args.reason}
    project.title = args.idea.title
    await pathway.set_item(
        context.session,
        project,
        stage_key="idea_development",
        item_key="chosen_idea",
        done=True,
        note=args.reason,
        by="mentor",
    )
    stage = await pathway.move_to(context.session, project, NEXT_STAGE_AFTER_CHOOSING)
    await context.session.commit()
    return ToolOutcome(
        result=f"Saved. The project is now called '{project.title}' and has moved to the "
        f"'{stage.definition.title}' stage. Congratulate the learner briefly, then begin "
        "that stage.",
        record=f"the learner chose the idea '{args.idea.title}'",
    )


select_idea = Tool(
    name="select_idea",
    description=(
        "Lock in the idea the learner has chosen. This names the project after it and moves "
        "the project to the Research Question stage. Call it only when the learner has "
        "clearly committed to one idea (for example by tapping 'Choose this' or saying so), "
        "never because you think it is the best one."
    ),
    args=SelectIdeaArgs,
    run=_select,
    status=lambda args: f"Saving “{args.idea.title}” as your project…",
)
