"""Tests for tick_colony.context — LLM context builder factories."""

from tick import Engine
from tick_colony.context import (
    make_resource_context,
    make_population_context,
    make_spatial_context,
    make_event_context,
    make_colony_context,
)
from tick_colony.needs import NeedSet, NeedHelper
from tick_colony.events import EventLog
from tick_colony.lifecycle import Lifecycle
from tick_fsm import FSM
from tick_resource import Inventory
from tick_spatial import Grid2D, Pos2D
from tick_atlas import CellDef, CellMap
from tick_ai.components import Blackboard


# ---------------------------------------------------------------------------
# make_resource_context
# ---------------------------------------------------------------------------


class TestMakeResourceContext:
    def test_empty_world(self):
        """No inventories produces the 'No inventories found' message."""
        engine = Engine(tps=20, seed=42)
        ctx_fn = make_resource_context()
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)
        assert "=== Resources ===" in result
        assert "No inventories found" in result

    def test_single_inventory(self):
        """Single entity with an Inventory shows totals and stockpile entry."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        inv = Inventory(slots={"wood": 30, "stone": 15}, capacity=100)
        engine.world.attach(e1, inv)

        ctx_fn = make_resource_context()
        result = ctx_fn(engine.world, e1)

        assert "=== Resources ===" in result
        assert "Colony totals:" in result
        assert "stone=15" in result
        assert "wood=30" in result
        assert "Stockpiles: 1 entities" in result
        assert f"Entity {e1}:" in result

    def test_multiple_inventories_aggregates_totals(self):
        """Multiple entities with Inventory have their totals summed."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"food": 50, "wood": 10}, capacity=200))
        engine.world.attach(e2, Inventory(slots={"food": 25, "stone": 5}, capacity=100))

        ctx_fn = make_resource_context()
        # eid argument is unused by resource context, pass any entity
        result = ctx_fn(engine.world, e1)

        assert "Colony totals:" in result
        assert "food=75" in result
        assert "wood=10" in result
        assert "stone=5" in result
        assert "Stockpiles: 2 entities" in result

    def test_resource_names_filter(self):
        """resource_names restricts which resources appear in output."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"food": 50, "wood": 10, "stone": 5}, capacity=200))

        ctx_fn = make_resource_context(resource_names=["food", "stone"])
        result = ctx_fn(engine.world, e1)

        assert "food=50" in result
        assert "stone=5" in result
        assert "wood" not in result

    def test_resource_names_filter_excludes_all(self):
        """resource_names with no matching keys produces 'No inventories found'."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"wood": 10}, capacity=200))

        ctx_fn = make_resource_context(resource_names=["gold"])
        result = ctx_fn(engine.world, e1)

        assert "No inventories found" in result

    def test_include_capacities(self):
        """include_capacities=True adds capacity info to each stockpile entry."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"food": 40, "wood": 10}, capacity=100))

        ctx_fn = make_resource_context(include_capacities=True)
        result = ctx_fn(engine.world, e1)

        # used = sum of ALL slots (40+10=50), capacity = 100
        assert "capacity: 50/100" in result

    def test_include_capacities_false_no_capacity_info(self):
        """include_capacities=False (default) omits capacity info."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"food": 40}, capacity=100))

        ctx_fn = make_resource_context()
        result = ctx_fn(engine.world, e1)

        assert "capacity:" not in result


# ---------------------------------------------------------------------------
# make_population_context
# ---------------------------------------------------------------------------


