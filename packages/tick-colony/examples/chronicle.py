"""Chronicle demo -- 10,000-tick colony simulation with seasons and world events.

Uses tick-event for a 4-season cycle and probabilistic world events (cold snaps,
heat waves, harvests, raids, plagues).  Uses tick-atlas for terrain (grass, forest,
water) and tick-spatial pathfinding for incremental movement.  After the simulation,
walks the EventLog to produce a narrative "chronicle" grouped by year and season.

Optionally enables 4 LLM agents (Steward, Builder, Warden, Narrator) that observe
colony state, issue directives influencing colonist behavior via FSM guards, and
produce a richer narrative.  Supports MockClient (default) and real LLM endpoint.

Run:
    uv run --package tick-colony python -m examples.chronicle [OPTIONS]

Options:
    --mock       Use MockClient (default)
    --llm        Use real LLM endpoint (Anthropic-compatible)
    --llm-url    LLM endpoint URL (default: http://localhost:1234)
    --model      Model name for real LLM
    --api-key    Bearer token / API key for LLM endpoint
    --no-llm     Run without LLM (original behavior)
    --seed       RNG seed (default: 42)
    --ticks      Total ticks (default: 10000)
"""
from __future__ import annotations

import argparse
import json
import random as _random_mod
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from tick import Engine, World
from tick.types import TickContext
from tick_colony import (
    Pos2D, NeedSet, NeedHelper, StatBlock, Modifiers, Inventory, InventoryHelper, Lifecycle,
    EventLog, Event, add_modifier,
    register_colony_components, effective,
    Grid2D, pathfind, make_spatial_cleanup_system, Timer, make_timer_system,
    FSM, FSMGuards, make_fsm_system, SignalBus,
    make_need_decay_system, make_modifier_tick_system, make_lifecycle_system,
    EventScheduler, EventGuards, EventDef, CycleDef, make_event_system,
    LLMAgent, LLMConfig, LLMManager, MockClient, Blackboard, make_llm_system,
    make_resource_context, make_population_context, make_event_context, make_colony_context,
    make_directive_parser, DirectiveHandler,
    PressureThresholds, make_pressure_system,
)
from tick_spatial import Coord
from tick_atlas import CellDef, CellMap

# -- Game-specific components -------------------------------------------------

@dataclass
class Colonist:
    name: str

@dataclass
class Destination:
    coord: Coord

# -- Constants ----------------------------------------------------------------
GRID_W, GRID_H = 20, 20
NAMES = ["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"]
EXTRA_NAMES = ["Ingrid", "Jarl", "Kara", "Leif", "Mira", "Nils", "Olga", "Per",
               "Runa", "Sven", "Tova", "Ulf", "Vera", "Wren", "Ylva", "Zeke"]
STOCKPILE: Coord = (10, 10)
TICKS_SEASON, TICKS_YEAR, TOTAL = 500, 2000, 10_000
SEASONS = ["spring", "summer", "autumn", "winter"]
W_EVENTS = ("cold_snap", "heat_wave", "bountiful_harvest", "raid", "plague")
MAX_POP = 20
BIRTH_FOOD_COST = 5
BIRTH_FOOD_MIN = 6
BIRTH_CHANCE = 0.015
FORAGE_TICKS = 8
REST_TICKS = 4
BUILD_TICKS = 10

# -- Terrain ------------------------------------------------------------------
GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0, properties={"food": True})
WATER = CellDef(name="water", passable=False)

def _setup_terrain(seed: int) -> None:
    rng = _random_mod.Random(seed)
    cells.clear_all()
    for x in range(GRID_W):
        for y in range(GRID_H):
            edge_dist = min(x, y, GRID_W - 1 - x, GRID_H - 1 - y)
            if edge_dist <= 2 and rng.random() < 0.4:
                cells.set((x, y), FOREST)
    cells.fill_rect((14, 3), (17, 6), WATER)
    cells.set(STOCKPILE, GRASS)

# -- Shared state -------------------------------------------------------------
grid = Grid2D(GRID_W, GRID_H)
cells = CellMap(default=GRASS)
log = EventLog()
bus = SignalBus()
sched = EventScheduler()
eguards = EventGuards()
stockpile_eid: int = -1
_name_idx: int = 0

# -- Colony Policy (LLM-controlled) ------------------------------------------
policy: dict[str, Any] = {
    "foraging_priority": "normal",   # low | normal | high | critical
    "building_priority": "normal",   # low | normal | high
    "crisis_mode": False,
    "rationing": False,
    "hunger_threshold": 40.0,
    "fatigue_threshold": 40.0,
    "foraging_ratio": 0.5,
}

_current_tick: list[int] = [0]

# -- FSM Guards ---------------------------------------------------------------
fg = FSMGuards()
fg.register("is_hungry", lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "hunger") < policy["hunger_threshold"])
fg.register("is_tired",  lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "fatigue") < policy["fatigue_threshold"])
fg.register("timer_done", lambda w, e: not w.has(e, Timer))
fg.register("at_stockpile", lambda w, e: grid.position_of(e) == STOCKPILE)
fg.register("should_forage", lambda w, e: (e % 100) / 100.0 < policy["foraging_ratio"])
fg.register("always", lambda w, e: True)
TRANS = {
    "idle": [["is_hungry", "foraging"], ["is_tired", "resting"],
             ["should_forage", "foraging"], ["always", "building"]],
    "foraging": [["timer_done", "returning"]],
    "returning": [["at_stockpile", "idle"]],
    "resting": [["timer_done", "idle"]],
    "building": [["timer_done", "idle"]],
}

