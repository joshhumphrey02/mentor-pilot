"""Every tool the mentor can call."""

from typing import Any

from app.ai.tools.base import Tool
from app.ai.tools.circuit import render_circuit
from app.ai.tools.ideas import compare_ideas, propose_project_ideas, select_idea
from app.ai.tools.media import search_images, search_videos
from app.ai.tools.progress import advance_stage, revisit_stage, update_checklist
from app.ai.tools.visuals import (
    build_bill_of_materials,
    create_experiment_plan,
    quiz_me,
    render_chart,
    render_diagram,
)
from app.core.config import Settings

ALL_TOOLS: tuple[Tool[Any], ...] = (
    propose_project_ideas,
    compare_ideas,
    select_idea,
    update_checklist,
    advance_stage,
    revisit_stage,
    render_diagram,
    render_circuit,
    render_chart,
    search_images,
    search_videos,
    build_bill_of_materials,
    create_experiment_plan,
    quiz_me,
)

# How many times the model may call tools and continue within one turn. A cap
# keeps a confused model from looping, and keeps cost per turn predictable.
MAX_TOOL_ROUNDS = 5


def available_tools(settings: Settings) -> dict[str, Tool[Any]]:
    return {tool.name: tool for tool in ALL_TOOLS if tool.available(settings)}
