"""The project summary PDF a learner takes to a teacher or mentor."""

from datetime import datetime
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.services import pathway, workspace

# The built-in PDF fonts cover Latin-1 only. Common characters outside it are
# swapped for plain equivalents rather than printed as "?".
_REPLACEMENTS = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "−": "-",
    "…": "...",
    "→": "->",
    "Ω": "ohm",
    "Ω": "ohm",
    "×": "x",
    "✓": "x",
    "•": "-",
}
INK = (28, 32, 51)
MUTED = (98, 104, 122)
BRAND = (59, 67, 214)


def _latin(text: Any) -> str:
    cleaned = str(text if text is not None else "")
    for source, target in _REPLACEMENTS.items():
        cleaned = cleaned.replace(source, target)
    return cleaned.encode("latin-1", "replace").decode("latin-1")


class _Summary(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", size=8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Mentor Pilot project summary - page {self.page_no()}", align="C")

    def heading(self, text: str) -> None:
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*BRAND)
        self.cell(0, 8, _latin(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def body(self, text: str, *, bold: bool = False, muted: bool = False) -> None:
        self.set_font("Helvetica", "B" if bold else "", 10.5)
        self.set_text_color(*(MUTED if muted else INK))
        self.multi_cell(0, 5.4, _latin(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*INK)

    def field(self, label: str, value: Any) -> None:
        if value in (None, "", []):
            return
        self.set_font("Helvetica", "B", 10.5)
        self.write(5.4, _latin(f"{label}: "))
        self.set_font("Helvetica", "", 10.5)
        self.multi_cell(0, 5.4, _latin(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def grid(self, header: list[str], rows: list[list[str]]) -> None:
        if not header:
            return
        self.set_font("Helvetica", size=9.5)
        with self.table(
            text_align="LEFT", line_height=5.4, borders_layout="HORIZONTAL_LINES"
        ) as table:
            heading = table.row()
            for cell in header:
                heading.cell(_latin(cell))
            for row in rows:
                line = table.row()
                for cell in row:
                    line.cell(_latin(cell))
        self.ln(2)


async def build_project_pdf(session: AsyncSession, user: User, project: Project) -> bytes:
    stages = await pathway.progress(session, project)
    logbook = list(reversed(await workspace.list_logbook(session, project)))
    datasets = await workspace.list_datasets(session, project)
    pins = await workspace.list_pins(session, project)
    here = pathway.current(stages, project)

    pdf = _Summary(format="A4")
    pdf.set_title(_latin(project.title))
    pdf.set_author(_latin(user.full_name))
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(18, 16, 18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 9, _latin(project.title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    profile = user.student_profile
    school = profile.school.name if profile and profile.school else ""
    grade = f"Grade {profile.grade}" if profile and profile.grade else ""
    pdf.body(" | ".join(part for part in (user.full_name, school, grade) if part), muted=True)
    pdf.body(
        f"Stage {here.definition.position} of {len(stages)}: {here.definition.title}"
        f" | Exported {datetime.now().strftime('%d %B %Y')}",
        muted=True,
    )

    idea: dict[str, Any] = project.idea or {}
    if idea:
        pdf.heading("The idea")
        pdf.field("Problem", idea.get("problem"))
        pdf.field("Field", idea.get("field"))
        pdf.field("Why I chose it", idea.get("reason"))
        pdf.field("Materials", ", ".join(idea.get("materials") or []))
        pdf.field("Safety", idea.get("safety_note"))

    pdf.heading("Progress")
    for stage in stages:
        if stage.state.status == "locked":
            continue
        pdf.body(f"{stage.definition.position}. {stage.definition.title}", bold=True)
        for item in stage.items:
            mark = "[x]" if item["done"] else "[ ]"
            note = f" - {item['note']}" if item["note"] else ""
            pdf.body(f"   {mark} {item['label']}{note}")

    for pin in pins:
        block = pin.block
        if block.get("type") == "bom_table":
            pdf.heading(str(block.get("title") or "Bill of materials"))
            pdf.grid(
                ["Item", "Qty", "Each (R)", "Cheaper option"],
                [
                    [
                        str(item.get("name", "")),
                        str(item.get("quantity", "")),
                        f"{float(item.get('unit_price_zar') or 0):.2f}",
                        str(item.get("substitute", "")),
                    ]
                    for item in block.get("items", [])
                ],
            )
            pdf.body(f"Estimated total: R{float(block.get('total_zar') or 0):.2f}", bold=True)
        elif block.get("type") == "experiment_plan":
            pdf.heading(str(block.get("title") or "Experiment plan"))
            pdf.field("What I change", block.get("independent_variable"))
            pdf.field("What I measure", block.get("dependent_variable"))
            pdf.field("What I keep the same", "; ".join(block.get("controlled_variables") or []))
            pdf.field("Trials", block.get("trials"))

    for dataset in datasets:
        pdf.heading(f"Data: {dataset.title}")
        pdf.grid(dataset.columns, dataset.rows)

    other = [pin for pin in pins if pin.block.get("type") not in ("bom_table", "experiment_plan")]
    if other:
        pdf.heading("Also saved in the app")
        for pin in other:
            pdf.body(f"- {pin.title}")

    if logbook:
        pdf.heading("Logbook")
        for entry in logbook:
            pdf.body(entry.created_at.strftime("%d %B %Y, %H:%M"), bold=True)
            pdf.body(entry.text)
            pdf.ln(1.5)

    return bytes(pdf.output())
