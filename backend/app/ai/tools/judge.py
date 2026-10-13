from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.ai.blocks import JudgeScorecardBlock, RubricScore, ShortStr
from app.ai.tools.base import Tool, ToolContext, ToolOutcome

RULES = (
    "Judge practice has started. From now until you score it, act as a fair but demanding "
    "science-expo judge:\n"
    "- Ask ONE question at a time and wait for the answer. Ask four or five in total.\n"
    "- Ask what real judges ask: why this project, why this method, what the variables were, "
    "what the results mean, what went wrong, what they would do differently, and how they "
    "used AI.\n"
    "- Base each question on this learner's actual project and on their previous answer. "
    "Follow up on vague answers.\n"
    "- Do not coach, praise or correct between questions: a brief neutral acknowledgement, "
    "then the next question. Feedback comes at the end.\n"
    "- After the last answer, call judge_practice again with action 'score'.\n"
    "Start now by telling the learner in one sentence what is about to happen, then ask "
    "your first question."
)


class JudgePracticeArgs(BaseModel):
    action: Annotated[
        Literal["start", "score"],
        Field(description="'start' to begin a practice round; 'score' after the last answer."),
    ]
    scores: Annotated[
        list[RubricScore], Field(max_length=6, description="Required for 'score'.")
    ] = Field(default_factory=list)
    strengths: Annotated[list[ShortStr], Field(max_length=4)] = Field(default_factory=list)
    improvements: Annotated[list[ShortStr], Field(max_length=4)] = Field(default_factory=list)


async def _judge(_context: ToolContext, args: JudgePracticeArgs) -> ToolOutcome:
    if args.action == "start":
        return ToolOutcome(result=RULES, record="started a judge practice round")
    if len(args.scores) < 3 or not args.strengths or not args.improvements:
        return ToolOutcome(
            result="To score the round, give at least three rubric scores, at least one "
            "strength and at least one thing to improve.",
            is_error=True,
        )
    average = sum(score.score for score in args.scores) / len(args.scores)
    return ToolOutcome(
        result="The learner can now see their scorecard. Judge practice is over: return to "
        "your normal mentoring voice, say one encouraging and specific thing, and offer to "
        "practise the weakest area.",
        blocks=[
            JudgeScorecardBlock(
                scores=args.scores, strengths=args.strengths, improvements=args.improvements
            )
        ],
        record=f"judge practice scorecard (average {average:.1f} out of 5)",
    )


judge_practice = Tool(
    name="judge_practice",
    description=(
        "Run a mock judging session, as at a science expo. Call it with action 'start' when "
        "the learner wants to practise being questioned (most useful in the Expo Preparation "
        "stage, or whenever they ask). You then ask tough questions one at a time. After their "
        "last answer, call it with action 'score' and an honest rubric: a learner who is told "
        "everything was great learns nothing, so score what you actually heard."
    ),
    args=JudgePracticeArgs,
    run=_judge,
    status=lambda args: (
        "Putting on the judge's badge…" if args.action == "start" else "Scoring your answers…"
    ),
)
