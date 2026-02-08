"""Tests for BlueprintRegistry."""
from __future__ import annotations

import pytest
from dataclasses import dataclass
from tick import Engine
from tick_blueprint import BlueprintRegistry


# Test components
@dataclass
class Pos:
    """Position component for testing."""
    x: float
    y: float


@dataclass
class Health:
    """Health component for testing."""
    value: int
    max_value: int


@dataclass
class Name:
    """Name component for testing."""
    label: str


@dataclass
class Velocity:
    """Velocity component for testing."""
    dx: float
    dy: float


# Helper function to get registry key
def get_key(ctype: type) -> str:
    """Get the registry key for a component type."""
    return f"{ctype.__module__}.{ctype.__qualname__}"


# Test fixtures
@pytest.fixture
def engine():
    """Create a fresh engine for each test."""
    return Engine(tps=20, seed=42)


@pytest.fixture
def world(engine):
    """Get world from engine and register test components."""
    w = engine.world
    w.register_component(Pos)
    w.register_component(Health)
    w.register_component(Name)
    w.register_component(Velocity)
    return w


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    return BlueprintRegistry()


# Registry basics tests
class TestRegistryBasics:
    """Test basic registry operations."""

    def test_define_and_has(self, registry):
        """Test 1: define a recipe, has returns True."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("player", recipe)
        assert registry.has("player") is True

    def test_has_returns_false_for_undefined(self, registry):
        """Test 2: has returns False for undefined name."""
        assert registry.has("nonexistent") is False

    def test_define_overwrites_existing(self, registry):
        """Test 3: define overwrites existing recipe."""
        recipe1 = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        recipe2 = {get_key(Health): {"value": 100, "max_value": 100}}

        registry.define("entity", recipe1)
        registry.define("entity", recipe2)

        recipes = registry.recipes()
        assert recipes["entity"] == recipe2

    def test_remove_deletes_recipe(self, registry):
        """Test 4: remove deletes recipe, has returns False after."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("temp", recipe)
        assert registry.has("temp") is True

        registry.remove("temp")
        assert registry.has("temp") is False

    def test_remove_raises_keyerror_for_undefined(self, registry):
        """Test 5: remove raises KeyError for undefined name."""
        with pytest.raises(KeyError):
            registry.remove("nonexistent")

    def test_recipes_returns_all_defined(self, registry):
        """Test 6: recipes returns all defined recipes."""
        recipe1 = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        recipe2 = {get_key(Health): {"value": 100, "max_value": 100}}

        registry.define("entity1", recipe1)
        registry.define("entity2", recipe2)

        recipes = registry.recipes()
        assert len(recipes) == 2
        assert "entity1" in recipes
        assert "entity2" in recipes
        assert recipes["entity1"] == recipe1
        assert recipes["entity2"] == recipe2

    def test_recipes_returns_copy(self, registry):
        """Test 7: recipes returns a copy - modifying it doesn't affect registry (criterion 39)."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("original", recipe)

        # Get recipes and modify the returned dict
        recipes = registry.recipes()
        recipes["modified"] = {get_key(Health): {"value": 50, "max_value": 50}}
        recipes["original"][get_key(Pos)]["x"] = 999.0

        # Verify original registry is unchanged
        assert registry.has("modified") is False
        original_recipe = registry.recipes()["original"]
        assert original_recipe[get_key(Pos)]["x"] == 10.0


# Spawn basics tests
class TestSpawnBasics:
    """Test basic spawn operations."""

    def test_spawn_creates_entity_with_all_components(self, registry, world):
        """Test 8: spawn creates entity with all components (criterion 35)."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100},
            get_key(Name): {"label": "Player"}
        }
        registry.define("player", recipe)

        eid = registry.spawn(world, "player")

        # Verify all components are attached
        assert world.has(eid, Pos)
        assert world.has(eid, Health)
        assert world.has(eid, Name)

        # Verify component values
        pos = world.get(eid, Pos)
        assert pos.x == 10.0
        assert pos.y == 20.0

        health = world.get(eid, Health)
        assert health.value == 100
        assert health.max_value == 100

        name = world.get(eid, Name)
        assert name.label == "Player"

    def test_spawn_returns_valid_entity_id(self, registry, world):
        """Test 9: spawn returns valid entity ID."""
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        registry.define("entity", recipe)

        eid = registry.spawn(world, "entity")

        # Entity ID should be an integer
        assert isinstance(eid, int)
        # Entity should exist in world
        assert world.has(eid, Pos)

    def test_spawn_raises_keyerror_for_undefined_recipe(self, registry, world):
        """Test 10: spawn raises KeyError for undefined recipe (criterion 37)."""
        with pytest.raises(KeyError, match="nonexistent"):
            registry.spawn(world, "nonexistent")

    def test_spawn_raises_keyerror_for_unregistered_component(self, registry, engine):
        """Test 11: spawn raises KeyError for unregistered component type (criterion 38)."""
        # Create a world WITHOUT registering Pos
        world = engine.world

        # Define recipe with unregistered component
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("entity", recipe)

        # Should raise KeyError when trying to spawn
        with pytest.raises(KeyError):
            registry.spawn(world, "entity")


