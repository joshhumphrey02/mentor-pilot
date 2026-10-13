from typing import Any

from app.ai.blocks import CircuitBlock, CircuitComponent, CircuitWire
from app.ai.circuits import (
    COMPONENTS,
    PlacedPin,
    PlacedWire,
    check_wiring,
    normalise_hole,
)
from app.ai.tools.base import Tool, ToolContext, ToolOutcome

RULES = (
    "Breadboard rules: columns are numbered 1-30. Rows A-E are above the centre gap and rows "
    "F-J below it. The five holes of one column on one side of the gap are joined by a metal "
    "strip (A12, B12, C12, D12 and E12 are all connected; F12-J12 are a separate strip). "
    "Nothing connects across the gap or between columns. The rails '+top', '-top', '+bottom' "
    "and '-bottom' each run the whole length of the board. So a part must have each leg in a "
    "different column, and two things are connected by sharing a column or by a wire."
)


def _normalise_layout(
    components: list[CircuitComponent], wires: list[CircuitWire], highlights: list[str]
) -> tuple[list[CircuitComponent], list[CircuitWire], list[str], list[str]]:
    """Canonical hole names throughout, plus any structural problems found."""
    problems: list[str] = []
    seen: set[str] = set()
    fixed_components: list[CircuitComponent] = []
    for component in components:
        spec = COMPONENTS[component.type]
        if component.id in seen:
            problems.append(f"The id '{component.id}' is used twice. Ids must be unique.")
        seen.add(component.id)

        unknown = sorted(set(component.pins) - set(spec.pins))
        missing = sorted(set(spec.pins) - set(component.pins))
        if unknown:
            problems.append(
                f"{component.id} ({component.type}) has no pin called {', '.join(unknown)}. "
                f"Its pins are: {', '.join(spec.pins)}."
            )
        if missing and not spec.partial:
            problems.append(f"{component.id} ({component.type}) is missing: {', '.join(missing)}.")

        pins: dict[str, str] = {}
        for name, raw in component.pins.items():
            hole = normalise_hole(raw)
            if hole is None:
                problems.append(f"'{raw}' ({component.id}.{name}) is not a hole on the board.")
            else:
                pins[name] = hole
        fixed_components.append(component.model_copy(update={"pins": pins}))

    fixed_wires: list[CircuitWire] = []
    for wire in wires:
        start, end = normalise_hole(wire.from_), normalise_hole(wire.to)
        for raw, hole in ((wire.from_, start), (wire.to, end)):
            if hole is None:
                problems.append(f"'{raw}' (a wire end) is not a hole on the board.")
        if start is not None and end is not None:
            fixed_wires.append(wire.model_copy(update={"from_": start, "to": end}))

    fixed_highlights = [hole for raw in highlights if (hole := normalise_hole(raw)) is not None]
    return fixed_components, fixed_wires, fixed_highlights, problems


def _electrical_problems(components: list[CircuitComponent], wires: list[CircuitWire]) -> list[str]:
    pins = [
        PlacedPin(component.id, component.type, name, hole)
        for component in components
        for name, hole in component.pins.items()
    ]
    return check_wiring(pins, [PlacedWire(wire.from_, wire.to) for wire in wires])


async def _render(_context: ToolContext, args: CircuitBlock) -> ToolOutcome:
    components, wires, highlight, problems = _normalise_layout(
        args.components, args.wires, args.highlight
    )
    if not problems:
        # Only a structurally valid layout can be checked electrically.
        problems = _electrical_problems(components, wires)
    if problems:
        return ToolOutcome(
            result="The circuit was not shown because it would not work as wired:\n- "
            + "\n- ".join(problems[:8])
            + f"\n\n{RULES}\n\nFix the wiring and call the tool again.",
            is_error=True,
        )

    update: dict[str, Any] = {
        "components": components,
        "wires": wires,
        "highlight": highlight,
        "annotations": [
            note.model_copy(update={"at": hole})
            for note in args.annotations
            if (hole := normalise_hole(note.at)) is not None
        ],
    }
    if args.mistake is not None:
        # The mistake is meant to be wrong, so it is only checked for being
        # drawable: real holes and real pin names.
        bad_components, bad_wires, bad_highlight, bad_problems = _normalise_layout(
            args.mistake.components, args.mistake.wires, args.mistake.highlight
        )
        if bad_problems:
            return ToolOutcome(
                result="The 'mistake' version cannot be drawn:\n- "
                + "\n- ".join(bad_problems[:8])
                + "\n\nFix it and call the tool again.",
                is_error=True,
            )
        update["mistake"] = args.mistake.model_copy(
            update={"components": bad_components, "wires": bad_wires, "highlight": bad_highlight}
        )

    extras = " It includes a Do/Don't switch showing the common mistake." if args.mistake else ""
    return ToolOutcome(
        result="The learner can now see an interactive breadboard of this circuit. They can "
        "reveal the metal strips inside the board, step through the build one part at a time, "
        f"and tap any part to learn about it.{extras} Do not list the connections again in "
        "text; ask them to try the step-through or the reveal.",
        blocks=[args.model_copy(update=update)],
        record=f"interactive breadboard: {args.title}",
    )


