"""Chronicle demo -- 10,000-tick colony simulation with seasons and world events.

Uses tick-event for a 4-season cycle and probabilistic world events (cold snaps,
heat waves, harvests, raids, plagues).  After the simulation, walks the EventLog
to produce a narrative "chronicle" grouped by year and season.

Run: uv run --package tick-colony python -m examples.chronicle
"""
from __future__ import annotations

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext
from tick_colony import (
    Pos2D, NeedSet, NeedHelper, StatBlock, Modifiers, Container, Lifecycle,
    EventLog, Event, add_modifier, add_to_container, remove_from_container,
    contents, register_colony_components,
    Grid2D, make_spatial_cleanup_system, Timer, make_timer_system,
    FSM, FSMGuards, make_fsm_system, SignalBus,
    make_need_decay_system, make_modifier_tick_system, make_lifecycle_system,
    EventScheduler, EventGuards, EventDef, CycleDef, make_event_system,
)
from tick_spatial import Coord

@dataclass
class Colonist:
    name: str

# -- Constants ----------------------------------------------------------------
GRID_W, GRID_H = 20, 20
NAMES = ["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"]
EXTRA_NAMES = ["Ingrid", "Jarl", "Kara", "Leif", "Mira", "Nils", "Olga", "Per",
               "Runa", "Sven", "Tova", "Ulf", "Vera", "Wren", "Ylva", "Zeke"]
STOCKPILE: Coord = (10, 10)
TICKS_SEASON, TICKS_YEAR, TOTAL = 500, 2000, 10_000
SEASONS = ["spring", "summer", "autumn", "winter"]
W_EVENTS = ("cold_snap", "heat_wave", "bountiful_harvest", "raid", "plague")

# -- Shared state -------------------------------------------------------------
grid = Grid2D(GRID_W, GRID_H)
log = EventLog()
bus = SignalBus()
sched = EventScheduler()
eguards = EventGuards()
stockpile_eid: int = -1
_name_idx: int = 0

