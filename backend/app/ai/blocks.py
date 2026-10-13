"""Render blocks: the typed pieces an assistant message is made of.

A message is an ordered list of blocks rather than one markdown string, so the
UI can render each kind with its own component. These schemas are the single
definition: they validate what is stored and, through OpenAPI, generate the
TypeScript types the frontend renders from.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

CalloutVariant = Literal["tip", "safety", "judge_insight", "common_mistake"]


class MarkdownBlock(BaseModel):
    type: Literal["markdown"] = "markdown"
    text: str


class CalloutBlock(BaseModel):
    type: Literal["callout"] = "callout"
    variant: CalloutVariant = "tip"
    text: str


class SuggestedRepliesBlock(BaseModel):
    type: Literal["suggested_replies"] = "suggested_replies"
    replies: list[Annotated[str, Field(max_length=120)]] = Field(max_length=4)


class ErrorBlock(BaseModel):
    """A friendly failure notice, shown in place of an answer."""

    type: Literal["error"] = "error"
    code: str
    text: str
    retryable: bool = False


# --- Blocks produced by tools ---------------------------------------------------
# The model fills these in through tool calls. Field descriptions are part of
# the tool schema the model sees, so they are written for it.

SafetyLevel = Literal["low", "medium", "high"]
ShortStr = Annotated[str, Field(max_length=200)]


class IdeaCard(BaseModel):
    title: Annotated[str, Field(max_length=80, description="A short, specific project title.")]
    problem: Annotated[
        str, Field(max_length=240, description="The real-world problem this project addresses.")
    ]
    field: Annotated[
        str,
        Field(
            max_length=60,
            description="The science or engineering field, e.g. 'Environmental science'.",
        ),
    ]
    difficulty: Annotated[
        int, Field(ge=1, le=5, description="1 = very easy for this learner, 5 = very hard.")
    ]
    cost_min_zar: Annotated[int, Field(ge=0, description="Lowest realistic total cost in rand.")]
    cost_max_zar: Annotated[int, Field(ge=0, description="Highest realistic total cost in rand.")]
    materials: Annotated[
        list[ShortStr], Field(max_length=10, description="The main materials or equipment needed.")
    ]
    time_needed: Annotated[
        str, Field(max_length=60, description="Roughly how long it takes, e.g. '3 to 4 weeks'.")
    ]
    why_judges_like_it: Annotated[
        str, Field(max_length=240, description="What would impress an expo judge about this.")
    ]
    safety_level: Annotated[
        SafetyLevel,
        Field(
            description="low = no real risk; medium = needs care; high = needs adult supervision."
        ),
    ]
    safety_note: Annotated[
        str, Field(max_length=200, description="The main risk and how to manage it. Empty if none.")
    ] = ""


class IdeaCardsBlock(BaseModel):
    type: Literal["idea_cards"] = "idea_cards"
    ideas: Annotated[list[IdeaCard], Field(min_length=1, max_length=6)]


class ComparisonRow(BaseModel):
    criterion: Annotated[
        str, Field(max_length=60, description="What is being compared, e.g. 'Cost'.")
    ]
    values: Annotated[
        list[ShortStr],
        Field(description="One short value per option, in the same order as `options`."),
    ]


class ComparisonTableBlock(BaseModel):
    type: Literal["comparison_table"] = "comparison_table"
    title: Annotated[str, Field(max_length=100)] = ""
    options: Annotated[
        list[Annotated[str, Field(max_length=80)]],
        Field(
            min_length=2, max_length=4, description="The things being compared (column headings)."
        ),
    ]
    rows: Annotated[list[ComparisonRow], Field(min_length=1, max_length=10)]


class DiagramBlock(BaseModel):
    type: Literal["diagram"] = "diagram"
    title: Annotated[str, Field(max_length=100)]
    mermaid: Annotated[
        str,
        Field(
            max_length=4000,
            description="Mermaid diagram source, e.g. starting with 'flowchart TD'. "
            "Keep node labels short. Do not wrap it in a code fence.",
        ),
    ]
    caption: Annotated[str, Field(max_length=240)] = ""


class GalleryImage(BaseModel):
    url: str
    thumbnail_url: str
    title: str
    # Where the image came from, for credit and so learners can cite it.
    source_url: str
    author: str = ""
    license: str = ""
    width: int | None = None
    height: int | None = None


class ImageGalleryBlock(BaseModel):
    type: Literal["image_gallery"] = "image_gallery"
    query: str
    images: list[GalleryImage]


class VideoCard(BaseModel):
    video_id: str
    title: str
    channel: str = ""
    thumbnail_url: str = ""


class VideoCardsBlock(BaseModel):
    type: Literal["video_cards"] = "video_cards"
    query: str
    videos: list[VideoCard]


class ChartPoint(BaseModel):
    x: Annotated[float | str, Field(description="A number, or a category label for bar charts.")]
    y: float


class ChartSeries(BaseModel):
    name: Annotated[str, Field(max_length=60)]
    points: Annotated[list[ChartPoint], Field(min_length=1, max_length=200)]


class ChartBlock(BaseModel):
    type: Literal["chart"] = "chart"
    chart_type: Annotated[
        Literal["line", "bar", "scatter"],
        Field(
            description="line: change over a continuous quantity. bar: comparing categories. "
            "scatter: the relationship between two measured quantities."
        ),
    ]
    title: Annotated[str, Field(max_length=100)]
    x_label: Annotated[str, Field(max_length=60, description="Axis label, with units.")]
    y_label: Annotated[str, Field(max_length=60, description="Axis label, with units.")]
    series: Annotated[list[ChartSeries], Field(min_length=1, max_length=6)]


class ChecklistBlock(BaseModel):
    """Points at a stage's checklist. The UI shows its live state and lets the
    learner tick items, so the block stores no copy that could go stale."""

    type: Literal["checklist"] = "checklist"
    stage_key: str


class DataTableTemplate(BaseModel):
    columns: Annotated[
        list[Annotated[str, Field(max_length=60)]],
        Field(min_length=2, max_length=8, description="Column headings, with units."),
    ]
    rows: Annotated[
        int, Field(ge=1, le=30, description="How many blank rows (usually one per trial).")
    ]


class ExperimentPlanBlock(BaseModel):
    type: Literal["experiment_plan"] = "experiment_plan"
    title: Annotated[str, Field(max_length=100)]
    independent_variable: Annotated[
        str, Field(max_length=200, description="The one thing the learner will change on purpose.")
    ]
    dependent_variable: Annotated[
        str, Field(max_length=200, description="What they will measure, and with what.")
    ]
    controlled_variables: Annotated[
        list[ShortStr], Field(min_length=1, max_length=8, description="What must stay the same.")
    ]
    trials: Annotated[int, Field(ge=1, le=30, description="How many times each test is repeated.")]
    data_table: DataTableTemplate


class BomItem(BaseModel):
    name: Annotated[str, Field(max_length=100)]
    quantity: Annotated[int, Field(ge=1, le=1000)]
    unit_price_zar: Annotated[
        float, Field(ge=0, description="Estimated price each, in rand. 0 if recycled or free.")
    ]
    where_to_get: Annotated[
        str, Field(max_length=120, description="A kind of shop or source, e.g. 'hardware store'.")
    ] = ""
    substitute: Annotated[
        str,
        Field(max_length=160, description="A cheaper or recycled alternative, if there is one."),
    ] = ""


class BomTableBlock(BaseModel):
    type: Literal["bom_table"] = "bom_table"
    title: Annotated[str, Field(max_length=100)] = "Bill of materials"
    items: Annotated[list[BomItem], Field(min_length=1, max_length=30)]
    # Worked out by the server, so the sum is always right.
    total_zar: float = 0


class QuizQuestion(BaseModel):
    question: Annotated[str, Field(max_length=300)]
    options: Annotated[list[ShortStr], Field(min_length=2, max_length=4)]
    correct_index: Annotated[
        int, Field(ge=0, le=3, description="Index of the right option, from 0.")
    ]
    explanation: Annotated[
        str, Field(max_length=400, description="Why that answer is right, in plain language.")
    ]


class QuizBlock(BaseModel):
    type: Literal["quiz"] = "quiz"
    title: Annotated[str, Field(max_length=100)] = "Quick check"
    questions: Annotated[list[QuizQuestion], Field(min_length=1, max_length=5)]


ComponentType = Literal[
    "led",
    "resistor",
    "button",
    "buzzer",
    "ldr",
    "potentiometer",
    "battery",
    "arduino_uno",
    "ultrasonic",
    "servo",
    "dc_motor",
]
Hole = Annotated[
    str,
    Field(
        max_length=12,
        description="A breadboard hole: a row letter A-J and a column 1-30, e.g. 'E12'. Or a "
        "power rail: '+top', '-top', '+bottom' or '-bottom'.",
    ),
]


class CircuitComponent(BaseModel):
    id: Annotated[str, Field(max_length=24, description="A short unique id, e.g. 'led1'.")]
    type: ComponentType
    pins: Annotated[
        dict[str, Hole],
        Field(
            description="Where each leg goes, by pin name. led: anode, cathode. resistor, "
            "button, ldr, dc_motor: a, b. buzzer, battery: positive, negative. potentiometer: "
            "a, wiper, b. ultrasonic: vcc, trig, echo, gnd. servo: signal, vcc, gnd. "
            "arduino_uno: only the pins used, from 5V, 3V3, GND, D0-D13, A0-A5."
        ),
    ]
    props: Annotated[
        dict[str, str],
        Field(
            description="Optional details: 'color' for an LED (red, green, yellow, blue, "
            "white), 'value' for a resistor (e.g. '220Ω') or battery (e.g. '3V')."
        ),
    ] = Field(default_factory=dict)
    note: Annotated[
        str,
        Field(
            max_length=160,
            description="One short teaching point shown when this part is placed in "
            "step-through, e.g. 'The long leg is the anode'.",
        ),
    ] = ""


class CircuitWire(BaseModel):
    from_: Annotated[Hole, Field(alias="from")]
    to: Hole
    color: Annotated[
        str, Field(max_length=16, description="red for positive, black for negative, else any.")
    ] = "blue"
    note: Annotated[str, Field(max_length=160)] = ""

    model_config = {"populate_by_name": True}


class CircuitAnnotation(BaseModel):
    at: Hole
    text: Annotated[str, Field(max_length=120)]


class CircuitMistake(BaseModel):
    """The "Don't" version: the same circuit built with one common mistake."""

    title: Annotated[
        str, Field(max_length=80, description="The mistake in a few words, e.g. 'LED backwards'.")
    ]
    explanation: Annotated[
        str,
        Field(max_length=400, description="What goes wrong and why, in plain language."),
    ]
    components: Annotated[list[CircuitComponent], Field(min_length=1, max_length=12)]
    wires: Annotated[list[CircuitWire], Field(max_length=24)] = Field(default_factory=list)
    highlight: Annotated[
        list[Hole], Field(max_length=8, description="The holes where the mistake is.")
    ] = Field(default_factory=list)


class CircuitBlock(BaseModel):
    type: Literal["circuit"] = "circuit"
    title: Annotated[str, Field(max_length=100)]
    components: Annotated[
        list[CircuitComponent],
        Field(min_length=1, max_length=12, description="In the order they should be placed."),
    ]
    wires: Annotated[
        list[CircuitWire], Field(max_length=24, description="In the order they should be added.")
    ] = Field(default_factory=list)
    highlight: Annotated[list[Hole], Field(max_length=8)] = Field(default_factory=list)
    annotations: Annotated[list[CircuitAnnotation], Field(max_length=6)] = Field(
        default_factory=list
    )
    mistake: CircuitMistake | None = None


class StageTransitionBlock(BaseModel):
    """A proposal to move on. The learner confirms it in the UI; nothing changes
    until they do. Once the project is at `to_stage` the card becomes a celebration."""

    type: Literal["stage_transition"] = "stage_transition"
    from_stage: str
    to_stage: str
    from_title: str
    to_title: str
    summary: str


Block = Annotated[
    MarkdownBlock
    | CalloutBlock
    | SuggestedRepliesBlock
    | ErrorBlock
    | IdeaCardsBlock
    | ComparisonTableBlock
    | DiagramBlock
    | ImageGalleryBlock
    | VideoCardsBlock
    | ChartBlock
    | ChecklistBlock
    | ExperimentPlanBlock
    | BomTableBlock
    | QuizBlock
    | CircuitBlock
    | StageTransitionBlock,
    Field(discriminator="type"),
]

BLOCK_LIST: TypeAdapter[list[Block]] = TypeAdapter(list[Block])


def dump_blocks(blocks: list[Block]) -> list[dict[str, Any]]:
    # by_alias so a wire is stored as {"from": ..., "to": ...}, as the UI reads it.
    return [block.model_dump(mode="json", by_alias=True) for block in blocks]


def load_blocks(raw: list[dict[str, Any]]) -> list[Block]:
    return BLOCK_LIST.validate_python(raw)


_MACHINE_KEYS = frozenset(
    {"type", "stage_key", "from_stage", "to_stage", "video_id", "id", "pins", "from", "to", "at"}
)


def block_strings(block: Block) -> list[str]:
    """Every piece of text in a block, for moderation and search."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            found.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                # Skip machine values: type tags, keys, ids and links.
                if key not in _MACHINE_KEYS and (not key.endswith("url")):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(block.model_dump(mode="json", by_alias=True))
    return found
