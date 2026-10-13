"""Breadboard geometry and wiring checks for the circuit block.

A model asked to wire a breadboard often gets a coordinate wrong: both legs of
an LED in one connected row, a lead left dangling, plus wired straight to
minus. Shown to a learner, that teaches the mistake. So the circuit a tool
call describes is checked here, electrically, before it is displayed, and any
problem is sent back to the model to fix.

The board modelled is the common half-size one: 30 columns, rows A-E above the
centre gap and F-J below, and a pair of power rails along each long edge.
"""

import re
from dataclasses import dataclass

COLUMNS = 30
TOP_ROWS = "ABCDE"
BOTTOM_ROWS = "FGHIJ"
RAILS = ("+top", "-top", "+bottom", "-bottom")

# Friendly names a model is likely to use for the rails.
_RAIL_ALIASES = {
    "+rail": "+top",
    "-rail": "-top",
    "+": "+top",
    "-": "-top",
    "vcc": "+top",
    "5v": "+top",
    "gnd": "-top",
    "ground": "-top",
}
_TIE_POINT = re.compile(r"^([A-J])(\d{1,2})$")
_RAIL = re.compile(r"^([+-](?:top|bottom))(?::(\d{1,2}))?$")


@dataclass(frozen=True)
class ComponentSpec:
    label: str
    pins: tuple[str, ...]
    # Sits beside the board and reaches it with leads (a battery pack, a servo).
    off_board: bool = False
    # Any subset of `pins` may be wired (an Arduino uses only the pins it needs).
    partial: bool = False
    # What to search Wikimedia Commons for when a learner taps the part.
    photo_query: str = ""


_ARDUINO_PINS = (
    "5V",
    "3V3",
    "GND",
    "VIN",
    *(f"D{n}" for n in range(14)),
    *(f"A{n}" for n in range(6)),
)

# To add a component: add it here, and add its drawing to the frontend's
# component library (features/circuit/library.tsx). Nothing else changes.
COMPONENTS: dict[str, ComponentSpec] = {
    "led": ComponentSpec("LED", ("anode", "cathode"), photo_query="light-emitting diode"),
    "resistor": ComponentSpec("Resistor", ("a", "b"), photo_query="resistor electronic component"),
    "button": ComponentSpec("Push button", ("a", "b"), photo_query="tactile push button switch"),
    "buzzer": ComponentSpec("Buzzer", ("positive", "negative"), photo_query="piezo buzzer"),
    "ldr": ComponentSpec("Light sensor (LDR)", ("a", "b"), photo_query="photoresistor LDR"),
    "potentiometer": ComponentSpec(
        "Potentiometer", ("a", "wiper", "b"), photo_query="potentiometer electronic component"
    ),
    "battery": ComponentSpec(
        "Battery pack", ("positive", "negative"), off_board=True, photo_query="AA battery holder"
    ),
    "arduino_uno": ComponentSpec(
        "Arduino Uno", _ARDUINO_PINS, off_board=True, partial=True, photo_query="Arduino Uno board"
    ),
    "ultrasonic": ComponentSpec(
        "Ultrasonic sensor", ("vcc", "trig", "echo", "gnd"), photo_query="HC-SR04 ultrasonic sensor"
    ),
    "servo": ComponentSpec(
        "Servo motor", ("signal", "vcc", "gnd"), off_board=True, photo_query="SG90 micro servo"
    ),
    "dc_motor": ComponentSpec(
        "DC motor", ("a", "b"), off_board=True, photo_query="small DC hobby motor"
    ),
}

_POWER_SOURCES = frozenset({"battery", "arduino_uno"})


def normalise_hole(raw: str) -> str | None:
    """The canonical name of a hole ("E12", "+top", "-bottom:7"), or None if it is not one."""
    text = raw.strip()
    lowered = text.lower().replace(" ", "")
    alias = _RAIL_ALIASES.get(lowered)
    if alias:
        return alias
    rail = _RAIL.match(lowered)
    if rail:
        column = rail.group(2)
        if column is None:
            return rail.group(1)
        return f"{rail.group(1)}:{int(column)}" if 1 <= int(column) <= COLUMNS else None
    tie = _TIE_POINT.match(text.upper().replace(" ", ""))
    if tie and 1 <= int(tie.group(2)) <= COLUMNS:
        return f"{tie.group(1)}{int(tie.group(2))}"
    return None