# -- Event Guards -------------------------------------------------------------
eguards.register("is_winter", lambda w, s: s.is_active("winter"))
eguards.register("is_summer", lambda w, s: s.is_active("summer"))
eguards.register("is_autumn", lambda w, s: s.is_active("autumn"))

# -- Timer callback -----------------------------------------------------------
def _on_fire(world: World, ctx: TickContext, eid: int, timer: Timer) -> None:
    if not world.alive(eid): return
    ns = world.get(eid, NeedSet)
    nm = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    if timer.name == "forage":
        NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") + 30.0)
        log.emit(tick=ctx.tick_number, type="forage_done", colonist=nm)
    elif timer.name == "rest":
        NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") + 40.0)
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        log.emit(tick=ctx.tick_number, type="rest_done", colonist=nm)
    elif timer.name == "build":
        log.emit(tick=ctx.tick_number, type="build_done", colonist=nm)

# -- FSM transition -----------------------------------------------------------
def _on_trans(world: World, ctx: TickContext, eid: int, old: str, new: str) -> None:
    if new == "foraging":
        forests = cells.of_type("forest")
        if forests:
            target = ctx.random.choice(forests)
        else:
            target = (ctx.random.randint(0, GRID_W - 1), ctx.random.choice([0, GRID_H - 1]))
        world.attach(eid, Destination(coord=target))
        world.attach(eid, Timer(name="forage", remaining=FORAGE_TICKS))
    elif new == "returning":
        world.attach(eid, Destination(coord=STOCKPILE))
    elif new == "resting":
        world.attach(eid, Destination(coord=STOCKPILE))
        world.attach(eid, Timer(name="rest", remaining=REST_TICKS))
    elif new == "building":
        if world.has(eid, Destination):
            world.detach(eid, Destination)
        world.attach(eid, Timer(name="build", remaining=BUILD_TICKS))

    # Arrived at stockpile after foraging -- deposit food
    if old == "returning" and new == "idle":
        nm = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
        if world.has(stockpile_eid, Inventory):
            InventoryHelper.add(world.get(stockpile_eid, Inventory), "food", 1)
        log.emit(tick=ctx.tick_number, type="food_deposited", colonist=nm,
                 food_stored=InventoryHelper.count(world.get(stockpile_eid, Inventory), "food"))

# -- Movement system ----------------------------------------------------------
def _movement(world: World, ctx: TickContext) -> None:
    for eid, (dest, stats, mods) in world.query(Destination, StatBlock, Modifiers):
        pos = grid.position_of(eid)
        if pos is None or pos == dest.coord:
            world.detach(eid, Destination)
            continue
        path = pathfind(grid, pos, dest.coord, cost=cells.move_cost, walkable=cells.passable)
        if path is None or len(path) <= 1:
            world.detach(eid, Destination)
            continue
        speed = max(1, int(effective(stats, mods, "speed")))
        for step in path[1 : speed + 1]:
            grid.move(eid, step)
        final = grid.position_of(eid)
        if final is not None:
            world.attach(eid, Pos2D(x=float(final[0]), y=float(final[1])))
        if final == dest.coord:
            world.detach(eid, Destination)

# -- World event callbacks ----------------------------------------------------
def _ev_start(world: World, ctx: TickContext, name: str) -> None:
    log.emit(tick=ctx.tick_number, type="event_start", event=name)
    if name == "bountiful_harvest":
        for eid, (ns,) in world.query(NeedSet):
            if world.has(eid, Colonist):
                NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") + 20)
    elif name == "raid":
        cols = [(e, c) for e, (c,) in world.query(Colonist)]
        if cols:
            for e, c in ctx.random.sample(cols, min(len(cols), ctx.random.randint(2, 4))):
                ns = world.get(e, NeedSet)
                NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 40)
                log.emit(tick=ctx.tick_number, type="raid_damage", colonist=c.name)
        if world.alive(stockpile_eid) and world.has(stockpile_eid, Inventory):
            inv = world.get(stockpile_eid, Inventory)
            InventoryHelper.remove(inv, "food", ctx.random.randint(3, 10))
    elif name == "plague":
        pass  # plague effect applied via on_tick
    elif name in SEASONS:
        log.emit(tick=ctx.tick_number, type="season_change", season=name)

def _ev_end(world: World, ctx: TickContext, name: str) -> None:
    log.emit(tick=ctx.tick_number, type="event_end", event=name)

def _ev_tick(world: World, ctx: TickContext, name: str, rem: int) -> None:
    if name == "cold_snap":
        for eid, (ns,) in world.query(NeedSet):
            if world.has(eid, Colonist):
                NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 1.5)
    elif name == "heat_wave":
        for eid, (ns,) in world.query(NeedSet):
            if world.has(eid, Colonist):
                NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") - 1.0)
    elif name == "plague":
        for eid, (ns,) in world.query(NeedSet):
            if world.has(eid, Colonist):
                NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 0.8)
                NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") - 0.8)

def _on_zero(world: World, ctx: TickContext, eid: int, need: str) -> None:
    if not world.has(eid, Colonist): return
    nm = world.get(eid, Colonist).name
    if need == "hunger":
        log.emit(tick=ctx.tick_number, type="death", name=nm, cause="starvation")
        world.despawn(eid)
    elif need == "fatigue":
        log.emit(tick=ctx.tick_number, type="exhaustion", name=nm)

# -- Lifecycle on_death callback ----------------------------------------------
def _on_death(world: World, ctx: TickContext, eid: int, cause: str) -> None:
    if not world.has(eid, Colonist): return
    nm = world.get(eid, Colonist).name
    log.emit(tick=ctx.tick_number, type="death", name=nm, cause="old_age")