class TestMakePopulationContext:
    def test_no_entities(self):
        """Empty world shows 'Total entities: 0'."""
        engine = Engine(tps=20, seed=42)
        ctx_fn = make_population_context()
        eid = engine.world.spawn()  # observer entity, no NeedSet
        result = ctx_fn(engine.world, eid)

        assert "=== Population ===" in result
        assert "Total entities: 0" in result

    def test_with_needs(self):
        """Entities with NeedSet are counted and average need levels shown."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        e2 = engine.world.spawn()

        ns1 = NeedSet()
        NeedHelper.add(ns1, "hunger", 80.0, 100.0, 1.0, 20.0)
        ns2 = NeedSet()
        NeedHelper.add(ns2, "hunger", 40.0, 100.0, 1.0, 20.0)

        engine.world.attach(e1, ns1)
        engine.world.attach(e2, ns2)

        ctx_fn = make_population_context()
        result = ctx_fn(engine.world, e1)

        assert "Total entities: 2" in result
        assert "Need levels (avg):" in result
        # avg hunger = (80+40)/2 = 60.0
        assert "hunger=60.0" in result

    def test_with_fsm_states(self):
        """FSM state distribution is reported when include_fsm_states=True."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        engine.world.attach(e1, NeedSet())
        engine.world.attach(e2, NeedSet())
        engine.world.attach(e3, NeedSet())

        engine.world.attach(e1, FSM(state="idle", transitions={}))
        engine.world.attach(e2, FSM(state="working", transitions={}))
        engine.world.attach(e3, FSM(state="idle", transitions={}))

        ctx_fn = make_population_context(include_fsm_states=True)
        result = ctx_fn(engine.world, e1)

        assert "FSM states:" in result
        assert "idle=2" in result
        assert "working=1" in result

    def test_fsm_states_disabled(self):
        """include_fsm_states=False omits FSM state distribution."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, NeedSet())
        engine.world.attach(e1, FSM(state="idle", transitions={}))

        ctx_fn = make_population_context(include_fsm_states=False)
        result = ctx_fn(engine.world, e1)

        assert "FSM states:" not in result

    def test_critical_needs(self):
        """Entities with critical needs are counted in the Critical line."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        ns1 = NeedSet()
        NeedHelper.add(ns1, "hunger", 10.0, 100.0, 1.0, 20.0)  # critical
        ns2 = NeedSet()
        NeedHelper.add(ns2, "hunger", 80.0, 100.0, 1.0, 20.0)  # not critical
        ns3 = NeedSet()
        NeedHelper.add(ns3, "hunger", 15.0, 100.0, 1.0, 20.0)  # critical

        engine.world.attach(e1, ns1)
        engine.world.attach(e2, ns2)
        engine.world.attach(e3, ns3)

        ctx_fn = make_population_context()
        result = ctx_fn(engine.world, e1)

        assert "Critical:" in result
        assert "2 hunger" in result

    def test_no_critical_needs_omits_critical_line(self):
        """When no needs are critical, the Critical line is omitted."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()

        ns = NeedSet()
        NeedHelper.add(ns, "hunger", 80.0, 100.0, 1.0, 20.0)
        engine.world.attach(e1, ns)

        ctx_fn = make_population_context()
        result = ctx_fn(engine.world, e1)

        assert "Critical:" not in result

    def test_include_lifecycle(self):
        """include_lifecycle=True reports mortal entity count and avg max_age."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        # e1 and e2 are mortal, e3 is immortal
        engine.world.attach(e1, Lifecycle(born_tick=0, max_age=100))
        engine.world.attach(e2, Lifecycle(born_tick=0, max_age=200))
        engine.world.attach(e3, Lifecycle(born_tick=0, max_age=-1))

        ctx_fn = make_population_context(include_lifecycle=True)
        result = ctx_fn(engine.world, e1)

        assert "Lifecycle:" in result
        assert "2 mortal" in result
        assert "avg max_age=150" in result

    def test_include_lifecycle_false(self):
        """include_lifecycle=False (default) omits lifecycle info."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Lifecycle(born_tick=0, max_age=100))

        ctx_fn = make_population_context(include_lifecycle=False)
        result = ctx_fn(engine.world, e1)

        assert "Lifecycle:" not in result

    def test_needs_disabled(self):
        """include_needs=False omits need level and critical info."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", 10.0, 100.0, 1.0, 20.0)
        engine.world.attach(e1, ns)

        ctx_fn = make_population_context(include_needs=False)
        result = ctx_fn(engine.world, e1)

        assert "Need levels" not in result
        assert "Critical:" not in result


# ---------------------------------------------------------------------------
# make_spatial_context
# ---------------------------------------------------------------------------


