"""Tests for tick-atlas integration in tick-colony."""

from tick import Engine
from tick_colony import (
    CellDef,
    CellMap,
    Grid2D,
    Pos2D,
    ColonySnapshot,
    pathfind,
    register_colony_components,
)


class TestAtlasIntegration:
    """Test tick-atlas re-exports and colony integration."""

    def test_celldef_and_cellmap_importable(self):
        """CellDef and CellMap importable from tick_colony."""
        grass = CellDef(name="grass")
        cells = CellMap(default=grass)
        assert cells.default == grass
        assert cells.at((0, 0)) == grass

    def test_cellmap_pathfind_avoids_impassable(self):
        """CellMap + pathfind integration -- path avoids impassable cells."""
        grass = CellDef(name="grass")
        water = CellDef(name="water", passable=False)

        grid = Grid2D(10, 10)
        cells = CellMap(default=grass)

        # Block a wall of water across the direct path from (0,0) to (5,5)
        for y in range(10):
            cells.set((3, y), water)
        # Leave a gap at (3, 0) so there is a way around
        cells.set((3, 0), grass)

        # pathfind with walkable using cellmap passability
        path = pathfind(
            grid,
            start=(0, 0),
            goal=(5, 5),
            walkable=cells.passable,
        )

        assert path is not None
        # Path must go through the gap, not through any water cell
        for coord in path:
            assert cells.passable(coord), f"Path went through impassable cell at {coord}"
        assert path[0] == (0, 0)
        assert path[-1] == (5, 5)

    def test_cellmap_snapshot_roundtrip_via_colony_snapshot(self):
        """CellMap snapshot roundtrip via ColonySnapshot."""
        grass = CellDef(name="grass")
        forest = CellDef(name="forest", move_cost=2.0)
        water = CellDef(name="water", passable=False)

        cells = CellMap(default=grass)
        cells.register(forest)
        cells.register(water)
        cells.set((5, 5), forest)
        cells.set((3, 3), water)

        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        snapper = ColonySnapshot(cellmap=cells)
        data = snapper.snapshot(engine)
        assert "cellmap" in data["colony"]

        # Restore into fresh engine
        engine2 = Engine(tps=20, seed=42)
        cells2 = CellMap(default=grass)
        cells2.register(forest)
        cells2.register(water)
        snapper2 = ColonySnapshot(cellmap=cells2)
        snapper2.restore(engine2, data)

        # Verify cells2 has forest at (5,5) and water at (3,3)
        assert cells2.at((5, 5)) == forest
        assert cells2.at((3, 3)) == water
        assert cells2.at((0, 0)) == grass  # default unchanged

    def test_colony_snapshot_without_cellmap(self):
        """ColonySnapshot without cellmap parameter still works (backwards compat)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        eid = world.spawn()
        world.attach(eid, Pos2D(x=5.0, y=7.0))

        snapper = ColonySnapshot()
        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert "cellmap" not in snapshot["colony"]

        # Restore should work without error
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot()
        snapper2.restore(engine2, snapshot)

        assert engine2.world.alive(eid)

    def test_cellmap_matches_for_placement_validation(self):
        """cellmap.matches() for entity placement validation."""
        void = CellDef(name="void")
        grass = CellDef(name="grass", properties={"fertile": True})
        stone = CellDef(name="stone", properties={"fertile": False})

        cells = CellMap(default=void)
        cells.register(grass)
        cells.register(stone)
        cells.set((5, 5), grass)
        cells.set((3, 3), stone)

        # matches checks terrain name
        assert cells.matches((5, 5), {"terrain": "grass"})
        assert not cells.matches((3, 3), {"terrain": "grass"})
        assert cells.matches((3, 3), {"terrain": "stone"})

        # matches checks properties
        assert cells.matches((5, 5), {"fertile": True})
        assert cells.matches((3, 3), {"fertile": False})
        assert not cells.matches((3, 3), {"fertile": True})

        # Default (sparse) cells return False for matches()
        assert not cells.matches((0, 0), {"terrain": "void"})
