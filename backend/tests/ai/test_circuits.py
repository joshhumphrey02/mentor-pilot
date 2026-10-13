import copy
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.blocks import CircuitBlock, dump_blocks
from app.ai.circuits import (
    COMPONENTS,
    PlacedPin,
    PlacedWire,
    check_wiring,
    normalise_hole,
    strip_of,
)
from app.ai.providers.fake import FakeProvider
from app.ai.tools.base import ToolContext
from app.ai.tools.circuit import LED_CIRCUIT, render_circuit
from app.api.v1 import media
from app.core.config import Settings
from app.services import projects
from tests.ai.test_tools import commons_page, serving
from tests.conftest import csrf, login_as, make_user
from tests.test_chat import events, final_message, send


def circuit(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(LED_CIRCUIT)
    data.update(changes)
    return data


def with_led_at(anode: str, cathode: str) -> dict[str, Any]:
    data = circuit(mistake=None)
    data["components"][2]["pins"] = {"anode": anode, "cathode": cathode}
    return data


@pytest.fixture
async def context(db: AsyncSession, settings: Settings) -> ToolContext:
    user = await make_user(db, email="builder@example.com")
    project, _ = await projects.create(db, user, "")
    return ToolContext(session=db, project=project, settings=settings, http=httpx.AsyncClient())


# --- The board ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("E12", "E12"),
        ("e12", "E12"),
        (" a1 ", "A1"),
        ("J30", "J30"),
        ("+top", "+top"),
        ("-bottom", "-bottom"),
        ("+rail", "+top"),
        ("-rail", "-top"),
        ("GND", "-top"),
        ("5V", "+top"),
        ("+top:5", "+top:5"),
        ("-bottom:07", "-bottom:7"),
        ("K5", None),
        ("A0", None),
        ("A31", None),
        ("+top:31", None),
        ("12", None),
        ("", None),
    ],
)
def test_hole_names_are_normalised(raw: str, expected: str | None) -> None:
    assert normalise_hole(raw) == expected


def test_holes_in_one_column_share_a_strip_but_not_across_the_gap() -> None:
    assert strip_of("A12") == strip_of("E12")
    assert strip_of("F12") == strip_of("J12")
    assert strip_of("E12") != strip_of("F12"), "nothing connects across the centre gap"
    assert strip_of("A12") != strip_of("A13"), "neighbouring columns are separate"
    assert strip_of("+top:3") == strip_of("+top:27") == strip_of("+top"), "a rail is one strip"
    assert strip_of("+top") != strip_of("+bottom")


def test_every_component_type_has_pins_and_a_photo_query() -> None:
    for name, spec in COMPONENTS.items():
        assert spec.pins and spec.label and spec.photo_query, name
        assert len(set(spec.pins)) == len(spec.pins), name


# --- Wiring checks -----------------------------------------------------------


def layout(data: dict[str, Any]) -> tuple[list[PlacedPin], list[PlacedWire]]:
    pins = [
        PlacedPin(c["id"], c["type"], name, normalise_hole(hole) or hole)
        for c in data["components"]
        for name, hole in c["pins"].items()
    ]
    wires = [
        PlacedWire(normalise_hole(w["from"]) or "", normalise_hole(w["to"]) or "")
        for w in data["wires"]
    ]
    return pins, wires


def test_the_reference_led_circuit_is_sound() -> None:
    assert check_wiring(*layout(LED_CIRCUIT)) == []


def test_the_reference_mistake_really_is_a_mistake() -> None:
    problems = check_wiring(*layout(LED_CIRCUIT["mistake"]))

    assert any("bypasses it" in problem and "column 10" in problem for problem in problems)


def test_both_legs_in_one_column_is_caught() -> None:
    problems = check_wiring(*layout(with_led_at("D10", "E10")))

    assert any("All the legs of led" in problem for problem in problems)


def test_a_dangling_leg_is_caught() -> None:
    problems = check_wiring(*layout(with_led_at("D10", "D20")))

    assert any("cathode leg of led in D20 is not connected" in problem for problem in problems)