class TestMakeSpatialContext:
    def test_entity_position_reported(self):
        """Entity placed on grid has its position reported."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        grid.place(e1, (3, 4))

        ctx_fn = make_spatial_context(grid)
        result = ctx_fn(engine.world, e1)

        assert "=== Spatial ===" in result
        assert "Position: (3, 4)" in result

    def test_unknown_position(self):
        """Entity not on the grid produces 'Position: unknown'."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        # e1 not placed on grid

        ctx_fn = make_spatial_context(grid)
        result = ctx_fn(engine.world, e1)

        assert "Position: unknown" in result
        # Should NOT contain Nearby or coord group lines
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + position: unknown

    def test_nearby_entities_all(self):
        """With radius=-1 (default), all tracked entities are listed as nearby."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        grid.place(e1, (0, 0))
        grid.place(e2, (5, 5))
        grid.place(e3, (9, 9))

        ctx_fn = make_spatial_context(grid)
        result = ctx_fn(engine.world, e1)

        assert "Nearby: 2 entities" in result
        assert "(5, 5):" in result
        assert "(9, 9):" in result
        # e1's own position should NOT appear in nearby
        assert "(0, 0):" not in result

    def test_nearby_entities_with_radius(self):
        """With a finite radius, only entities within range are reported."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(20, 20)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        grid.place(e1, (5, 5))
        grid.place(e2, (6, 5))  # within radius=2
        grid.place(e3, (15, 15))  # far away

        ctx_fn = make_spatial_context(grid, radius=2)
        result = ctx_fn(engine.world, e1)

        assert "Nearby: 1 entities" in result
        assert "(6, 5):" in result
        assert "(15, 15)" not in result

    def test_with_cellmap(self):
        """CellMap terrain name is appended to coordinate entries."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        grass = CellDef(name="grass")
        forest = CellDef(name="forest")
        cellmap = CellMap(default=grass)
        cellmap.set((3, 3), forest)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()

        grid.place(e1, (0, 0))
        grid.place(e2, (3, 3))

        ctx_fn = make_spatial_context(grid, cellmap=cellmap)
        result = ctx_fn(engine.world, e1)

        # e2 is at (3,3) which is forest
        assert "forest" in result

    def test_grouped_entities_at_same_coord(self):
        """Multiple entities at the same coordinate are grouped together."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        grid.place(e1, (0, 0))
        grid.place(e2, (5, 5))
        grid.place(e3, (5, 5))

        ctx_fn = make_spatial_context(grid)
        result = ctx_fn(engine.world, e1)

        assert "Nearby: 2 entities" in result
        assert "(5, 5): 2 entities" in result

    def test_single_entity_at_coord_uses_singular(self):
        """Single entity at a coordinate uses 'entity' (singular)."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()

        grid.place(e1, (0, 0))
        grid.place(e2, (3, 3))

        ctx_fn = make_spatial_context(grid)
        result = ctx_fn(engine.world, e1)

        assert "1 entity" in result


# ---------------------------------------------------------------------------
# make_event_context
# ---------------------------------------------------------------------------


class TestMakeEventContext:
    def test_no_events(self):
        """Empty event log produces 'No recent events'."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()

        ctx_fn = make_event_context(log)
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)

        assert "=== Recent Events ===" in result
        assert "No recent events." in result

    def test_some_events(self):
        """Events are listed with tick, type, and data."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()
        log.emit(1, "birth", name="Alice")
        log.emit(3, "harvest", resource="wood", amount=5)

        ctx_fn = make_event_context(log)
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)

        assert "[Tick 1] birth:" in result
        assert "name=Alice" in result
        assert "[Tick 3] harvest:" in result
        assert "amount=5" in result
        assert "resource=wood" in result

    def test_event_types_filter(self):
        """event_types restricts which event types appear in output."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()
        log.emit(1, "birth", name="Alice")
        log.emit(2, "death", name="Bob")
        log.emit(3, "harvest", resource="wood", amount=5)

        ctx_fn = make_event_context(log, event_types=["birth", "harvest"])
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)

        assert "birth" in result
        assert "harvest" in result
        assert "death" not in result

    def test_max_events_limit(self):
        """max_events limits the number of events shown (most recent)."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()
        for i in range(30):
            log.emit(i, "tick_event", num=i)

        ctx_fn = make_event_context(log, max_events=5)
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)

        # Should contain last 5 events (ticks 25-29)
        assert "[Tick 25]" in result
        assert "[Tick 29]" in result
        # Should NOT contain earlier events
        assert "[Tick 0]" not in result
        assert "[Tick 24]" not in result

    def test_event_types_filter_produces_empty_when_no_match(self):
        """event_types filter that matches nothing produces 'No recent events'."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()
        log.emit(1, "birth", name="Alice")

        ctx_fn = make_event_context(log, event_types=["combat"])
        eid = engine.world.spawn()
        result = ctx_fn(engine.world, eid)

        assert "No recent events." in result


