"""Tests for BlueprintRegistry meta support."""
from __future__ import annotations

import pytest
from dataclasses import dataclass
from tick import Engine
from tick_blueprint import BlueprintRegistry


@dataclass
class Pos:
    x: float
    y: float


def get_key(ctype: type) -> str:
    return f"{ctype.__module__}.{ctype.__qualname__}"


@pytest.fixture
def registry() -> BlueprintRegistry:
    return BlueprintRegistry()


@pytest.fixture
def world():
    engine = Engine(tps=20, seed=42)
    engine.world.register_component(Pos)
    return engine.world


class TestMetaDefine:
    def test_define_with_meta(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        meta = {"cost": {"wood": 50}, "exclusive": True}
        registry.define("farm", recipe, meta=meta)
        assert registry.meta("farm") == meta

    def test_define_without_meta_defaults_empty(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        registry.define("farm", recipe)
        assert registry.meta("farm") == {}

    def test_define_with_none_meta_defaults_empty(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        registry.define("farm", recipe, meta=None)
        assert registry.meta("farm") == {}

    def test_overwrite_replaces_meta(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        registry.define("farm", recipe, meta={"v": 1})
        registry.define("farm", recipe, meta={"v": 2})
        assert registry.meta("farm") == {"v": 2}

    def test_overwrite_without_meta_resets(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 0.0, "y": 0.0}}
        registry.define("farm", recipe, meta={"v": 1})
        registry.define("farm", recipe)
        assert registry.meta("farm") == {}


class TestMetaAccessor:
    def test_meta_raises_keyerror_undefined(self, registry: BlueprintRegistry) -> None:
        with pytest.raises(KeyError):
            registry.meta("nonexistent")

    def test_meta_returns_same_dict_object(self, registry: BlueprintRegistry) -> None:
        meta = {"cost": 10}
        registry.define("x", {}, meta=meta)
        assert registry.meta("x") is registry.meta("x")

    def test_meta_independent_per_recipe(self, registry: BlueprintRegistry) -> None:
        registry.define("a", {}, meta={"type": "a"})
        registry.define("b", {}, meta={"type": "b"})
        assert registry.meta("a") == {"type": "a"}
        assert registry.meta("b") == {"type": "b"}


class TestMetaRemove:
    def test_remove_clears_meta(self, registry: BlueprintRegistry) -> None:
        registry.define("x", {}, meta={"v": 1})
        registry.remove("x")
        with pytest.raises(KeyError):
            registry.meta("x")


class TestMetaRecipesUnchanged:
    def test_recipes_excludes_meta(self, registry: BlueprintRegistry) -> None:
        recipe = {get_key(Pos): {"x": 1.0, "y": 2.0}}
        registry.define("farm", recipe, meta={"cost": 50})
        recipes = registry.recipes()
        assert "farm" in recipes
        assert recipes["farm"] == recipe

    def test_meta_not_in_recipe_values(self, registry: BlueprintRegistry) -> None:
        registry.define("farm", {}, meta={"big": True})
        recipes = registry.recipes()
        assert "big" not in recipes.get("farm", {})


class TestMetaSpawn:
    def test_spawn_still_works_with_meta(self, registry: BlueprintRegistry, world) -> None:
        recipe = {get_key(Pos): {"x": 5.0, "y": 10.0}}
        registry.define("entity", recipe, meta={"exclusive": True})
        eid = registry.spawn(world, "entity")
        pos = world.get(eid, Pos)
        assert pos.x == 5.0
        assert pos.y == 10.0