def test_a_short_across_the_rails_is_caught() -> None:
    data = circuit(mistake=None)
    data["wires"].append({"from": "+top:20", "to": "-top:20", "color": "red"})

    assert any("short circuit" in problem for problem in check_wiring(*layout(data)))


def test_an_led_without_a_resistor_is_caught() -> None:
    data = circuit(mistake=None)
    data["components"] = [c for c in data["components"] if c["type"] != "resistor"]
    data["components"][1]["pins"] = {"anode": "D5", "cathode": "D11"}

    assert any("no resistor" in problem for problem in check_wiring(*layout(data)))


def test_two_parts_cannot_share_a_hole() -> None:
    data = circuit(mistake=None)
    data["components"][2]["pins"] = {"anode": "C10", "cathode": "D11"}

    assert any("Hole C10 is used by both" in problem for problem in check_wiring(*layout(data)))


def test_legs_on_opposite_sides_of_the_gap_are_not_connected() -> None:
    """E10 and F10 look adjacent but the trench separates them."""
    data = circuit(mistake=None)
    data["components"][2]["pins"] = {"anode": "F10", "cathode": "F11"}
    data["wires"][1] = {"from": "J11", "to": "-bottom:11", "color": "black"}

    problems = check_wiring(*layout(data))

    assert any("b leg of resistor in C10 is not connected" in problem for problem in problems)


# --- The tool ----------------------------------------------------------------


async def test_a_sound_circuit_is_shown_with_canonical_holes(context: ToolContext) -> None:
    data = circuit()
    data["components"][2]["pins"] = {"anode": "d10", "cathode": " D11 "}
    data["wires"][1] = {"from": "a11", "to": "-rail", "color": "black"}

    outcome = await render_circuit.call(context, data)

    assert not outcome.is_error, outcome.result
    block = outcome.blocks[0]
    assert isinstance(block, CircuitBlock)
    assert block.components[2].pins == {"anode": "D10", "cathode": "D11"}
    assert (block.wires[1].from_, block.wires[1].to) == ("A11", "-top")
    assert block.mistake is not None and block.mistake.highlight == ["D10", "E10"]
    assert "Do/Don't" in outcome.result


async def test_wires_are_stored_with_from_and_to(context: ToolContext) -> None:
    outcome = await render_circuit.call(context, circuit())

    stored = dump_blocks(outcome.blocks)[0]
    assert stored["wires"][0] == {
        "from": "+top:5",
        "to": "A5",
        "color": "red",
        "note": "Positive rail to the resistor.",
    }


async def test_a_circuit_that_would_not_work_is_sent_back_with_the_rules(
    context: ToolContext,
) -> None:
    outcome = await render_circuit.call(context, with_led_at("D10", "E10"))

    assert outcome.is_error and outcome.blocks == []
    assert "would not work as wired" in outcome.result
    assert "All the legs of led are in column 10" in outcome.result
    assert "Breadboard rules" in outcome.result and "call the tool again" in outcome.result


async def test_holes_that_do_not_exist_are_reported(context: ToolContext) -> None:
    outcome = await render_circuit.call(context, with_led_at("Z99", "D11"))

    assert outcome.is_error and "'Z99' (led.anode) is not a hole on the board" in outcome.result


async def test_wrong_and_missing_pin_names_are_reported(context: ToolContext) -> None:
    data = circuit(mistake=None)
    data["components"][2]["pins"] = {"plus": "D10", "cathode": "D11"}

    outcome = await render_circuit.call(context, data)

    assert outcome.is_error
    assert "has no pin called plus" in outcome.result
    assert "Its pins are: anode, cathode" in outcome.result
    assert "is missing: anode" in outcome.result


async def test_an_arduino_only_needs_the_pins_it_uses(context: ToolContext) -> None:
    data = {
        "title": "Blink",
        "components": [
            {"id": "uno", "type": "arduino_uno", "pins": {"D13": "A5", "GND": "-top"}},
            {"id": "r1", "type": "resistor", "pins": {"a": "C5", "b": "C10"}},
            {"id": "led1", "type": "led", "pins": {"anode": "D10", "cathode": "D11"}},
        ],
        "wires": [{"from": "A11", "to": "-top:11", "color": "black"}],
    }

    outcome = await render_circuit.call(context, data)

    assert not outcome.is_error, outcome.result