# -- Birth system -------------------------------------------------------------
def _birth(world: World, ctx: TickContext) -> None:
    global _name_idx
    alive = len(list(world.query(Colonist)))
    if alive >= MAX_POP: return
    if not world.alive(stockpile_eid) or not world.has(stockpile_eid, Inventory): return
    stored = InventoryHelper.count(world.get(stockpile_eid, Inventory), "food")
    if stored < BIRTH_FOOD_MIN or ctx.random.random() > BIRTH_CHANCE: return
    InventoryHelper.remove(world.get(stockpile_eid, Inventory), "food", BIRTH_FOOD_COST)
    eid = world.spawn()
    nm = EXTRA_NAMES[_name_idx % len(EXTRA_NAMES)]; _name_idx += 1
    world.attach(eid, Colonist(name=nm))
    # Spawn near stockpile on a passable tile
    x, y = STOCKPILE[0], STOCKPILE[1]
    for _ in range(20):
        cx = ctx.random.randint(max(0, x - 2), min(GRID_W - 1, x + 2))
        cy = ctx.random.randint(max(0, y - 2), min(GRID_H - 1, y + 2))
        if cells.passable((cx, cy)):
            x, y = cx, cy
            break
    world.attach(eid, Pos2D(x=float(x), y=float(y))); grid.place(eid, (x, y))
    ns = NeedSet(data={})
    NeedHelper.add(ns, "hunger", ctx.random.uniform(60.0, 90.0), 100.0, 0.8, 15.0)
    NeedHelper.add(ns, "fatigue", ctx.random.uniform(70.0, 100.0), 100.0, 0.4, 15.0)
    world.attach(eid, ns)
    world.attach(eid, StatBlock(data={"strength": 8.0, "speed": 2.0}))
    world.attach(eid, Modifiers(entries=[]))
    world.attach(eid, Lifecycle(born_tick=ctx.tick_number,
                                max_age=ctx.random.randint(3000, 5000)))
    world.attach(eid, FSM(state="building", transitions=TRANS))
    world.attach(eid, Timer(name="build", remaining=ctx.random.randint(1, BUILD_TICKS)))
    log.emit(tick=ctx.tick_number, type="birth", name=nm)

def _flush(world: World, ctx: TickContext) -> None:
    bus.flush()

def _census(world: World, ctx: TickContext) -> None:
    if ctx.tick_number % 500 != 0: return
    pop = len(list(world.query(Colonist)))
    food = InventoryHelper.count(world.get(stockpile_eid, Inventory), "food") if world.alive(stockpile_eid) else 0
    log.emit(tick=ctx.tick_number, type="census", population=pop, food=food)

# -- Tick stamp system --------------------------------------------------------
def _tick_stamp(world: World, ctx: TickContext) -> None:
    _current_tick[0] = ctx.tick_number

# -- Directive Handlers -------------------------------------------------------
_FORAGE_LEVEL_MAP = {"low": 0.2, "normal": 0.5, "high": 0.7, "critical": 0.9}

def _handle_set_foraging_priority(d: dict[str, Any]) -> None:
    level = str(d.get("level", "normal")).lower()
    if level not in _FORAGE_LEVEL_MAP:
        return
    policy["foraging_priority"] = level
    policy["foraging_ratio"] = _FORAGE_LEVEL_MAP[level]
    log.emit(tick=_current_tick[0], type="directive",
             agent="steward", action="set_foraging_priority", level=level,
             foraging_ratio=policy["foraging_ratio"])

def _handle_set_hunger_threshold(d: dict[str, Any]) -> None:
    try:
        threshold = float(d.get("threshold", 40.0))
    except (TypeError, ValueError):
        return
    threshold = max(30.0, min(60.0, threshold))
    policy["hunger_threshold"] = threshold
    log.emit(tick=_current_tick[0], type="directive",
             agent="steward", action="set_hunger_threshold", threshold=threshold)

def _handle_set_rationing(d: dict[str, Any]) -> None:
    enabled = bool(d.get("enabled", False))
    policy["rationing"] = enabled
    log.emit(tick=_current_tick[0], type="directive",
             agent="steward", action="set_rationing", enabled=enabled)

def _handle_set_building_priority(d: dict[str, Any]) -> None:
    level = str(d.get("level", "normal")).lower()
    if level not in ("low", "normal", "high"):
        return
    policy["building_priority"] = level
    # Adjust foraging_ratio inversely if not in crisis
    if not policy["crisis_mode"]:
        adj = {"low": 0.6, "normal": 0.5, "high": 0.3}
        policy["foraging_ratio"] = adj.get(level, 0.5)
    log.emit(tick=_current_tick[0], type="directive",
             agent="builder", action="set_building_priority", level=level)

def _handle_activate_crisis(d: dict[str, Any]) -> None:
    reason = str(d.get("reason", "unknown"))
    policy["crisis_mode"] = True
    policy["hunger_threshold"] = 55.0
    policy["fatigue_threshold"] = 55.0
    policy["foraging_ratio"] = 0.9
    policy["foraging_priority"] = "critical"
    log.emit(tick=_current_tick[0], type="directive",
             agent="warden", action="activate_crisis", reason=reason)

def _handle_deactivate_crisis(d: dict[str, Any]) -> None:
    policy["crisis_mode"] = False
    policy["hunger_threshold"] = 40.0
    policy["fatigue_threshold"] = 40.0
    policy["foraging_ratio"] = 0.5
    policy["foraging_priority"] = "normal"
    policy["building_priority"] = "normal"
    log.emit(tick=_current_tick[0], type="directive",
             agent="warden", action="deactivate_crisis")

