from app.ai.blocks import BomTableBlock, ChartBlock, DiagramBlock, ExperimentPlanBlock, QuizBlock
from app.ai.tools.base import Tool, ToolContext, ToolOutcome

# Each of these tools takes the block itself as its arguments: the model fills
# in the structure, the schema validates it, and the UI renders it.

_MERMAID_STARTS = (
    "flowchart",
    "graph",
    "sequencediagram",
    "statediagram",
    "classdiagram",
    "erdiagram",
    "gantt",
    "pie",
    "mindmap",
    "timeline",
    "journey",
    "quadrantchart",
    "xychart",
    "block",
)


async def _diagram(_context: ToolContext, args: DiagramBlock) -> ToolOutcome:
    source = args.mermaid.strip()
    # Models often wrap the source in a code fence despite being asked not to.
    if source.startswith("```"):
        source = source.strip("`").removeprefix("mermaid").strip()
    first_word = source.split(maxsplit=1)[0].lower().split("-")[0] if source else ""
    if not first_word.startswith(_MERMAID_STARTS):
        return ToolOutcome(
            result="That is not valid Mermaid: the source must begin with a diagram type "
            "such as 'flowchart TD'. Fix it and call the tool again.",
            is_error=True,
        )
    return ToolOutcome(
        result="The learner can now see the diagram. Refer to it rather than describing it again.",
        blocks=[args.model_copy(update={"mermaid": source})],
        record=f"diagram: {args.title}",
    )


render_diagram = Tool(
    name="render_diagram",
    description=(
        "Draw a diagram from Mermaid source: a flowchart of a process or method, the "
        "engineering design cycle, how the parts of a system connect, or a timeline. Use it "
        "whenever a picture would explain something better than a paragraph. Keep it to a "
        "handful of nodes with short labels so it reads on a phone. Not for electronic "
        "circuits."
    ),
    args=DiagramBlock,
    run=_diagram,
    status=lambda args: f"Drawing “{args.title}”…",
)


async def _chart(_context: ToolContext, args: ChartBlock) -> ToolOutcome:
    return ToolOutcome(
        result="The learner can now see the chart. Ask them what they notice in it before "
        "you tell them what you see.",
        blocks=[args],
        record=f"{args.chart_type} chart: {args.title}",
    )


render_chart = Tool(
    name="render_chart",
    description=(
        "Plot data as a line, bar or scatter chart. Use it for the learner's own measurements "
        "once they have given them to you, or to illustrate a concept with clearly labelled "
        "example data. Only plot numbers the learner actually reported: never invent, "
        "estimate or smooth their results."
    ),
    args=ChartBlock,
    run=_chart,
    status=lambda _args: "Plotting your data…",
)


async def _bom(_context: ToolContext, args: BomTableBlock) -> ToolOutcome:
    total = round(sum(item.quantity * item.unit_price_zar for item in args.items), 2)
    return ToolOutcome(
        result=f"The learner can now see the bill of materials. The total comes to "
        f"R{total:.2f}. Check that fits their budget.",
        blocks=[args.model_copy(update={"total_zar": total})],
        record=f"bill of materials ({len(args.items)} items, about R{total:.0f})",
    )


build_bill_of_materials = Tool(
    name="build_bill_of_materials",
    description=(
        "Show a bill of materials: each part with its quantity, an estimated price in rand, "
        "where to get it, and a cheaper or recycled substitute where one exists. Use it when "
        "the learner is planning what to buy or collect. Prices are estimates, so say so. "
        "The total is calculated for you; leave total_zar out."
    ),
    args=BomTableBlock,
    run=_bom,
    status=lambda _args: "Working out what you'll need…",
)


async def _experiment_plan(_context: ToolContext, args: ExperimentPlanBlock) -> ToolOutcome:
    return ToolOutcome(
        result="The learner can now see the experiment plan with a blank data table. The "
        "hypothesis is not included: ask them to write it themselves.",
        blocks=[args],
        record=f"experiment plan: {args.title}",
    )


create_experiment_plan = Tool(
    name="create_experiment_plan",
    description=(
        "Lay out an experiment plan: the independent, dependent and controlled variables, "
        "the number of trials, and a blank data table to fill in. Use it once the learner has "
        "told you what they will change and what they will measure, and base it on what they "
        "said rather than deciding for them."
    ),
    args=ExperimentPlanBlock,
    run=_experiment_plan,
    status=lambda _args: "Laying out your experiment plan…",
)


async def _quiz(_context: ToolContext, args: QuizBlock) -> ToolOutcome:
    for number, question in enumerate(args.questions, start=1):
        if question.correct_index >= len(question.options):
            return ToolOutcome(
                result=f"Question {number}: correct_index {question.correct_index} is out of "
                f"range for {len(question.options)} options.",
                is_error=True,
            )
    return ToolOutcome(
        result=f"The learner now has a {len(args.questions)}-question quick check, answered "
        "one question at a time with instant feedback. Wait for them to tell you how it went.",
        blocks=[args],
        record=f"quiz: {args.title} ({len(args.questions)} questions)",
    )


quiz_me = Tool(
    name="quiz_me",
    description=(
        "Give the learner a short multiple-choice quick check (three to five questions) with "
        "an explanation for each answer. Use it to confirm understanding before moving to a "
        "new stage, or when they ask to be tested. Ask about ideas, not trivia, and make the "
        "wrong options the mistakes learners really make."
    ),
    args=QuizBlock,
    run=_quiz,
    status=lambda _args: "Writing a quick check…",
)