# Override tests
class TestOverrides:
    """Test spawn with overrides."""

    def test_spawn_with_overrides_merges_fields(self, registry, world):
        """Test 12: spawn with overrides merges fields (criterion 36)."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        overrides = {
            get_key(Pos): {"y": 50.0}  # Override y, keep x
        }

        eid = registry.spawn(world, "entity", overrides)

        pos = world.get(eid, Pos)
        assert pos.x == 10.0  # Original value
        assert pos.y == 50.0  # Overridden value

        health = world.get(eid, Health)
        assert health.value == 100  # Unchanged

    def test_override_replaces_field_values(self, registry, world):
        """Test 13: override replaces field values (shallow, not deep merge)."""
        recipe = {
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        overrides = {
            get_key(Health): {"value": 50}  # Replace value only
        }

        eid = registry.spawn(world, "entity", overrides)

        health = world.get(eid, Health)
        assert health.value == 50  # Overridden
        assert health.max_value == 100  # Original

    def test_override_can_add_new_components(self, registry, world):
        """Test 14: override can add new components not in original recipe."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0}
        }
        registry.define("entity", recipe)

        overrides = {
            get_key(Health): {"value": 50, "max_value": 50}  # Add new component
        }

        eid = registry.spawn(world, "entity", overrides)

        # Original component present
        assert world.has(eid, Pos)
        # New component added via override
        assert world.has(eid, Health)

        health = world.get(eid, Health)
        assert health.value == 50

    def test_override_doesnt_mutate_stored_recipe(self, registry, world):
        """Test 15: override doesn't mutate the stored recipe (spawn same recipe again, original values intact)."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0}
        }
        registry.define("entity", recipe)

        # Spawn with overrides
        overrides = {get_key(Pos): {"x": 999.0}}
        eid1 = registry.spawn(world, "entity", overrides)

        # Spawn again without overrides
        eid2 = registry.spawn(world, "entity")

        # First entity has overridden values
        pos1 = world.get(eid1, Pos)
        assert pos1.x == 999.0

        # Second entity has original recipe values
        pos2 = world.get(eid2, Pos)
        assert pos2.x == 10.0
        assert pos2.y == 20.0


# Serialization tests
class TestSerialization:
    """Test snapshot/restore round-trip."""

    def test_spawned_entity_round_trips(self, registry, engine, world):
        """Test 16: spawned entity round-trips through snapshot/restore (criterion 40)."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100},
            get_key(Name): {"label": "Player"}
        }
        registry.define("player", recipe)

        eid = registry.spawn(world, "player")

        # Take snapshot
        snapshot = engine.snapshot()

        # Modify the entity
        pos = world.get(eid, Pos)
        pos.x = 999.0

        # Restore snapshot
        engine.restore(snapshot)

        # Verify original values restored
        restored_pos = world.get(eid, Pos)
        assert restored_pos.x == 10.0
        assert restored_pos.y == 20.0

        health = world.get(eid, Health)
        assert health.value == 100

        name = world.get(eid, Name)
        assert name.label == "Player"