# -- Mock Response Functions --------------------------------------------------

def _mock_steward(system_prompt: str, user_message: str) -> str:
    msg = user_message.lower()
    # Parse food and population from context
    food = 0
    pop = 1
    food_match = re.search(r"food=(\d+)", msg)
    if food_match:
        food = int(food_match.group(1))
    pop_match = re.search(r"total entities:\s*(\d+)", msg)
    if pop_match:
        pop = max(1, int(pop_match.group(1)))
    per_capita = food / pop

    if per_capita < 1.0:
        level = "critical"
        threshold = 55.0
        rationing = True
    elif per_capita < 2.5:
        level = "high"
        threshold = 50.0
        rationing = False
    elif per_capita < 5.0:
        level = "normal"
        threshold = 40.0
        rationing = False
    else:
        level = "low"
        threshold = 35.0
        rationing = False

    return json.dumps({
        "directives": [
            {"type": "set_foraging_priority", "level": level},
            {"type": "set_hunger_threshold", "threshold": threshold},
            {"type": "set_rationing", "enabled": rationing},
        ],
        "reasoning": f"Food per capita is {per_capita:.1f} — setting foraging to {level}.",
        "confidence": 0.9,
    })


def _mock_warden(system_prompt: str, user_message: str) -> str:
    msg = user_message.lower()
    # Check for active threats: event_start without matching event_end
    has_raid = "event_start" in msg and "raid" in msg
    has_plague = "event_start" in msg and "plague" in msg
    # Check if threats ended
    raid_ended = "event_end" in msg and "raid" in msg
    plague_ended = "event_end" in msg and "plague" in msg

    active_threat = (has_raid and not raid_ended) or (has_plague and not plague_ended)

    if active_threat and "crisis_mode=true" not in msg:
        reasons = []
        if has_raid and not raid_ended:
            reasons.append("raid")
        if has_plague and not plague_ended:
            reasons.append("plague")
        return json.dumps({
            "directives": [
                {"type": "activate_crisis", "reason": " and ".join(reasons)},
            ],
            "reasoning": f"Active threat detected: {', '.join(reasons)}.",
            "confidence": 0.95,
        })
    elif not active_threat and "crisis_mode=true" in msg:
        return json.dumps({
            "directives": [
                {"type": "deactivate_crisis"},
            ],
            "reasoning": "Threats resolved, returning to normal operations.",
            "confidence": 0.9,
        })
    else:
        return json.dumps({
            "directives": [],
            "reasoning": "Situation stable, maintaining current posture.",
            "confidence": 0.8,
        })


def _mock_builder(system_prompt: str, user_message: str) -> str:
    msg = user_message.lower()
    if "crisis_mode=true" in msg:
        level = "low"
        reasoning = "Crisis active — deferring construction to prioritize survival."
    elif "foraging_priority=critical" in msg or "foraging_priority=high" in msg:
        level = "low"
        reasoning = "Foraging demand is high — reducing building activity."
    else:
        level = "normal"
        reasoning = "Conditions stable — maintaining standard building pace."

    return json.dumps({
        "directives": [
            {"type": "set_building_priority", "level": level},
        ],
        "reasoning": reasoning,
        "confidence": 0.85,
    })


def _mock_narrator(system_prompt: str, user_message: str) -> str:
    msg = user_message.lower()
    notable: list[str] = []
    tone = "neutral"

    # Count deaths and births — context format is "death: cause=..., name=..."
    death_count = msg.count("] death:")
    birth_count = msg.count("] birth:")

    # Check for world events — context format: "event_start: event=raid"
    has_raid = "event=raid" in msg
    has_plague = "event=plague" in msg
    has_cold = "event=cold_snap" in msg
    has_harvest = "event=bountiful_harvest" in msg

    # Check directive activity
    has_crisis = "activate_crisis" in msg
    has_rationing = "rationing=true" in msg

    if death_count > 2:
        notable.append("Multiple colonists have perished")
        tone = "somber"
    elif death_count > 0:
        notable.append(f"{death_count} colonist{'s' if death_count > 1 else ''} passed away")
    if has_raid:
        notable.append("Raiders descended upon the settlement")
        tone = "tense"
    if has_plague:
        notable.append("A plague swept through the colony")
        tone = "grim"
    if has_cold:
        notable.append("A bitter cold snap tested the colonists' resolve")
    if has_harvest:
        notable.append("A bountiful harvest lifted spirits")
        tone = "hopeful"
    if has_crisis:
        notable.append("The Warden has declared a state of crisis")
        if tone == "neutral":
            tone = "tense"
    if has_rationing:
        notable.append("Rationing has been imposed on the colony")
    if birth_count > 0:
        notable.append(f"{birth_count} new soul{'s' if birth_count > 1 else ''} joined the colony")
        if tone == "neutral":
            tone = "hopeful"

    if not notable:
        notable.append("The colony endured through another quiet season")
        tone = "reflective"

    text = ". ".join(notable) + "."

    return json.dumps({
        "text": text,
        "tone": tone,
        "notable": notable,
    })


def _mock_dispatch(system_prompt: str, user_message: str) -> str:
    sp = system_prompt.lower()
    if "steward" in sp:
        return _mock_steward(system_prompt, user_message)
    elif "warden" in sp:
        return _mock_warden(system_prompt, user_message)
    elif "builder" in sp:
        return _mock_builder(system_prompt, user_message)
    elif "narrator" in sp:
        return _mock_narrator(system_prompt, user_message)
    return json.dumps({"directives": [], "reasoning": "unknown agent"})

