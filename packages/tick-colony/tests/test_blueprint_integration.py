"""Integration tests for BlueprintRegistry with colony components."""

import json
import pytest
from tick import Engine
from tick_colony import (
    Pos2D, Timer, FSM, NeedSet, NeedHelper, StatBlock, Modifiers, Lifecycle,
    BlueprintRegistry, register_colony_components,
)


class TestBlueprintIntegration:
    """Test BlueprintRegistry recipes, spawn with overrides, and component registration."""

    def test_define_and_spawn_basic(self):
        """Define a blueprint with Pos2D and NeedSet, spawn entity."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        registry = BlueprintRegistry()

        # Define blueprint
        recipe = {
            "tick_spatial.types.Pos2D": {"x": 5.0, "y": 10.0},
            "tick_colony.needs.NeedSet": {"data": {"hunger": [100.0, 100.0, 2.0, 20.0]}},
        }
        registry.define("basic_entity", recipe)

        # Spawn entity
        e1 = registry.spawn(world, "basic_entity")

        # Verify components attached
        assert world.has(e1, Pos2D)
        assert world.has(e1, NeedSet)

        pos = world.get(e1, Pos2D)
        assert pos.x == 5.0
        assert pos.y == 10.0

        need_set = world.get(e1, NeedSet)
        assert "hunger" in need_set.data
        assert NeedHelper.get_value(need_set, "hunger") == 100.0

    def test_spawn_with_overrides(self):
        """Spawn blueprint with override values."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        registry = BlueprintRegistry()

        # Define blueprint with default position
        recipe = {
            "tick_spatial.types.Pos2D": {"x": 0.0, "y": 0.0},
        }
        registry.define("positioned_entity", recipe)

        # Spawn with override
        e1 = registry.spawn(world, "positioned_entity", overrides={
            "tick_spatial.types.Pos2D": {"x": 5.0, "y": 7.0}
        })

        # Verify overridden values
        pos = world.get(e1, Pos2D)
        assert pos.x == 5.0
        assert pos.y == 7.0

    def test_full_colonist_blueprint(self):
        """Define a full colonist blueprint with all major components."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        registry = BlueprintRegistry()

        # Define full colonist recipe
        recipe = {
            "tick_spatial.types.Pos2D": {"x": 10.0, "y": 15.0},
            "tick_colony.needs.NeedSet": {
                "data": {
                    "hunger": [100.0, 100.0, 2.0, 20.0],
                    "energy": [100.0, 100.0, 1.0, 20.0],
                }
            },
            "tick_colony.stats.StatBlock": {
                "data": {"strength": 10.0, "speed": 5.0}
            },
            "tick_colony.stats.Modifiers": {
                "entries": []
            },
            "tick_colony.lifecycle.Lifecycle": {
                "born_tick": 0,
                "max_age": 100,
            },
            "tick_fsm.components.FSM": {
                "state": "idle",
                "transitions": {"idle": [["always", "working"]]},
            },
        }
        registry.define("colonist", recipe)

        # Spawn colonist
        e1 = registry.spawn(world, "colonist")

        # Verify all components present
        assert world.has(e1, Pos2D)
        assert world.has(e1, NeedSet)
        assert world.has(e1, StatBlock)
        assert world.has(e1, Modifiers)
        assert world.has(e1, Lifecycle)
        assert world.has(e1, FSM)

        # Verify some data
        pos = world.get(e1, Pos2D)
        assert pos.x == 10.0

        fsm = world.get(e1, FSM)
        assert fsm.state == "idle"

        lifecycle = world.get(e1, Lifecycle)
        assert lifecycle.max_age == 100

    def test_spawn_multiple_from_same_blueprint(self):
        """Spawn multiple entities from same blueprint with different overrides."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        registry = BlueprintRegistry()

        # Define blueprint
        recipe = {
            "tick_spatial.types.Pos2D": {"x": 0.0, "y": 0.0},
            "tick_colony.stats.StatBlock": {"data": {"strength": 5.0}},
        }
        registry.define("soldier", recipe)

        # Spawn 3 entities with different positions and stats
        e1 = registry.spawn(world, "soldier", overrides={
            "tick_spatial.types.Pos2D": {"x": 10.0, "y": 10.0},
            "tick_colony.stats.StatBlock": {"data": {"strength": 8.0}},
        })
        e2 = registry.spawn(world, "soldier", overrides={
            "tick_spatial.types.Pos2D": {"x": 20.0, "y": 20.0},
            "tick_colony.stats.StatBlock": {"data": {"strength": 6.0}},
        })
        e3 = registry.spawn(world, "soldier", overrides={
            "tick_spatial.types.Pos2D": {"x": 30.0, "y": 30.0},
            "tick_colony.stats.StatBlock": {"data": {"strength": 7.0}},
        })

        # Verify independent state
        pos1 = world.get(e1, Pos2D)
        stats1 = world.get(e1, StatBlock)
        assert pos1.x == 10.0
        assert stats1.data["strength"] == 8.0

        pos2 = world.get(e2, Pos2D)
        stats2 = world.get(e2, StatBlock)
        assert pos2.x == 20.0
        assert stats2.data["strength"] == 6.0

        pos3 = world.get(e3, Pos2D)
        stats3 = world.get(e3, StatBlock)
        assert pos3.x == 30.0
        assert stats3.data["strength"] == 7.0

    def test_register_colony_components_enables_blueprints(self):
        """register_colony_components() registers all types needed for blueprints."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Register components
        register_colony_components(world)

        # Verify types in registry
        assert "tick_spatial.types.Pos2D" in world._registry
        assert "tick_schedule.components.Timer" in world._registry
        assert "tick_fsm.components.FSM" in world._registry
        assert "tick_colony.needs.NeedSet" in world._registry
        assert "tick_colony.stats.StatBlock" in world._registry
        assert "tick_colony.stats.Modifiers" in world._registry
        assert "tick_colony.containment.Container" in world._registry
        assert "tick_colony.containment.ContainedBy" in world._registry
        assert "tick_colony.lifecycle.Lifecycle" in world._registry

        # Now blueprints should work
        registry = BlueprintRegistry()
        recipe = {
            "tick_spatial.types.Pos2D": {"x": 1.0, "y": 2.0},
            "tick_colony.needs.NeedSet": {"data": {}},
        }
        registry.define("test_entity", recipe)

        # Should not raise
        e1 = registry.spawn(world, "test_entity")
        assert world.has(e1, Pos2D)
        assert world.has(e1, NeedSet)

    def test_blueprint_recipe_is_json_compatible(self):
        """Blueprint recipes are JSON-serializable."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        registry = BlueprintRegistry()

        # Define blueprints
        recipe1 = {
            "tick_spatial.types.Pos2D": {"x": 5.0, "y": 10.0},
            "tick_colony.needs.NeedSet": {"data": {"hunger": [100.0, 100.0, 2.0, 20.0]}},
        }
        recipe2 = {
            "tick_fsm.components.FSM": {
                "state": "idle",
                "transitions": {"idle": [["always", "working"]], "working": [["tired", "resting"]]},
            },
            "tick_colony.stats.StatBlock": {"data": {"strength": 10.0}},
        }
        registry.define("entity1", recipe1)
        registry.define("entity2", recipe2)

        # Get recipes
        all_recipes = registry.recipes()

        # Verify JSON-serializable
        json_str = json.dumps(all_recipes)
        assert isinstance(json_str, str)

        # Verify round-trip
        restored = json.loads(json_str)
        assert restored["entity1"]["tick_spatial.types.Pos2D"]["x"] == 5.0
        assert restored["entity2"]["tick_fsm.components.FSM"]["state"] == "idle"
