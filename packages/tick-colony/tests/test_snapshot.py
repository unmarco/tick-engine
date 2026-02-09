"""Tests for tick_colony.snapshot module - framework snapshot coordinator."""

import json
import pytest
from tick_colony import (
    Grid2D, Pos2D, EventLog, ColonySnapshot,
    CellDef, CellMap, AbilityDef, AbilityManager, ResourceDef, ResourceRegistry,
    Inventory, InventoryHelper, register_colony_components,
    EventScheduler,
)
from tick import Engine


class TestColonySnapshot:
    def test_snapshot_with_grid_only(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(30, 20)
        snapper = ColonySnapshot(grid=grid)

        e1 = world.spawn()
        world.attach(e1, Pos2D(x=5.0, y=10.0))
        grid.rebuild(world)

        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert "grid" in snapshot["colony"]
        assert snapshot["colony"]["grid"]["width"] == 30
        assert snapshot["colony"]["grid"]["height"] == 20

    def test_snapshot_with_eventlog_only(self):
        engine = Engine(tps=20, seed=42)

        event_log = EventLog()
        event_log.emit(tick=1, type="spawn", entity_id=1)
        event_log.emit(tick=2, type="move", x=5, y=10)

        snapper = ColonySnapshot(event_log=event_log)

        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert "events" in snapshot["colony"]
        assert len(snapshot["colony"]["events"]) == 2

    def test_snapshot_with_grid_and_eventlog(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(40, 30)
        event_log = EventLog()
        event_log.emit(tick=1, type="test", data=123)

        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        e1 = world.spawn()
        world.attach(e1, Pos2D(x=10.0, y=15.0))
        grid.rebuild(world)

        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert snapshot["colony"]["grid"]["width"] == 40
        assert snapshot["colony"]["grid"]["height"] == 30
        assert len(snapshot["colony"]["events"]) == 1

    def test_snapshot_includes_engine_snapshot(self):
        engine = Engine(tps=20, seed=42)
        grid = Grid2D(10, 10)
        snapper = ColonySnapshot(grid=grid)

        snapshot = snapper.snapshot(engine)

        # Verify engine snapshot fields are present
        assert "version" in snapshot
        assert "tick_number" in snapshot
        assert "tps" in snapshot
        assert "seed" in snapshot
        assert "world" in snapshot

    def test_snapshot_is_json_compatible(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(10, 10)
        event_log = EventLog()
        event_log.emit(tick=1, type="test", value=42)

        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        e1 = world.spawn()
        world.attach(e1, Pos2D(x=5.0, y=5.0))
        grid.rebuild(world)

        snapshot = snapper.snapshot(engine)

        # Should not raise
        json_str = json.dumps(snapshot)
        assert json_str is not None

    def test_restore_rebuilds_grid_from_positions(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(20, 20)
        snapper = ColonySnapshot(grid=grid)

        # Create entities with positions
        e1 = world.spawn()
        e2 = world.spawn()
        world.attach(e1, Pos2D(x=5.0, y=7.0))
        world.attach(e2, Pos2D(x=10.0, y=12.0))

        # Take snapshot
        snapshot = snapper.snapshot(engine)

        # Create new engine and grid
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid2D(20, 20)
        snapper2 = ColonySnapshot(grid=grid2)

        # Restore
        snapper2.restore(engine2, snapshot)

        # Verify grid was rebuilt
        assert grid2.position_of(e1) == (5, 7)
        assert grid2.position_of(e2) == (10, 12)

    def test_restore_restores_event_log(self):
        engine = Engine(tps=20, seed=42)

        event_log = EventLog()
        event_log.emit(tick=1, type="spawn", entity_id=1)
        event_log.emit(tick=5, type="attack", attacker=1, target=2)

        snapper = ColonySnapshot(event_log=event_log)

        snapshot = snapper.snapshot(engine)

        # Create new engine and event log
        engine2 = Engine(tps=20, seed=42)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(event_log=event_log2)

        snapper2.restore(engine2, snapshot)

        # Verify event log restored
        assert len(event_log2) == 2
        events = event_log2.query()
        assert events[0].tick == 1
        assert events[0].type == "spawn"
        assert events[1].tick == 5
        assert events[1].type == "attack"

    def test_roundtrip_snapshot_restore(self):
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world

        grid1 = Grid2D(15, 15)
        event_log1 = EventLog()
        snapper1 = ColonySnapshot(grid=grid1, event_log=event_log1)

        # Create some state
        e1 = world1.spawn()
        e2 = world1.spawn()
        world1.attach(e1, Pos2D(x=3.0, y=4.0))
        world1.attach(e2, Pos2D(x=7.0, y=9.0))
        grid1.rebuild(world1)

        event_log1.emit(tick=1, type="spawn", entity_id=e1)
        event_log1.emit(tick=2, type="spawn", entity_id=e2)

        # Snapshot
        snapshot = snapper1.snapshot(engine1)

        # Restore to new engine
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid2D(15, 15)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        snapper2.restore(engine2, snapshot)

        # Verify state matches
        world2 = engine2.world
        assert world2.alive(e1)
        assert world2.alive(e2)

        pos1 = world2.get(e1, Pos2D)
        pos2 = world2.get(e2, Pos2D)
        assert (pos1.x, pos1.y) == (3.0, 4.0)
        assert (pos2.x, pos2.y) == (7.0, 9.0)

        assert grid2.position_of(e1) == (3, 4)
        assert grid2.position_of(e2) == (7, 9)

        assert len(event_log2) == 2

    def test_snapshot_without_grid_or_eventlog(self):
        engine = Engine(tps=20, seed=42)
        snapper = ColonySnapshot()

        snapshot = snapper.snapshot(engine)

        # Should still have colony section
        assert "colony" in snapshot
        # But grid and events should be minimal or absent
        colony_data = snapshot["colony"]
        assert "grid" not in colony_data or colony_data["grid"] is None
        assert "events" not in colony_data or colony_data["events"] == []

    def test_restore_with_no_grid(self):
        engine1 = Engine(tps=20, seed=42)
        event_log1 = EventLog()
        event_log1.emit(tick=1, type="test")

        snapper1 = ColonySnapshot(event_log=event_log1)
        snapshot = snapper1.snapshot(engine1)

        engine2 = Engine(tps=20, seed=42)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(event_log=event_log2)

        snapper2.restore(engine2, snapshot)

        assert len(event_log2) == 1

    def test_restore_with_no_eventlog(self):
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world

        grid1 = Grid2D(10, 10)
        snapper1 = ColonySnapshot(grid=grid1)

        e1 = world1.spawn()
        world1.attach(e1, Pos2D(x=2.0, y=3.0))
        grid1.rebuild(world1)

        snapshot = snapper1.snapshot(engine1)

        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid2D(10, 10)
        snapper2 = ColonySnapshot(grid=grid2)

        snapper2.restore(engine2, snapshot)

        assert grid2.position_of(e1) == (2, 3)

    def test_works_with_engine_snapshot_restore(self):
        """Verify compatibility with engine's snapshot/restore methods."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(10, 10)
        event_log = EventLog()
        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        # Setup state
        e1 = world.spawn()
        world.attach(e1, Pos2D(x=5.0, y=5.0))
        grid.rebuild(world)
        event_log.emit(tick=1, type="test", entity_id=e1)

        # Use ColonySnapshot for snapshot
        snapshot = snapper.snapshot(engine)

        # Engine should be able to restore its portion
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid2D(10, 10)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        # Full restore
        snapper2.restore(engine2, snapshot)

        # Verify all state restored
        assert engine2.clock.tick_number == engine.clock.tick_number
        assert engine2.seed == engine.seed
        assert grid2.position_of(e1) == (5, 5)
        assert len(event_log2) == 1

    # --- CellMap tests ---

    def test_snapshot_with_cellmap(self):
        engine = Engine(tps=20, seed=42)

        grass = CellDef(name="grass")
        forest = CellDef(name="forest", move_cost=2.0)
        water = CellDef(name="water", passable=False)

        cells = CellMap(default=grass)
        cells.set((5, 5), forest)
        cells.set((3, 7), water)

        snapper = ColonySnapshot(cellmap=cells)
        data = snapper.snapshot(engine)

        assert "colony" in data
        assert "cellmap" in data["colony"]
        cellmap_data = data["colony"]["cellmap"]
        assert cellmap_data["default"] == "grass"
        assert "5,5" in cellmap_data["cells"]
        assert cellmap_data["cells"]["5,5"] == "forest"
        assert "3,7" in cellmap_data["cells"]
        assert cellmap_data["cells"]["3,7"] == "water"

    def test_restore_with_cellmap(self):
        engine1 = Engine(tps=20, seed=42)

        grass = CellDef(name="grass")
        forest = CellDef(name="forest", move_cost=2.0)
        water = CellDef(name="water", passable=False)

        cells1 = CellMap(default=grass)
        cells1.set((5, 5), forest)
        cells1.set((3, 7), water)

        snapper1 = ColonySnapshot(cellmap=cells1)
        data = snapper1.snapshot(engine1)

        # Restore to new engine and new cellmap
        engine2 = Engine(tps=20, seed=42)
        cells2 = CellMap(default=grass)
        # Register forest and water so restore can resolve them
        cells2.register(forest)
        cells2.register(water)

        snapper2 = ColonySnapshot(cellmap=cells2)
        snapper2.restore(engine2, data)

        assert cells2.at((5, 5)) == forest
        assert cells2.at((3, 7)) == water
        assert cells2.at((0, 0)) == grass  # default for unset coords

    # --- AbilityManager tests ---

    def test_snapshot_with_ability_manager(self):
        engine = Engine(tps=20, seed=42)

        mgr = AbilityManager()
        mgr.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))

        snapper = ColonySnapshot(ability_manager=mgr)
        data = snapper.snapshot(engine)

        assert "colony" in data
        assert "ability_manager" in data["colony"]
        am_data = data["colony"]["ability_manager"]
        assert "abilities" in am_data
        assert len(am_data["abilities"]) == 1
        assert am_data["abilities"][0]["name"] == "heal"
        assert am_data["abilities"][0]["charges"] == 2

    def test_restore_with_ability_manager(self):
        engine1 = Engine(tps=20, seed=42)

        mgr1 = AbilityManager()
        heal_def = AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2)
        mgr1.define(heal_def)

        snapper1 = ColonySnapshot(ability_manager=mgr1)
        data = snapper1.snapshot(engine1)

        # Restore to new engine and new manager
        engine2 = Engine(tps=20, seed=42)
        mgr2 = AbilityManager()
        mgr2.define(heal_def)  # definitions must be registered before restore

        snapper2 = ColonySnapshot(ability_manager=mgr2)
        snapper2.restore(engine2, data)

        assert mgr2.charges("heal") == 2
        assert mgr2.cooldown_remaining("heal") == 0
        assert mgr2.time_remaining("heal") == 0

    # --- ResourceRegistry tests ---

    def test_snapshot_with_resource_registry(self):
        engine = Engine(tps=20, seed=42)

        reg = ResourceRegistry()
        reg.define(ResourceDef(name="food", max_stack=100, decay_rate=1))
        reg.define(ResourceDef(name="wood", max_stack=50))

        snapper = ColonySnapshot(resource_registry=reg)
        data = snapper.snapshot(engine)

        assert "colony" in data
        assert "resource_registry" in data["colony"]
        rr_data = data["colony"]["resource_registry"]
        assert "definitions" in rr_data
        assert "food" in rr_data["definitions"]
        assert rr_data["definitions"]["food"]["max_stack"] == 100
        assert rr_data["definitions"]["food"]["decay_rate"] == 1
        assert "wood" in rr_data["definitions"]
        assert rr_data["definitions"]["wood"]["max_stack"] == 50

    def test_restore_with_resource_registry(self):
        engine1 = Engine(tps=20, seed=42)

        reg1 = ResourceRegistry()
        reg1.define(ResourceDef(name="food", max_stack=100, decay_rate=1))
        reg1.define(ResourceDef(name="wood", max_stack=50))

        snapper1 = ColonySnapshot(resource_registry=reg1)
        data = snapper1.snapshot(engine1)

        # Restore to new engine and new registry
        engine2 = Engine(tps=20, seed=42)
        reg2 = ResourceRegistry()

        snapper2 = ColonySnapshot(resource_registry=reg2)
        snapper2.restore(engine2, data)

        assert reg2.has("food")
        assert reg2.has("wood")
        food_def = reg2.get("food")
        assert food_def.max_stack == 100
        assert food_def.decay_rate == 1
        wood_def = reg2.get("wood")
        assert wood_def.max_stack == 50

    # --- Combined / integration tests ---

    def test_snapshot_with_all_optional_params(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid2D(20, 20)
        event_log = EventLog()
        event_log.emit(tick=1, type="test")
        scheduler = EventScheduler()

        grass = CellDef(name="grass")
        cells = CellMap(default=grass)
        cells.set((1, 1), CellDef(name="stone", move_cost=3.0))

        mgr = AbilityManager()
        mgr.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))

        reg = ResourceRegistry()
        reg.define(ResourceDef(name="food", max_stack=100, decay_rate=1))

        snapper = ColonySnapshot(
            grid=grid,
            event_log=event_log,
            scheduler=scheduler,
            cellmap=cells,
            ability_manager=mgr,
            resource_registry=reg,
        )

        e1 = world.spawn()
        world.attach(e1, Pos2D(x=5.0, y=5.0))
        grid.rebuild(world)

        data = snapper.snapshot(engine)

        colony = data["colony"]
        assert "grid" in colony
        assert "events" in colony
        assert "scheduler" in colony
        assert "cellmap" in colony
        assert "ability_manager" in colony
        assert "resource_registry" in colony

    def test_register_colony_components_includes_inventory(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        register_colony_components(world)

        eid = world.spawn()
        world.attach(eid, Inventory(slots={"wood": 10}, capacity=100))

        inv = world.get(eid, Inventory)
        assert inv.slots["wood"] == 10
        assert inv.capacity == 100