async def test_an_undrawable_mistake_is_reported(context: ToolContext) -> None:
    data = circuit()
    data["mistake"]["components"][2]["pins"] = {"anode": "D10", "cathode": "Q1"}

    outcome = await render_circuit.call(context, data)

    assert outcome.is_error and "'mistake' version cannot be drawn" in outcome.result


async def test_duplicate_ids_are_reported(context: ToolContext) -> None:
    data = circuit(mistake=None)
    data["components"][2]["id"] = "resistor"

    outcome = await render_circuit.call(context, data)

    assert outcome.is_error and "used twice" in outcome.result


# --- In a conversation -------------------------------------------------------


async def test_asking_how_to_connect_an_led_produces_a_breadboard(
    client: AsyncClient, db: AsyncSession, fake_ai: FakeProvider
) -> None:
    await make_user(db, email="learner@example.com")
    await login_as(client, "learner@example.com")
    project = (await client.post("/api/v1/projects", json={}, headers=csrf(client))).json()

    response = await send(
        client, project["latest_conversation"]["id"], "How do I connect an LED on a breadboard?"
    )

    message = final_message(response)
    kinds = [block["type"] for block in message["blocks"]]
    assert kinds == ["markdown", "circuit", "markdown", "callout", "suggested_replies"]
    board = message["blocks"][1]
    assert board["mistake"]["title"] == "Both LED legs in one column"
    assert board["wires"][0]["from"] == "+top:5"
    streamed = next(
        data["block"]
        for name, data in events(response)
        if name == "block_complete" and data["block"]["type"] == "circuit"
    )
    assert streamed["wires"][0]["from"] == "+top:5", "the stream uses the same field names"
    status = [data["text"] for name, data in events(response) if name == "tool_status"]
    assert status == ["Building “Lighting an LED” on the breadboard…"]


# --- Component photos --------------------------------------------------------


@pytest.fixture
async def signed_in_learner(client: AsyncClient, db: AsyncSession) -> AsyncClient:
    await make_user(db, email="learner@example.com")
    await login_as(client, "learner@example.com")
    media._photo_cache.clear()
    return client


async def test_component_photo_is_fetched_once_and_cached(
    signed_in_learner: AsyncClient, app: FastAPI
) -> None:
    seen: list[httpx.Request] = []
    app.state.chat.http = serving({"query": {"pages": {"1": commons_page(1, "Red_LED")}}}, seen)

    first = await signed_in_learner.get("/api/v1/media/component-photo/led")
    second = await signed_in_learner.get("/api/v1/media/component-photo/led")

    assert first.status_code == 200
    assert first.json()["label"] == "LED"
    assert first.json()["image"]["title"] == "Red LED"
    assert first.json()["image"]["license"] == "CC BY-SA 4.0"
    assert second.json() == first.json()
    assert len(seen) == 1
    assert "light-emitting diode" in str(seen[0].url.params["gsrsearch"])


async def test_a_failed_photo_lookup_is_not_cached(
    signed_in_learner: AsyncClient, app: FastAPI
) -> None:
    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    app.state.chat.http = httpx.AsyncClient(transport=httpx.MockTransport(down))
    missing = await signed_in_learner.get("/api/v1/media/component-photo/resistor")
    assert missing.status_code == 200 and missing.json()["image"] is None

    app.state.chat.http = serving({"query": {"pages": {"1": commons_page(1, "Resistor")}}})
    found = await signed_in_learner.get("/api/v1/media/component-photo/resistor")
    assert found.json()["image"]["title"] == "Resistor"


async def test_unknown_component_is_404(signed_in_learner: AsyncClient) -> None:
    assert (
        await signed_in_learner.get("/api/v1/media/component-photo/flux_capacitor")
    ).status_code == 404


async def test_component_photos_need_login(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/media/component-photo/led")).status_code == 401
