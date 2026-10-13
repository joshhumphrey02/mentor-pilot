from typing import Annotated

from pydantic import BaseModel, Field

from app.ai.blocks import ChecklistBlock, StageTransitionBlock
from app.ai.tools.base import Tool, ToolContext, ToolOutcome
from app.core.errors import AppError
from app.services import pathway


class ChecklistUpdate(BaseModel):
    item_key: Annotated[str, Field(description="The deliverable's key, from the stage checklist.")]
    done: bool
    evidence: Annotated[
        str,
        Field(
            max_length=300,
            description="What the learner did or said that shows this is done. Required when "
            "ticking an item.",
        ),
    ] = ""


class UpdateChecklistArgs(BaseModel):
    updates: Annotated[list[ChecklistUpdate], Field(min_length=1, max_length=6)]


async def _update_checklist(context: ToolContext, args: UpdateChecklistArgs) -> ToolOutcome:
    stage_key = context.project.current_stage
    changed: list[str] = []
    for update in args.updates:
        if update.done and not update.evidence.strip():
            return ToolOutcome(
                result=f"'{update.item_key}' was not ticked: say what the learner did that "
                "shows it is done.",
                is_error=True,
            )
        try:
            await pathway.set_item(
                context.session,
                context.project,
                stage_key=stage_key,
                item_key=update.item_key,
                done=update.done,
                note=update.evidence,
                by="mentor",
            )
        except AppError:
            valid = ", ".join(
                item["key"]
                for item in pathway.current(
                    await pathway.progress(context.session, context.project), context.project
                ).definition.deliverables
            )
            return ToolOutcome(
                result=f"'{update.item_key}' is not an item in this stage. Valid keys: {valid}.",
                is_error=True,
            )
        changed.append(f"{update.item_key} {'done' if update.done else 'not done'}")
    await context.session.commit()

    stage = pathway.current(
        await pathway.progress(context.session, context.project), context.project
    )
    remaining = [item["label"] for item in stage.items if not item["done"]]
    status = (
        "Everything in this stage is ticked."
        if not remaining
        else f"Still to do: {'; '.join(remaining)}."
    )
    return ToolOutcome(
        result=f"Checklist updated. {status}",
        blocks=[ChecklistBlock(stage_key=stage_key)],
        record=f"checklist updated ({', '.join(changed)})",
    )


update_checklist = Tool(
    name="update_checklist",
    description=(
        "Tick or untick deliverables on the current stage's checklist. Tick an item only "
        "when the learner has actually done it and you can say what shows that; the "
        "checklist is their record of real progress, not a to-do list to clear."
    ),
    args=UpdateChecklistArgs,
    run=_update_checklist,
    status=lambda _args: "Updating your checklist…",
)


class AdvanceStageArgs(BaseModel):
    summary: Annotated[
        str,
        Field(
            max_length=300,
            description="One or two sentences on what the learner achieved in this stage, "
            "addressed to them.",
        ),
    ]


async def _advance(context: ToolContext, args: AdvanceStageArgs) -> ToolOutcome:
    stages = await pathway.progress(context.session, context.project)
    here = pathway.current(stages, context.project)
    following = pathway.next_after(stages, here.definition.key)
    if following is None:
        return ToolOutcome(
            result="This is the final stage, so there is no next stage to move to.",
            is_error=True,
        )
    unticked = [item["label"] for item in here.items if not item["done"]]
    note = (
        f" Note that these checklist items are still unticked: {'; '.join(unticked)}."
        if unticked
        else ""
    )
    return ToolOutcome(
        result=f"The learner now sees a card asking them to confirm moving from "
        f"'{here.definition.title}' to '{following.definition.title}'. Nothing has changed "
        f"yet: the project moves only when they confirm.{note} End your reply here and "
        "wait for them.",
        blocks=[
            StageTransitionBlock(
                from_stage=here.definition.key,
                to_stage=following.definition.key,
                from_title=here.definition.title,
                to_title=following.definition.title,
                summary=args.summary,
            )
        ],
        record=f"proposed moving on to the {following.definition.title} stage",
    )


advance_stage = Tool(
    name="advance_stage",
    description=(
        "Propose moving the project to the next stage. Use this when the current stage's "
        "exit criteria are met. It shows the learner a confirmation card; the project only "
        "moves when they agree. Do not use it to rush: a stage is finished when the learner "
        "has done the thinking, not when you have explained it."
    ),
    args=AdvanceStageArgs,
    run=_advance,
    status=lambda _args: "Checking you're ready for the next stage…",
)


class RevisitStageArgs(BaseModel):
    stage_key: Annotated[str, Field(description="The key of the earlier stage to go back to.")]
    reason: Annotated[str, Field(max_length=300)]


async def _revisit(context: ToolContext, args: RevisitStageArgs) -> ToolOutcome:
    try:
        await pathway.revisit(context.session, context.project, args.stage_key)
    except AppError as exc:
        return ToolOutcome(result=exc.detail, is_error=True)
    stage = pathway.current(
        await pathway.progress(context.session, context.project), context.project
    )
    return ToolOutcome(
        result=f"The project is back at the '{stage.definition.title}' stage. Work from later "
        "stages has been kept.",
        blocks=[ChecklistBlock(stage_key=stage.definition.key)],
        record=f"went back to the {stage.definition.title} stage: {args.reason}",
    )


revisit_stage = Tool(
    name="revisit_stage",
    description=(
        "Take the project back to an earlier stage, for example when testing shows the "
        "research question needs to change. Going back is a normal part of real science and "
        "engineering; say so. Agree it with the learner first."
    ),
    args=RevisitStageArgs,
    run=_revisit,
    status=lambda _args: "Going back a stage…",
)