# Edge case tests
class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_empty_recipe_spawns_entity_with_no_components(self, registry, world):
        """Test 17: empty recipe - spawns entity with no components."""
        recipe = {}  # Empty recipe
        registry.define("empty", recipe)

        eid = registry.spawn(world, "empty")

        # Entity should exist but have no components
        assert isinstance(eid, int)
        assert not world.has(eid, Pos)
        assert not world.has(eid, Health)
        assert not world.has(eid, Name)

    def test_multiple_spawns_create_independent_entities(self, registry, world):
        """Test 18: multiple spawns from same recipe create independent entities."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        eid1 = registry.spawn(world, "entity")
        eid2 = registry.spawn(world, "entity")
        eid3 = registry.spawn(world, "entity")

        # All entities should be different
        assert eid1 != eid2
        assert eid2 != eid3
        assert eid1 != eid3

        # Modifying one shouldn't affect others
        pos1 = world.get(eid1, Pos)
        pos1.x = 999.0

        pos2 = world.get(eid2, Pos)
        assert pos2.x == 10.0  # Unchanged

    def test_recipe_with_multiple_components(self, registry, world):
        """Test 19: recipe with multiple components - all get attached."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100},
            get_key(Name): {"label": "Player"},
            get_key(Velocity): {"dx": 1.5, "dy": -2.0}
        }
        registry.define("player", recipe)

        eid = registry.spawn(world, "player")

        # All four components should be attached
        assert world.has(eid, Pos)
        assert world.has(eid, Health)
        assert world.has(eid, Name)
        assert world.has(eid, Velocity)

        # Verify all values
        pos = world.get(eid, Pos)
        assert pos.x == 10.0 and pos.y == 20.0

        health = world.get(eid, Health)
        assert health.value == 100 and health.max_value == 100

        name = world.get(eid, Name)
        assert name.label == "Player"

        vel = world.get(eid, Velocity)
        assert vel.dx == 1.5 and vel.dy == -2.0