# -- Agent Context Functions --------------------------------------------------

_resource_ctx = make_resource_context(["food"])
_population_ctx = make_population_context(include_needs=True, include_fsm_states=True)
_event_ctx_tactical = make_event_context(log, max_events=15,
    event_types=["event_start", "event_end", "death", "raid_damage",
                 "census", "directive"])
_event_ctx_narrator = make_event_context(log, max_events=30,
    event_types=["event_start", "event_end", "death", "birth", "raid_damage",
                 "census", "directive", "season_change"])


def _policy_summary() -> str:
    lines = ["=== Colony Policy ==="]
    for k, v in sorted(policy.items()):
        lines.append(f"  {k}={v}")
    return "\n".join(lines)


def _steward_context(world: World, eid: int) -> str:
    parts = [
        _resource_ctx(world, eid),
        _population_ctx(world, eid),
        _event_ctx_tactical(world, eid),
        _policy_summary(),
    ]
    return "\n\n".join(parts)


def _warden_context(world: World, eid: int) -> str:
    parts = [
        _population_ctx(world, eid),
        _event_ctx_tactical(world, eid),
        _policy_summary(),
    ]
    return "\n\n".join(parts)


def _builder_context(world: World, eid: int) -> str:
    parts = [
        _resource_ctx(world, eid),
        _population_ctx(world, eid),
        _policy_summary(),
    ]
    return "\n\n".join(parts)


def _narrator_context(world: World, eid: int) -> str:
    parts = [
        _resource_ctx(world, eid),
        _population_ctx(world, eid),
        _event_ctx_narrator(world, eid),
        _policy_summary(),
    ]
    # Include directive events since last narration
    directive_evs = log.query(type="directive")
    if world.has(eid, Blackboard):
        bb = world.get(eid, Blackboard)
        narratives = bb.data.get("narratives", [])
        last_tick = narratives[-1]["tick"] if narratives else 0
        directive_evs = [e for e in directive_evs if e.tick > last_tick]
    if directive_evs:
        lines = ["=== Recent Directives ==="]
        for ev in directive_evs[-10:]:
            data_str = ", ".join(f"{k}={v}" for k, v in sorted(ev.data.items()))
            lines.append(f"  [Tick {ev.tick}] {data_str}")
        parts.append("\n".join(lines))
    # Include previous narratives for continuity
    if world.has(eid, Blackboard):
        bb = world.get(eid, Blackboard)
        narratives = bb.data.get("narratives", [])
        if narratives:
            lines = ["=== Previous Narratives ==="]
            for n in narratives[-3:]:
                lines.append(f"  [Tick {n['tick']}, {n['tone']}] {n['text']}")
            parts.append("\n".join(lines))
    return "\n\n".join(parts)

# -- Narrator Parser ----------------------------------------------------------