# -- FSM Guards ---------------------------------------------------------------
fg = FSMGuards()
fg.register("is_hungry", lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "hunger") < 40)
fg.register("is_tired",  lambda w, e: NeedHelper.get_value(w.get(e, NeedSet), "fatigue") < 40)
fg.register("timer_done", lambda w, e: not w.has(e, Timer))
fg.register("always", lambda w, e: True)
TRANS = {
    "idle": [["is_hungry", "foraging"], ["is_tired", "resting"], ["always", "building"]],
    "foraging": [["timer_done", "idle"]], "resting": [["timer_done", "idle"]],
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
        NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") + 20)
        grid.move(eid, STOCKPILE)
        food = world.spawn()
        if world.has(stockpile_eid, Container):
            add_to_container(world, stockpile_eid, food)
        log.emit(tick=ctx.tick_number, type="forage_done", colonist=nm)
    elif timer.name == "rest":
        NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") + 25)
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        log.emit(tick=ctx.tick_number, type="rest_done", colonist=nm)
    elif timer.name == "build":
        log.emit(tick=ctx.tick_number, type="build_done", colonist=nm)

# -- FSM transition -----------------------------------------------------------
def _on_trans(world: World, ctx: TickContext, eid: int, old: str, new: str) -> None:
    if new == "foraging":
        tx, ty = ctx.random.randint(0, GRID_W - 1), ctx.random.choice([0, GRID_H - 1])
        _move(eid, tx, ty, ctx)
        world.attach(eid, Timer(name="forage", remaining=8))
    elif new == "resting":
        _move(eid, STOCKPILE[0], STOCKPILE[1], ctx)
        world.attach(eid, Timer(name="rest", remaining=4))
    elif new == "building":
        world.attach(eid, Timer(name="build", remaining=10))

def _move(eid: int, tx: int, ty: int, ctx: TickContext) -> None:
    pos = grid.position_of(eid)
    if not pos: return
    x, y = pos
    for _ in range(2):
        dx = 1 if tx > x else (-1 if tx < x else 0)
        dy = 1 if ty > y else (-1 if ty < y else 0)
        nx, ny = max(0, min(GRID_W-1, x+dx)), max(0, min(GRID_H-1, y+dy))
        if (nx, ny) != (x, y):
            grid.move(eid, (nx, ny)); x, y = nx, ny

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
        if world.alive(stockpile_eid) and world.has(stockpile_eid, Container):
            stored = contents(world, stockpile_eid)
            for f in stored[:min(len(stored), ctx.random.randint(3, 10))]:
                remove_from_container(world, stockpile_eid, f); world.despawn(f)
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

# -- Birth system -------------------------------------------------------------
def _birth(world: World, ctx: TickContext) -> None:
    global _name_idx
    alive = len(list(world.query(Colonist)))
    if alive >= 8: return
    if not world.alive(stockpile_eid) or not world.has(stockpile_eid, Container): return
    stored = contents(world, stockpile_eid)
    if len(stored) < 8 or ctx.random.random() > 0.01: return
    for f in stored[:5]:
        remove_from_container(world, stockpile_eid, f); world.despawn(f)
    eid = world.spawn()
    nm = EXTRA_NAMES[_name_idx % len(EXTRA_NAMES)]; _name_idx += 1
    world.attach(eid, Colonist(name=nm))
    x, y = ctx.random.randint(8, 12), ctx.random.randint(8, 12)
    world.attach(eid, Pos2D(x=float(x), y=float(y))); grid.place(eid, (x, y))
    ns = NeedSet(data={})
    NeedHelper.add(ns, "hunger", 80.0, 100.0, 1.0, 20.0)
    NeedHelper.add(ns, "fatigue", 90.0, 100.0, 0.6, 20.0)
    world.attach(eid, ns)
    world.attach(eid, StatBlock(data={"strength": 8.0, "speed": 2.0}))
    world.attach(eid, Modifiers(entries=[])); world.attach(eid, Lifecycle(born_tick=ctx.tick_number, max_age=-1))
    world.attach(eid, FSM(state="idle", transitions=TRANS))
    log.emit(tick=ctx.tick_number, type="birth", name=nm)

def _flush(world: World, ctx: TickContext) -> None:
    bus.flush()

def _census(world: World, ctx: TickContext) -> None:
    if ctx.tick_number % 500 != 0: return
    pop = len(list(world.query(Colonist)))
    food = len(contents(world, stockpile_eid)) if world.alive(stockpile_eid) else 0
    log.emit(tick=ctx.tick_number, type="census", population=pop, food=food)

# -- Setup --------------------------------------------------------------------
def setup(seed: int = 42) -> Engine:
    global stockpile_eid
    engine = Engine(tps=20, seed=seed)
    w = engine.world; register_colony_components(w); w.register_component(Colonist)
    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Pos2D(x=10.0, y=10.0))
    w.attach(stockpile_eid, Container(items=[], capacity=60))
    grid.place(stockpile_eid, STOCKPILE)
    for i in range(8):
        eid = w.spawn(); w.attach(eid, Colonist(name=NAMES[i]))
        x, y = 2 + (i*3) % 16, 2 + (i*5) % 16
        w.attach(eid, Pos2D(x=float(x), y=float(y))); grid.place(eid, (x, y))
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", 80.0, 100.0, 1.0, 20.0)
        NeedHelper.add(ns, "fatigue", 90.0, 100.0, 0.6, 20.0)
        w.attach(eid, ns)
        w.attach(eid, StatBlock(data={"strength": 8.0 + i%4, "speed": 2.0 + i%3}))
        w.attach(eid, Modifiers(entries=[])); w.attach(eid, Lifecycle(born_tick=0, max_age=-1))
        w.attach(eid, FSM(state="idle", transitions=TRANS))
    sched.define_cycle(CycleDef(name="seasons", phases=[
        ("spring", 500), ("summer", 500), ("autumn", 500), ("winter", 500)]))
    sched.define(EventDef("cold_snap", (80,150), cooldown=200, probability=0.003, conditions=["is_winter"]))
    sched.define(EventDef("heat_wave", (60,120), cooldown=200, probability=0.002, conditions=["is_summer"]))
    sched.define(EventDef("bountiful_harvest", (100,200), cooldown=300, probability=0.004, conditions=["is_autumn"]))
    sched.define(EventDef("raid", (30,60), cooldown=500, probability=0.001))
    sched.define(EventDef("plague", (100,200), cooldown=1000, probability=0.0004))
    engine.add_system(make_event_system(sched, eguards, on_start=_ev_start, on_end=_ev_end, on_tick=_ev_tick))
    engine.add_system(make_timer_system(on_fire=_on_fire))
    engine.add_system(make_fsm_system(guards=fg, on_transition=_on_trans))
    engine.add_system(make_need_decay_system(on_zero=_on_zero))
    engine.add_system(make_modifier_tick_system())
    engine.add_system(make_lifecycle_system())
    engine.add_system(_birth); engine.add_system(make_spatial_cleanup_system(grid))
    engine.add_system(_flush); engine.add_system(_census)
    return engine

# -- Chronicle ----------------------------------------------------------------
def _season_at(tick: int, changes: list[tuple[int, str]]) -> str:
    """Return the season name active at *tick* using logged season_change events."""
    result = "spring"  # default before first change
    for t, s in changes:
        if t > tick:
            break
        result = s
    return result


def chronicle(seed: int) -> None:
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

    # Summary stats
    deaths = log.query(type="death")
    births = log.query(type="birth")
    builds = log.query(type="build_done")
    cc: dict[str, int] = {}
    for d in deaths:
        c = d.data.get("cause", "unknown"); cc[c] = cc.get(c, 0) + 1
    wc: dict[str, int] = {}
    for ev in log.query(type="event_start"):
        en = ev.data.get("event", "")
        if en in W_EVENTS:
            wc[en] = wc.get(en, 0) + 1

    # Determine actual season order from transitions
    years = TOTAL // TICKS_YEAR
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

# -- Main ---------------------------------------------------------------------
def main() -> None:
    seed = 42
    print(f"=== Chronicle demo (seed={seed}, {TOTAL} ticks) ===")
    engine = setup(seed)
    engine.run(TOTAL)
    chronicle(seed)

if __name__ == "__main__":
    main()