def strip_of(hole: str) -> str:
    """Which metal strip a (canonical) hole belongs to. Holes on one strip are connected."""
    if hole[0] in "+-":
        return hole.split(":", 1)[0]
    half = "top" if hole[0] in TOP_ROWS else "bottom"
    return f"{half}:{hole[1:]}"


def describe_strip(strip: str) -> str:
    if strip in RAILS:
        sign, side = strip[0], strip[1:]
        return f"the {'positive' if sign == '+' else 'negative'} rail ({side})"
    half, column = strip.split(":")
    rows = "A-E" if half == "top" else "F-J"
    return f"column {column} ({rows})"


@dataclass(frozen=True)
class PlacedPin:
    component_id: str
    component_type: str
    pin: str
    hole: str


@dataclass(frozen=True)
class PlacedWire:
    start: str
    end: str


class _Nets:
    """Union-find over strips: wires join strips into one electrical net."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, strip: str) -> str:
        self._parent.setdefault(strip, strip)
        while self._parent[strip] != strip:
            self._parent[strip] = self._parent[self._parent[strip]]
            strip = self._parent[strip]
        return strip

    def join(self, a: str, b: str) -> None:
        self._parent[self.find(a)] = self.find(b)


def check_wiring(pins: list[PlacedPin], wires: list[PlacedWire]) -> list[str]:
    """Problems that would stop this circuit working, in plain language.

    Assumes every hole is already canonical. An empty list means the wiring is
    sound as far as these checks go; they catch the common construction
    errors, not every possible design fault.
    """
    problems: list[str] = []

    # 1. Two legs cannot share one hole.
    occupied: dict[str, PlacedPin] = {}
    for pin in pins:
        if pin.hole[0] in "+-" and ":" not in pin.hole:
            continue  # an unnumbered rail position is "somewhere on the rail"
        other = occupied.get(pin.hole)
        if other is not None and other.component_id != pin.component_id:
            problems.append(
                f"Hole {pin.hole} is used by both {other.component_id} and {pin.component_id}. "
                "Each hole takes one leg; use another hole in the same column."
            )
        occupied[pin.hole] = pin

    # 2. A part with all its legs on one strip is bypassed: current takes the metal.
    by_component: dict[str, list[PlacedPin]] = {}
    for pin in pins:
        by_component.setdefault(pin.component_id, []).append(pin)
    for component_id, placed in by_component.items():
        strips = {strip_of(pin.hole) for pin in placed}
        if len(placed) > 1 and len(strips) == 1:
            problems.append(
                f"All the legs of {component_id} are in {describe_strip(next(iter(strips)))}, "
                "which is one connected metal strip, so current bypasses it. Put each leg in a "
                "different column."
            )

    # 3. A wire from plus to minus is a short circuit.
    nets = _Nets()
    for wire in wires:
        nets.join(strip_of(wire.start), strip_of(wire.end))
    positive = {nets.find(rail) for rail in RAILS if rail.startswith("+")}
    negative = {nets.find(rail) for rail in RAILS if rail.startswith("-")}
    if positive & negative:
        problems.append(
            "The wires connect a positive rail directly to a negative rail. That is a short "
            "circuit. Current must pass through a component on the way."
        )

    # 4. Every leg and wire end must meet something else on its strip.
    ends: dict[str, int] = {}
    for pin in pins:
        ends[strip_of(pin.hole)] = ends.get(strip_of(pin.hole), 0) + 1
    for wire in wires:
        for hole in (wire.start, wire.end):
            ends[strip_of(hole)] = ends.get(strip_of(hole), 0) + 1
    for pin in pins:
        if ends[strip_of(pin.hole)] == 1:
            problems.append(
                f"The {pin.pin} leg of {pin.component_id} in {pin.hole} is not connected to "
                f"anything: nothing else is in {describe_strip(strip_of(pin.hole))}."
            )
    for wire in wires:
        for hole in (wire.start, wire.end):
            if ends[strip_of(hole)] == 1:
                problems.append(
                    f"The wire end at {hole} is not connected to anything: nothing else is in "
                    f"{describe_strip(strip_of(hole))}."
                )

    # 5. An LED on a power source needs a resistor to limit the current.
    types = {pin.component_type for pin in pins}
    if "led" in types and types & _POWER_SOURCES and "resistor" not in types:
        problems.append(
            "There is an LED and a power source but no resistor. Without one the LED draws too "
            "much current and burns out. Add a resistor in series with the LED."
        )

    return problems