# Additional integration and security tests
class TestIntegration:
    """Integration tests with tick engine."""

    def test_spawned_entities_can_be_queried(self, registry, world):
        """Test that spawned entities are queryable."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        eid1 = registry.spawn(world, "entity")
        eid2 = registry.spawn(world, "entity")

        # Query for entities with both components
        results = list(world.query(Pos, Health))
        assert len(results) >= 2

        # Verify both entities are in results
        entity_ids = [eid for eid, _ in results]
        assert eid1 in entity_ids
        assert eid2 in entity_ids

    def test_spawned_entities_can_be_despawned(self, registry, world):
        """Test that spawned entities can be despawned."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("entity", recipe)

        eid = registry.spawn(world, "entity")
        assert world.has(eid, Pos)

        world.despawn(eid)
        assert not world.has(eid, Pos)

    def test_components_can_be_detached_from_spawned_entities(self, registry, world):
        """Test that components can be detached from spawned entities."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        eid = registry.spawn(world, "entity")

        world.detach(eid, Pos)
        assert not world.has(eid, Pos)
        assert world.has(eid, Health)  # Other components remain

    def test_multiple_registries_are_independent(self, world):
        """Test that multiple registries are independent."""
        reg1 = BlueprintRegistry()
        reg2 = BlueprintRegistry()

        recipe1 = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        recipe2 = {get_key(Health): {"value": 50, "max_value": 50}}

        reg1.define("entity", recipe1)
        reg2.define("entity", recipe2)

        eid1 = reg1.spawn(world, "entity")
        eid2 = reg2.spawn(world, "entity")

        # First entity has Pos, not Health
        assert world.has(eid1, Pos)
        assert not world.has(eid1, Health)

        # Second entity has Health, not Pos
        assert not world.has(eid2, Pos)
        assert world.has(eid2, Health)


# Input validation and edge cases
class TestInputValidation:
    """Test input validation and error handling."""

    def test_empty_overrides_dict_same_as_none(self, registry, world):
        """Test that empty overrides dict behaves same as None."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("entity", recipe)

        eid1 = registry.spawn(world, "entity", None)
        eid2 = registry.spawn(world, "entity", {})

        pos1 = world.get(eid1, Pos)
        pos2 = world.get(eid2, Pos)

        assert pos1.x == pos2.x == 10.0
        assert pos1.y == pos2.y == 20.0

    def test_recipe_with_zero_values(self, registry, world):
        """Test that recipes can contain zero values."""
        recipe = {
            get_key(Pos): {"x": 0.0, "y": 0.0},
            get_key(Health): {"value": 0, "max_value": 1}
        }
        registry.define("zero", recipe)

        eid = registry.spawn(world, "zero")

        pos = world.get(eid, Pos)
        assert pos.x == 0.0 and pos.y == 0.0

        health = world.get(eid, Health)
        assert health.value == 0

    def test_recipe_with_negative_values(self, registry, world):
        """Test that recipes can contain negative values."""
        recipe = {
            get_key(Pos): {"x": -10.0, "y": -20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("negative", recipe)

        eid = registry.spawn(world, "negative")

        pos = world.get(eid, Pos)
        assert pos.x == -10.0 and pos.y == -20.0

    def test_override_all_fields(self, registry, world):
        """Test that overrides can replace all fields of a component."""
        recipe = {get_key(Pos): {"x": 10.0, "y": 20.0}}
        registry.define("entity", recipe)

        overrides = {get_key(Pos): {"x": 100.0, "y": 200.0}}
        eid = registry.spawn(world, "entity", overrides)

        pos = world.get(eid, Pos)
        assert pos.x == 100.0 and pos.y == 200.0

    def test_recipe_names_can_be_any_string(self, registry, world):
        """Test that recipe names can be any string."""
        recipe = {get_key(Pos): {"x": 1.0, "y": 2.0}}

        # Various valid recipe names
        names = ["simple", "with-dashes", "with_underscores", "123numeric", ""]

        for name in names:
            registry.define(name, recipe)
            assert registry.has(name)
            eid = registry.spawn(world, name)
            assert world.has(eid, Pos)


# Performance and stress tests
class TestPerformance:
    """Test performance characteristics (not strict benchmarks)."""

    def test_spawn_many_entities_from_same_recipe(self, registry, world):
        """Test spawning many entities from the same recipe."""
        recipe = {
            get_key(Pos): {"x": 10.0, "y": 20.0},
            get_key(Health): {"value": 100, "max_value": 100}
        }
        registry.define("entity", recipe)

        # Spawn 100 entities
        entity_ids = [registry.spawn(world, "entity") for _ in range(100)]

        # All should be unique
        assert len(set(entity_ids)) == 100

        # All should have the components
        for eid in entity_ids:
            assert world.has(eid, Pos)
            assert world.has(eid, Health)

    def test_many_recipes_in_registry(self, registry, world):
        """Test registry with many recipes."""
        # Define 50 different recipes
        for i in range(50):
            recipe = {get_key(Pos): {"x": float(i), "y": float(i * 2)}}
            registry.define(f"entity{i}", recipe)

        assert len(registry.recipes()) == 50

        # All recipes should be spawnable
        for i in range(50):
            eid = registry.spawn(world, f"entity{i}")
            pos = world.get(eid, Pos)
            assert pos.x == float(i)
            assert pos.y == float(i * 2)
