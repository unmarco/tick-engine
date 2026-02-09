"""Terrain definitions and color mapping."""
from tick_atlas import CellDef

# "void" default so matches() works on every explicitly-set cell
VOID = CellDef(name="void", passable=False)

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=3.0, properties={"trees": True})
WATER = CellDef(name="water", passable=False)
STONE = CellDef(name="stone", properties={"rocky": True})
SAND = CellDef(name="sand")

ALL_TERRAIN = [GRASS, FOREST, WATER, STONE, SAND]

TERRAIN_COLORS: dict[str, tuple[int, int, int]] = {
    "void": (20, 20, 20),
    "grass": (76, 153, 0),
    "forest": (34, 100, 34),
    "water": (51, 119, 204),
    "stone": (140, 140, 140),
    "sand": (210, 190, 130),
}