render_circuit = Tool(
    name="render_circuit",
    description=(
        "Show an interactive breadboard that the learner can explore: they can reveal the "
        "metal strips inside the board, step through the build one part at a time, and switch "
        "between the correct wiring and a common mistake. Use it whenever a learner asks how "
        "to connect, wire or build any circuit, or does not understand how a breadboard "
        "works. It teaches far better than a description.\n\n"
        f"{RULES}\n\n"
        "List components and wires in the order a beginner should place them. Give LEDs a "
        "series resistor. Include a `mistake` whenever there is a classic one for this circuit "
        "(both legs in one column, LED reversed, resistor left out, a short across the rails, "
        "a part bridging nothing): seeing the wrong version beside the right one is what makes "
        "it stick. Low-voltage battery or Arduino circuits only, never mains.\n\n"
        "Your wiring is checked before it is shown. If it would not work you will be told "
        "why, so you can correct it."
    ),
    args=CircuitBlock,
    run=_render,
    status=lambda args: f"Building “{args.title}” on the breadboard…",
)

# A known-good circuit: used by the demo provider, the landing page and tests.
LED_CIRCUIT: dict[str, Any] = {
    "title": "Lighting an LED",
    "components": [
        {
            "id": "battery",
            "type": "battery",
            "pins": {"positive": "+top", "negative": "-top"},
            "props": {"value": "3V"},
            "note": "Two AA batteries give 3 volts: safe to touch and enough for an LED.",
        },
        {
            "id": "resistor",
            "type": "resistor",
            "pins": {"a": "C5", "b": "C10"},
            "props": {"value": "100Ω"},
            "note": "The resistor limits the current so the LED does not burn out.",
        },
        {
            "id": "led",
            "type": "led",
            "pins": {"anode": "D10", "cathode": "D11"},
            "props": {"color": "red"},
            "note": "The long leg (anode) goes towards positive. Each leg has its own column.",
        },
    ],
    "wires": [
        {"from": "+top:5", "to": "A5", "color": "red", "note": "Positive rail to the resistor."},
        {"from": "A11", "to": "-top:11", "color": "black", "note": "Back to the negative rail."},
    ],
    "highlight": [],
    "annotations": [{"at": "D10", "text": "Long leg (anode) on the positive side"}],
    "mistake": {
        "title": "Both LED legs in one column",
        "explanation": "Column 10 is a single metal strip under the board, so both legs are "
        "joined together. The current takes the easy path through the strip and skips the "
        "LED, which stays dark. Reveal the inside of the board to see the strip.",
        "components": [
            {
                "id": "battery",
                "type": "battery",
                "pins": {"positive": "+top", "negative": "-top"},
                "props": {"value": "3V"},
            },
            {
                "id": "resistor",
                "type": "resistor",
                "pins": {"a": "C5", "b": "C10"},
                "props": {"value": "100Ω"},
            },
            {
                "id": "led",
                "type": "led",
                "pins": {"anode": "D10", "cathode": "E10"},
                "props": {"color": "red"},
            },
        ],
        "wires": [
            {"from": "+top:5", "to": "A5", "color": "red"},
            {"from": "A10", "to": "-top:10", "color": "black"},
        ],
        "highlight": ["D10", "E10"],
    },
}
