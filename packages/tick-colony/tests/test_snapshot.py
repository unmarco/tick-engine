"""Tests for tick_colony.snapshot module - framework snapshot coordinator."""

import json
import pytest
from tick_colony import Grid, Position, EventLog, ColonySnapshot
from tick import Engine


class TestColonySnapshot:
    def test_snapshot_with_grid_only(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(30, 20)
        snapper = ColonySnapshot(grid=grid)

        e1 = world.spawn()
        world.attach(e1, Position(x=5, y=10))
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

        grid = Grid(40, 30)
        event_log = EventLog()
        event_log.emit(tick=1, type="test", data=123)

        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        e1 = world.spawn()
        world.attach(e1, Position(x=10, y=15))
        grid.rebuild(world)

        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert snapshot["colony"]["grid"]["width"] == 40
        assert snapshot["colony"]["grid"]["height"] == 30
        assert len(snapshot["colony"]["events"]) == 1

    def test_snapshot_includes_engine_snapshot(self):
        engine = Engine(tps=20, seed=42)
        grid = Grid(10, 10)
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

        grid = Grid(10, 10)
        event_log = EventLog()
        event_log.emit(tick=1, type="test", value=42)

        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        e1 = world.spawn()
        world.attach(e1, Position(x=5, y=5))
        grid.rebuild(world)

        snapshot = snapper.snapshot(engine)

        # Should not raise
        json_str = json.dumps(snapshot)
        assert json_str is not None

    def test_restore_rebuilds_grid_from_positions(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(20, 20)
        snapper = ColonySnapshot(grid=grid)

        # Create entities with positions
        e1 = world.spawn()
        e2 = world.spawn()
        world.attach(e1, Position(x=5, y=7))
        world.attach(e2, Position(x=10, y=12))

        # Take snapshot
        snapshot = snapper.snapshot(engine)

        # Create new engine and grid
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid(20, 20)
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

        grid1 = Grid(15, 15)
        event_log1 = EventLog()
        snapper1 = ColonySnapshot(grid=grid1, event_log=event_log1)

        # Create some state
        e1 = world1.spawn()
        e2 = world1.spawn()
        world1.attach(e1, Position(x=3, y=4))
        world1.attach(e2, Position(x=7, y=9))
        grid1.rebuild(world1)

        event_log1.emit(tick=1, type="spawn", entity_id=e1)
        event_log1.emit(tick=2, type="spawn", entity_id=e2)

        # Snapshot
        snapshot = snapper1.snapshot(engine1)

        # Restore to new engine
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid(15, 15)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        snapper2.restore(engine2, snapshot)

        # Verify state matches
        world2 = engine2.world
        assert world2.alive(e1)
        assert world2.alive(e2)

        pos1 = world2.get(e1, Position)
        pos2 = world2.get(e2, Position)
        assert (pos1.x, pos1.y) == (3, 4)
        assert (pos2.x, pos2.y) == (7, 9)

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

        grid1 = Grid(10, 10)
        snapper1 = ColonySnapshot(grid=grid1)

        e1 = world1.spawn()
        world1.attach(e1, Position(x=2, y=3))
        grid1.rebuild(world1)

        snapshot = snapper1.snapshot(engine1)

        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid(10, 10)
        snapper2 = ColonySnapshot(grid=grid2)

        snapper2.restore(engine2, snapshot)

        assert grid2.position_of(e1) == (2, 3)

    def test_works_with_engine_snapshot_restore(self):
        """Verify compatibility with engine's snapshot/restore methods."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(10, 10)
        event_log = EventLog()
        snapper = ColonySnapshot(grid=grid, event_log=event_log)

        # Setup state
        e1 = world.spawn()
        world.attach(e1, Position(x=5, y=5))
        grid.rebuild(world)
        event_log.emit(tick=1, type="test", entity_id=e1)

        # Use ColonySnapshot for snapshot
        snapshot = snapper.snapshot(engine)

        # Engine should be able to restore its portion
        engine2 = Engine(tps=20, seed=42)
        grid2 = Grid(10, 10)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        # Full restore
        snapper2.restore(engine2, snapshot)

        # Verify all state restored
        assert engine2.clock.tick_number == engine.clock.tick_number
        assert engine2.seed == engine.seed
        assert grid2.position_of(e1) == (5, 5)
        assert len(event_log2) == 1