# ---------------------------------------------------------------------------
# make_colony_context
# ---------------------------------------------------------------------------


class TestMakeColonyContext:
    def test_combines_resource_and_population(self):
        """Colony context always includes resource and population sections."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"food": 20}, capacity=100))
        ns = NeedSet()
        NeedHelper.add(ns, "hunger", 70.0, 100.0, 1.0, 20.0)
        engine.world.attach(e1, ns)

        ctx_fn = make_colony_context()
        result = ctx_fn(engine.world, e1)

        assert "=== Resources ===" in result
        assert "=== Population ===" in result
        assert "food=20" in result
        assert "Total entities: 1" in result

    def test_with_grid_includes_spatial(self):
        """Passing a grid enables the spatial section."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)

        e1 = engine.world.spawn()
        grid.place(e1, (2, 3))

        ctx_fn = make_colony_context(grid=grid)
        result = ctx_fn(engine.world, e1)

        assert "=== Spatial ===" in result
        assert "Position: (2, 3)" in result

    def test_with_event_log_includes_events(self):
        """Passing an event_log enables the events section."""
        engine = Engine(tps=20, seed=42)
        log = EventLog()
        log.emit(5, "raid", damage=10)

        e1 = engine.world.spawn()
        ctx_fn = make_colony_context(event_log=log, max_events=10)
        result = ctx_fn(engine.world, e1)

        assert "=== Recent Events ===" in result
        assert "[Tick 5] raid:" in result
        assert "damage=10" in result

    def test_no_optional_objects(self):
        """With no grid and no event_log, only resource and population appear."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()

        ctx_fn = make_colony_context()
        result = ctx_fn(engine.world, e1)

        assert "=== Resources ===" in result
        assert "=== Population ===" in result
        assert "=== Spatial ===" not in result
        assert "=== Recent Events ===" not in result

    def test_include_strategy(self):
        """include_strategy=True reads from Blackboard.data['strategy']."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(
            e1, Blackboard(data={"strategy": {"focus": "expansion", "priority": "food"}})
        )

        ctx_fn = make_colony_context(include_strategy=True)
        result = ctx_fn(engine.world, e1)

        assert "=== Current Strategy ===" in result
        assert "expansion" in result
        assert "food" in result

    def test_include_strategy_no_blackboard(self):
        """include_strategy=True with no Blackboard on entity omits strategy section."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()

        ctx_fn = make_colony_context(include_strategy=True)
        result = ctx_fn(engine.world, e1)

        assert "=== Current Strategy ===" not in result

    def test_include_strategy_empty_strategy(self):
        """Blackboard with empty/falsy strategy omits strategy section."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(e1, Blackboard(data={"strategy": {}}))

        ctx_fn = make_colony_context(include_strategy=True)
        result = ctx_fn(engine.world, e1)

        assert "=== Current Strategy ===" not in result

    def test_include_strategy_false(self):
        """include_strategy=False skips strategy even if Blackboard exists."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(
            e1, Blackboard(data={"strategy": {"focus": "defense"}})
        )

        ctx_fn = make_colony_context(include_strategy=False)
        result = ctx_fn(engine.world, e1)

        assert "=== Current Strategy ===" not in result

    def test_sections_separated_by_blank_lines(self):
        """Sections in combined context are separated by double newlines."""
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)
        log = EventLog()
        log.emit(1, "test", x=1)

        e1 = engine.world.spawn()
        grid.place(e1, (0, 0))
        engine.world.attach(e1, Inventory(slots={"food": 5}, capacity=50))

        ctx_fn = make_colony_context(grid=grid, event_log=log)
        result = ctx_fn(engine.world, e1)

        # Sections are joined by "\n\n"
        assert "\n\n" in result
        sections = result.split("\n\n")
        # Should have: Resources, Population, Spatial, Recent Events = 4 sections
        assert len(sections) == 4

    def test_resource_names_forwarded(self):
        """resource_names parameter filters resources in combined context."""
        engine = Engine(tps=20, seed=42)
        e1 = engine.world.spawn()
        engine.world.attach(
            e1, Inventory(slots={"food": 30, "wood": 10, "stone": 5}, capacity=200)
        )

        ctx_fn = make_colony_context(resource_names=["food"])
        result = ctx_fn(engine.world, e1)

        assert "food=30" in result
        assert "wood" not in result
        assert "stone" not in result