def _narrator_parser(response: str, blackboard: Blackboard) -> None:
    cleaned = response.strip()
    # Strip code fences if present
    fence_match = re.match(r"^\s*```(?:json)?\s*\n?(.*?)\n?\s*```\s*$", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    entry = {
        "text": parsed.get("text", ""),
        "tone": parsed.get("tone", "neutral"),
        "tick": _current_tick[0],
        "notable": parsed.get("notable", []),
    }
    narratives: list[dict[str, Any]] = blackboard.data.setdefault("narratives", [])
    narratives.append(entry)

# -- LLM Setup ---------------------------------------------------------------

# Entity IDs for agents (set during _setup_llm)
_agent_eids: dict[str, int] = {}

def _setup_llm(engine: Engine, llm_mode: str, llm_url: str, model: str, api_key: str = "") -> Any:
    """Set up LLM manager, agents, and systems. Returns the LLMSystem for shutdown.

    Must be called BEFORE adding the other systems so that tick_stamp, pressure,
    and LLM dispatch run first in each tick.
    """
    w = engine.world

    config = LLMConfig(
        max_queries_per_tick=2,
        max_queries_per_second=10,
        thread_pool_size=4,
        query_timeout=30.0,
    )
    manager = LLMManager(config)

    # Roles
    manager.define_role("steward", (
        "You are the Steward of a colony simulation. You manage food resources and "
        "foraging priorities. You monitor food per capita and set foraging urgency.\n"
        "Respond with JSON: {\"directives\": [{\"type\": \"set_foraging_priority\", \"level\": ...}, "
        "{\"type\": \"set_hunger_threshold\", \"threshold\": ...}, "
        "{\"type\": \"set_rationing\", \"enabled\": ...}], "
        "\"reasoning\": ..., \"confidence\": ...}\n"
        "Levels: low, normal, high, critical. Threshold: 30-60."
    ))
    manager.define_role("warden", (
        "You are the Warden of a colony simulation. You handle defense and crisis response. "
        "You activate crisis mode during raids and plagues, and deactivate when threats pass.\n"
        "Respond with JSON: {\"directives\": [{\"type\": \"activate_crisis\", \"reason\": ...}], "
        "\"reasoning\": ..., \"confidence\": ...}\n"
        "Or to deactivate: {\"directives\": [{\"type\": \"deactivate_crisis\"}], ...}"
    ))
    manager.define_role("builder", (
        "You are the Builder of a colony simulation. You manage construction priorities. "
        "During crises you defer building; otherwise you maintain steady construction.\n"
        "Respond with JSON: {\"directives\": [{\"type\": \"set_building_priority\", \"level\": ...}], "
        "\"reasoning\": ..., \"confidence\": ...}\n"
        "Levels: low, normal, high."
    ))
    manager.define_role("narrator", (
        "You are the Narrator of a colony simulation. You observe events, deaths, births, "
        "and directives, then compose a brief narrative passage (1-3 sentences) describing "
        "the state of the colony. You do NOT issue directives.\n"
        "Respond with JSON: {\"text\": \"...\", \"tone\": \"...\", \"notable\": [...]}\n"
        "Tones: hopeful, somber, tense, grim, neutral, reflective."
    ))

    # Personalities
    manager.define_personality("pragmatic", (
        "You are practical and data-driven. You base decisions on numbers and "
        "thresholds rather than sentiment."
    ))
    manager.define_personality("vigilant", (
        "You are watchful and quick to respond to threats. You err on the side "
        "of caution, activating defenses at the first sign of danger."
    ))
    manager.define_personality("steady", (
        "You are patient and methodical. You maintain a steady pace and avoid "
        "overreacting to temporary setbacks."
    ))
    manager.define_personality("poetic", (
        "You are eloquent and observe the human condition. You find meaning "
        "in both triumphs and tragedies."
    ))

    # Contexts
    manager.define_context("steward_ctx", _steward_context)
    manager.define_context("warden_ctx", _warden_context)
    manager.define_context("builder_ctx", _builder_context)
    manager.define_context("narrator_ctx", _narrator_context)

    # Parsers
    steward_handlers: dict[str, DirectiveHandler] = {
        "set_foraging_priority": _handle_set_foraging_priority,
        "set_hunger_threshold": _handle_set_hunger_threshold,
        "set_rationing": _handle_set_rationing,
    }
    warden_handlers: dict[str, DirectiveHandler] = {
        "activate_crisis": _handle_activate_crisis,
        "deactivate_crisis": _handle_deactivate_crisis,
    }
    builder_handlers: dict[str, DirectiveHandler] = {
        "set_building_priority": _handle_set_building_priority,
    }
    manager.define_parser("steward_parser", make_directive_parser(steward_handlers))
    manager.define_parser("warden_parser", make_directive_parser(warden_handlers))
    manager.define_parser("builder_parser", make_directive_parser(builder_handlers))
    manager.define_parser("narrator_parser", _narrator_parser)

    # Client
    if llm_mode == "mock":
        client = MockClient(responses=_mock_dispatch, latency=0.0, error_rate=0.05)
    else:
        client = LMStudioAnthropicClient(model=model, base_url=llm_url, api_key=api_key)
    manager.register_client(client)

    # Observable: print narrator passages live
    def _on_response(eid: int, latency: float, resp_size: int, tick: int) -> None:
        if eid == _agent_eids.get("narrator") and w.has(eid, Blackboard):
            bb = w.get(eid, Blackboard)
            narratives = bb.data.get("narratives", [])
            if narratives:
                n = narratives[-1]
                season_idx = (tick // TICKS_SEASON) % 4
                season = SEASONS[season_idx]
                year = tick // TICKS_YEAR + 1
                print(f"\n  >> Narrator [Y{year} {season}, tick {tick}, {n['tone']}]: {n['text']}")

    manager.on_response(_on_response)

    # Spawn agent entities
    for name, role, personality, context, parser_name, interval, priority, cooldown in [
        ("Steward",  "steward",  "pragmatic", "steward_ctx",  "steward_parser",  200, 5, 100),
        ("Warden",   "warden",   "vigilant",  "warden_ctx",   "warden_parser",   150, 5, 80),
        ("Builder",  "builder",  "steady",    "builder_ctx",  "builder_parser",  300, 3, 150),
        ("Narrator", "narrator", "poetic",    "narrator_ctx", "narrator_parser", 500, 1, 250),
    ]:
        eid = w.spawn()
        w.attach(eid, Blackboard(data={}))
        w.attach(eid, LLMAgent(
            role=role,
            personality=personality,
            context=context,
            parser=parser_name,
            query_interval=interval,
            priority=priority,
            max_retries=3,
            cooldown_ticks=cooldown,
        ))
        _agent_eids[role] = eid

    # Pressure system
    pressure_thresholds = PressureThresholds(
        resource_change=0.25,
        population_change=0.2,
        critical_needs_ratio=0.4,
        event_types=("event_start", "event_end", "death", "raid_damage"),
        event_burst=3,
    )

    llm_sys = make_llm_system(manager)
    pressure_sys = make_pressure_system(
        pressure_thresholds, log, check_interval=10, min_priority=3,
    )

    # Add systems: tick_stamp, pressure, llm (will run before colony systems)
    engine.add_system(_tick_stamp)
    engine.add_system(pressure_sys)
    engine.add_system(llm_sys)

    return llm_sys

# -- LMStudioOpenAIClient (inline for --llm mode) ----------------------------

class LMStudioAnthropicClient:
    """LLM client for LM Studio's Anthropic-compatible endpoint."""

    def __init__(
        self,
        model: str = "default",
        base_url: str = "http://localhost:1234",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str = "",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._api_key = api_key or "lm-studio"

    def query(self, system_prompt: str, user_message: str) -> str:
        payload = json.dumps({
            "model": self._model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["content"][0]["text"]


class LMStudioOpenAIClient:
    """LLM client for LM Studio's OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str = "default",
        base_url: str = "http://localhost:1234",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str = "",
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._api_key = api_key

    def query(self, system_prompt: str, user_message: str) -> str:
        payload = json.dumps({
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }).encode("utf-8")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(
            f"{self._base_url}/v1/chat/completions",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

# -- Setup --------------------------------------------------------------------
def setup(
    seed: int = 42,
    llm_mode: str = "none",
    llm_url: str = "http://localhost:1234",
    model: str = "default",
    api_key: str = "",
) -> tuple[Engine, Any]:
    global stockpile_eid
    engine = Engine(tps=20, seed=seed)
    w = engine.world
    register_colony_components(w)
    w.register_component(Colonist)
    w.register_component(Destination)

    # Generate terrain
    _setup_terrain(seed)

    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Pos2D(x=float(STOCKPILE[0]), y=float(STOCKPILE[1])))
    w.attach(stockpile_eid, Inventory(capacity=60))
    grid.place(stockpile_eid, STOCKPILE)

    rng = _random_mod.Random(seed)
    for i in range(8):
        eid = w.spawn()
        w.attach(eid, Colonist(name=NAMES[i]))
        x = 2 + (i * 3) % (GRID_W - 4)
        y = 2 + (i * 5) % (GRID_H - 4)
        # Nudge off impassable tiles
        while not cells.passable((x, y)):
            x = rng.randint(0, GRID_W - 1)
            y = rng.randint(0, GRID_H - 1)
        w.attach(eid, Pos2D(x=float(x), y=float(y)))
        grid.place(eid, (x, y))
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", rng.uniform(55.0, 90.0), 100.0, 0.8, 15.0)
        NeedHelper.add(ns, "fatigue", rng.uniform(65.0, 100.0), 100.0, 0.4, 15.0)
        w.attach(eid, ns)
        w.attach(eid, StatBlock(data={"strength": 8.0 + i % 4, "speed": 2.0 + i % 3}))
        w.attach(eid, Modifiers(entries=[]))
        w.attach(eid, Lifecycle(born_tick=0, max_age=rng.randint(1500, 2500)))
        # Stagger initial build for desync
        w.attach(eid, FSM(state="building", transitions=TRANS))
        w.attach(eid, Timer(name="build", remaining=rng.randint(1, BUILD_TICKS)))

    sched.define_cycle(CycleDef(name="seasons", phases=[
        ("spring", 500), ("summer", 500), ("autumn", 500), ("winter", 500)]))
    sched.define(EventDef("cold_snap", (80, 150), cooldown=200, probability=0.003, conditions=["is_winter"]))
    sched.define(EventDef("heat_wave", (60, 120), cooldown=200, probability=0.002, conditions=["is_summer"]))
    sched.define(EventDef("bountiful_harvest", (100, 200), cooldown=300, probability=0.004, conditions=["is_autumn"]))
    sched.define(EventDef("raid", (30, 60), cooldown=500, probability=0.001))
    sched.define(EventDef("plague", (100, 200), cooldown=1000, probability=0.0004))

    # LLM systems added first so they run before colony systems each tick
    llm_sys = None
    if llm_mode != "none":
        llm_sys = _setup_llm(engine, llm_mode, llm_url, model, api_key)

    # Colony systems (order matters)
    engine.add_system(make_timer_system(on_fire=_on_fire))
    engine.add_system(make_fsm_system(guards=fg, on_transition=_on_trans))
    engine.add_system(_movement)
    engine.add_system(make_need_decay_system(on_zero=_on_zero))
    engine.add_system(make_modifier_tick_system())
    engine.add_system(make_event_system(sched, eguards, on_start=_ev_start, on_end=_ev_end, on_tick=_ev_tick))
    engine.add_system(make_lifecycle_system(on_death=_on_death))
    engine.add_system(_birth)
    engine.add_system(make_spatial_cleanup_system(grid))
    engine.add_system(_flush)
    engine.add_system(_census)

    return engine, llm_sys

# -- Chronicle ----------------------------------------------------------------
def _season_at(tick: int, changes: list[tuple[int, str]]) -> str:
    """Return the season name active at *tick* using logged season_change events."""
    result = "spring"  # default before first change
    for t, s in changes:
        if t > tick:
            break
        result = s
    return result


def chronicle(seed: int, total_ticks: int, narratives: list[dict[str, Any]] | None = None) -> None:
    all_ev = log.query()

    # Build season transition timeline from logged events
    changes: list[tuple[int, str]] = sorted(
        (ev.tick, ev.data["season"])
        for ev in log.query(type="season_change")
    )

    # Build event spans (start tick, end tick)
    spans: dict[str, list[tuple[int, int]]] = {}
    opened: dict[str, int] = {}
    for ev in all_ev:
        en = ev.data.get("event", "")
        if ev.type == "event_start" and en in W_EVENTS:
            opened[en] = ev.tick
        elif ev.type == "event_end" and en in opened:
            spans.setdefault(en, []).append((opened.pop(en), ev.tick))

    # Bucket all events by (year, season_name)
    def year_season(tick: int) -> tuple[int, str]:
        return (tick // TICKS_YEAR + 1, _season_at(tick, changes))

    buckets: dict[tuple[int, str], list[Event]] = {}
    for ev in all_ev:
        k = year_season(ev.tick)
        buckets.setdefault(k, []).append(ev)

    # Index narrator passages by (year, season) for interleaving
    narr_by_ys: dict[tuple[int, str], list[dict[str, Any]]] = {}
    if narratives:
        for n in narratives:
            ys = year_season(n["tick"])
            narr_by_ys.setdefault(ys, []).append(n)

    # Summary stats
    deaths = log.query(type="death")
    births = log.query(type="birth")
    builds = log.query(type="build_done")
    directives = log.query(type="directive")
    cc: dict[str, int] = {}
    for d in deaths:
        c = d.data.get("cause", "unknown"); cc[c] = cc.get(c, 0) + 1
    wc: dict[str, int] = {}
    for ev in log.query(type="event_start"):
        en = ev.data.get("event", "")
        if en in W_EVENTS:
            wc[en] = wc.get(en, 0) + 1

    # Determine actual season order from transitions
    years = total_ticks // TICKS_YEAR
    print(f"\n=== The Chronicle of the Colony (seed={seed}) ===")
    for y in range(1, years + 1):
        print(f"\n--- Year {y} ---")
        y_start = (y - 1) * TICKS_YEAR
        y_end = y * TICKS_YEAR
        # Get seasons active in this year, in chronological order
        year_seasons: list[str] = []
        # Check what season is active at the start of this year
        start_season = _season_at(y_start, changes)
        year_seasons.append(start_season)
        for t, s in changes:
            if y_start < t < y_end and s not in year_seasons:
                year_seasons.append(s)
        for sn in year_seasons:
            lines: list[str] = []
            if y == 1 and sn == year_seasons[0]:
                lines.append("The colony was founded with 8 settlers.")
            # World events that started during this year+season
            for en in W_EVENTS:
                for (t0, t1) in spans.get(en, []):
                    ys = year_season(t0)
                    if ys == (y, sn):
                        lbl = en.replace("_", " ")
                        if en in ("cold_snap", "heat_wave", "plague"):
                            lines.append(f"A {lbl} struck (ticks {t0}-{t1}).")
                        elif en == "bountiful_harvest":
                            lines.append("A bountiful harvest blessed the colony.")
                        elif en == "raid":
                            lines.append(f"Raiders attacked (ticks {t0}-{t1}).")
            bucket = buckets.get((y, sn), [])
            for d in (e for e in bucket if e.type == "death"):
                lines.append(f"{d.data.get('name', '?')} died of {d.data.get('cause', '?')}.")
            for b in (e for e in bucket if e.type == "birth"):
                lines.append(f"{b.data.get('name', '?')} was born into the colony.")
            print(f"  {sn.capitalize()}: {' '.join(lines) if lines else 'All was quiet.'}")
            # Interleave narrator passages
            for n in narr_by_ys.get((y, sn), []):
                print(f"    >> [{n['tone']}] {n['text']}")

    lc = log.last("census")
    fp, ff = (lc.data.get("population", 0), lc.data.get("food", 0)) if lc else (0, 0)
    print(f"\n=== Final Reckoning ===")
    print(f"  Survivors: {fp}")
    print(f"  Born: {len(births)} new colonists")
    cs = ", ".join(f"{n} {c}" for c, n in sorted(cc.items()))
    print(f"  Deaths: {len(deaths)} total" + (f" ({cs})" if cs else ""))
    ep = [f"{wc[e]} {l}" for e, l in [("cold_snap", "cold snaps"), ("heat_wave", "heat waves"),
          ("bountiful_harvest", "harvests"), ("raid", "raids"), ("plague", "plagues")] if wc.get(e, 0) > 0]
    print(f"  Events survived: {', '.join(ep) if ep else 'none'}")
    print(f"  Food stored: {ff}")
    print(f"  Buildings completed: {len(builds)}")
    if directives:
        print(f"  Directives issued: {len(directives)}")

# -- Main ---------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chronicle demo -- colony simulation with optional LLM agents")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--mock", action="store_const", const="mock", dest="llm_mode",
                            help="Use MockClient (default)")
    mode_group.add_argument("--llm", action="store_const", const="llm", dest="llm_mode",
                            help="Use real LLM endpoint")
    mode_group.add_argument("--no-llm", action="store_const", const="none", dest="llm_mode",
                            help="Run without LLM (original behavior)")
    parser.add_argument("--llm-url", default="http://localhost:1234",
                        help="LLM endpoint URL (default: http://localhost:1234)")
    parser.add_argument("--model", default="default",
                        help="Model name for real LLM")
    parser.add_argument("--api-key", default="",
                        help="Bearer token / API key for LLM endpoint")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument("--ticks", type=int, default=10_000,
                        help="Total ticks (default: 10000)")
    parser.set_defaults(llm_mode="mock")
    args = parser.parse_args()

    seed = args.seed
    total_ticks = args.ticks
    llm_mode = args.llm_mode

    mode_label = {"mock": "MockClient", "llm": f"LLM ({args.llm_url})", "none": "no LLM"}
    print(f"=== Chronicle demo (seed={seed}, {total_ticks} ticks, {mode_label[llm_mode]}) ===")

    engine, llm_sys = setup(seed, llm_mode, args.llm_url, args.model, args.api_key)

    n_forest = len(cells.of_type("forest"))
    n_water = len(cells.of_type("water"))
    print(f"Terrain: {n_forest} forest, {n_water} water, "
          f"{GRID_W * GRID_H - n_forest - n_water} grass\n")

    if llm_mode == "llm":
        # Step-by-step with sleeps so async LLM futures can complete
        for tick_num in range(1, total_ticks + 1):
            engine.step()
            time.sleep(0.05)
    else:
        engine.run(total_ticks)

    # Collect narratives from narrator blackboard
    narratives = None
    narrator_eid = _agent_eids.get("narrator")
    if narrator_eid is not None and engine.world.has(narrator_eid, Blackboard):
        bb = engine.world.get(narrator_eid, Blackboard)
        narratives = bb.data.get("narratives")

    # Shutdown LLM system
    if llm_sys is not None:
        llm_sys.shutdown()

    chronicle(seed, total_ticks, narratives)

if __name__ == "__main__":
    main()
