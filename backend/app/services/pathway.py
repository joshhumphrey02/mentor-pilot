"""The project pathway: stage definitions and each project's progress through them."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.core.time import utcnow
from app.models import Project, ProjectStage, ProjectStatus, StageDefinition, StageStatus

STAGES_FILE = Path(__file__).resolve().parents[1] / "pathway" / "stages.yaml"


@dataclass(frozen=True)
class StageProgress:
    definition: StageDefinition
    state: ProjectStage

    @property
    def items(self) -> list[dict[str, Any]]:
        """The checklist, in definition order, with each item's current state."""
        return [
            {
                "key": item["key"],
                "label": item["label"],
                "done": bool(self.state.checklist.get(item["key"], {}).get("done")),
                "note": str(self.state.checklist.get(item["key"], {}).get("note") or ""),
            }
            for item in self.definition.deliverables
        ]


def default_definitions() -> list[StageDefinition]:
    data = yaml.safe_load(STAGES_FILE.read_text())
    return [
        StageDefinition(
            key=stage["key"],
            position=position,
            title=stage["title"],
            goal=stage["goal"],
            deliverables=stage["deliverables"],
            exit_criteria=stage["exit_criteria"],
            instructions=stage.get("instructions", "").strip(),
            handoff=bool(stage.get("handoff", False)),
            version=int(data.get("version", 1)),
        )
        for position, stage in enumerate(data["stages"], start=1)
    ]


async def ensure_definitions(session: AsyncSession) -> None:
    """Loads the shipped stages into an empty table. Existing rows are never
    overwritten: once seeded, the table is what admins edit."""
    if await session.scalar(select(func.count()).select_from(StageDefinition)):
        return
    session.add_all(default_definitions())
    await session.commit()


async def definitions(session: AsyncSession) -> list[StageDefinition]:
    return list(await session.scalars(select(StageDefinition).order_by(StageDefinition.position)))


async def start_project(session: AsyncSession, project: Project) -> None:
    """Creates the project's stage rows, with the first one active. Does not commit."""
    stages = await definitions(session)
    now = utcnow()
    for index, definition in enumerate(stages):
        session.add(
            ProjectStage(
                project_id=project.id,
                stage_key=definition.key,
                status=(StageStatus.ACTIVE if index == 0 else StageStatus.LOCKED).value,
                started_at=now if index == 0 else None,
            )
        )
    if stages:
        project.current_stage = stages[0].key


async def progress(session: AsyncSession, project: Project) -> list[StageProgress]:
    stages = await _load(session, project)
    if not stages:
        # A project from before the pathway existed: give it its stages now.
        await start_project(session, project)
        await session.flush()
        stages = await _load(session, project)
    return stages


async def _load(session: AsyncSession, project: Project) -> list[StageProgress]:
    rows = (
        await session.execute(
            select(StageDefinition, ProjectStage)
            .join(ProjectStage, ProjectStage.stage_key == StageDefinition.key)
            .where(ProjectStage.project_id == project.id)
            .order_by(StageDefinition.position)
        )
    ).all()
    return [StageProgress(definition=row[0], state=row[1]) for row in rows]


def _find(stages: list[StageProgress], key: str) -> StageProgress:
    for stage in stages:
        if stage.definition.key == key:
            return stage
    raise NotFoundError("That stage doesn't exist.", code="stage_not_found")


def current(stages: list[StageProgress], project: Project) -> StageProgress:
    return _find(stages, project.current_stage)


def next_after(stages: list[StageProgress], key: str) -> StageProgress | None:
    position = _find(stages, key).definition.position
    return next((s for s in stages if s.definition.position == position + 1), None)


async def set_item(
    session: AsyncSession,
    project: Project,
    *,
    stage_key: str,
    item_key: str,
    done: bool,
    note: str = "",
    by: str,
) -> StageProgress:
    """Ticks or unticks one deliverable. Does not commit."""
    stage = _find(await progress(session, project), stage_key)
    if item_key not in {item["key"] for item in stage.definition.deliverables}:
        raise NotFoundError("That checklist item doesn't exist.", code="checklist_item_not_found")
    previous = stage.state.checklist.get(item_key, {})
    # Reassigned, not mutated in place, so SQLAlchemy sees the JSON change.
    stage.state.checklist = {
        **stage.state.checklist,
        item_key: {
            "done": done,
            "note": note or str(previous.get("note") or ""),
            "by": by,
            "at": utcnow().isoformat(),
        },
    }
    return stage


async def move_to(session: AsyncSession, project: Project, target_key: str) -> StageProgress:
    """Makes `target_key` the current stage. Does not commit.

    Moving forward completes every stage before the target. Moving back keeps
    later stages' work and simply reopens the earlier one.
    """
    stages = await progress(session, project)
    target = _find(stages, target_key)
    now = utcnow()
    for stage in stages:
        if stage.definition.position < target.definition.position:
            if stage.state.status != StageStatus.COMPLETED.value:
                stage.state.status = StageStatus.COMPLETED.value
                stage.state.completed_at = now
            stage.state.started_at = stage.state.started_at or now
    target.state.status = StageStatus.ACTIVE.value
    target.state.started_at = target.state.started_at or now
    target.state.completed_at = None
    project.current_stage = target.definition.key
    project.status = ProjectStatus.ACTIVE.value
    return target


async def advance(session: AsyncSession, project: Project, *, expected_from: str | None) -> Project:
    """Completes the current stage and opens the next. Commits."""
    stages = await progress(session, project)
    here = current(stages, project)
    if expected_from is not None and expected_from != here.definition.key:
        # The confirm button belonged to an older proposal.
        raise AppError("Your project has already moved on from that stage.", code="stage_changed")
    following = next_after(stages, here.definition.key)
    if following is None:
        here.state.status = StageStatus.COMPLETED.value
        here.state.completed_at = utcnow()
        project.status = ProjectStatus.COMPLETED.value
    else:
        await move_to(session, project, following.definition.key)
    project.last_activity_at = utcnow()
    await session.commit()
    return project


async def revisit(session: AsyncSession, project: Project, stage_key: str) -> Project:
    """Goes back to an earlier stage. Commits."""
    stages = await progress(session, project)
    target = _find(stages, stage_key)
    if target.definition.position >= current(stages, project).definition.position:
        raise AppError("You can only go back to an earlier stage.", code="not_an_earlier_stage")
    await move_to(session, project, stage_key)
    await session.commit()
    return project
