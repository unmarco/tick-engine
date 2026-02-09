"""Tests for hierarchical FSM feature (dot-notation states, initial, history)."""
import pytest
from dataclasses import dataclass
from tick import Engine
from tick_fsm import FSM, FSMGuards, make_fsm_system


@dataclass
class Health:
    """Component tracking health level."""
    value: float


@dataclass
class Ammo:
    """Component tracking ammunition."""
    value: int


class TestHierarchicalFSMBackwardCompatibility:
    """Ensure flat FSMs still work with new hierarchical system."""

    def test_flat_fsm_no_hierarchy(self):
        """Flat FSM (no dots) behaves identically to before."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [["go", "active"]],
                "active": [["go", "done"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "active"

        engine.step()
        assert fsm.state == "done"

    def test_fsm_without_initial_and_history_fields(self):
        """FSM with only state and transitions (no initial/history) works."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("trigger", lambda w, e: True)

        eid = world.spawn()
        # Create FSM without explicitly setting initial/history (uses defaults)
        world.attach(eid, FSM(
            state="start",
            transitions={"start": [["trigger", "end"]]}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "end"
        assert fsm.initial == {}  # default
        assert fsm.history == {}  # default

    def test_flat_fsm_on_transition_callback(self):
        """on_transition callback receives correct old/new states for flat FSM."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={"idle": [["go", "moving"]]}
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        assert len(transitions_log) == 1
        assert transitions_log[0] == (eid, "idle", "moving")


class TestParentFallback:
    """Test parent state fallback behavior for hierarchical transitions."""

    def test_parent_transition_fires_when_child_has_none(self):
        """Entity in 'combat.attack', parent 'combat' has transition to 'idle'."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)

        guards = FSMGuards()
        guards.register("low_health", lambda w, e: w.has(e, Health) and w.get(e, Health).value < 20)

        eid = world.spawn()
        world.attach(eid, Health(value=10))  # low health
        world.attach(eid, FSM(
            state="combat.attack",
            transitions={
                "combat": [["low_health", "flee"]],  # parent fallback
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should transition via parent 'combat' rule
        fsm = world.get(eid, FSM)
        assert fsm.state == "flee"

    def test_child_transition_priority_over_parent(self):
        """Child state has its own transition - takes priority over parent."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)

        guards = FSMGuards()
        guards.register("low_health", lambda w, e: w.has(e, Health) and w.get(e, Health).value < 20)

        eid = world.spawn()
        world.attach(eid, Health(value=10))
        world.attach(eid, FSM(
            state="combat.attack",
            transitions={
                "combat.attack": [["low_health", "combat.defend"]],  # child
                "combat": [["low_health", "flee"]],  # parent
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - child transition should fire, not parent
        fsm = world.get(eid, FSM)
        assert fsm.state == "combat.defend"

    def test_multi_level_parent_walk(self):
        """State 'a.b.c' walks up through 'a.b', then 'a' to find transition."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("trigger", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b.c",
            transitions={
                "a": [["trigger", "root"]],  # only grandparent has transition
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should walk up to 'a' and fire transition
        fsm = world.get(eid, FSM)
        assert fsm.state == "root"

    def test_parent_fallback_skips_intermediate_level(self):
        """State 'x.y.z' has no transition, 'x.y' has none, 'x' has transition."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="x.y.z",
            transitions={
                "x": [["go", "done"]],  # only top-level parent
                # no transitions for x.y or x.y.z
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "done"

    def test_no_transition_at_any_level(self):
        """State 'a.b.c' has no transitions at any level - stays put."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("trigger", lambda w, e: False)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b.c",
            transitions={
                "a.b.c": [["trigger", "leaf"]],
                "a.b": [["trigger", "middle"]],
                "a": [["trigger", "root"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - no transition fires, state unchanged
        fsm = world.get(eid, FSM)
        assert fsm.state == "a.b.c"


class TestInitialChildResolution:
    """Test initial child state resolution when entering parent states."""

    def test_initial_child_on_entry(self):
        """Target 'combat' with initial mapping resolves to 'combat.attack'."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("enter_combat", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [["enter_combat", "combat"]],
            },
            initial={"combat": "combat.attack"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should resolve to combat.attack, not just combat
        fsm = world.get(eid, FSM)
        assert fsm.state == "combat.attack"

    def test_chained_initial_resolution(self):
        """Chained initial: 'a' -> 'a.b' -> 'a.b.c'."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="start",
            transitions={
                "start": [["go", "a"]],
            },
            initial={
                "a": "a.b",
                "a.b": "a.b.c",
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should chain through initial mappings to leaf
        fsm = world.get(eid, FSM)
        assert fsm.state == "a.b.c"

    def test_no_initial_mapping_stays_as_target(self):
        """No initial mapping for target - state stays as raw target (leaf)."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [["go", "moving"]],
            },
            initial={}  # no mappings
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - no initial mapping, stays as 'moving'
        fsm = world.get(eid, FSM)
        assert fsm.state == "moving"

    def test_partial_initial_chain(self):
        """Initial maps 'a' -> 'a.b' but 'a.b' has no further mapping."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="root",
            transitions={
                "root": [["go", "a"]],
            },
            initial={
                "a": "a.b",
                # no mapping for a.b
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - resolves to a.b and stops (no further mapping)
        fsm = world.get(eid, FSM)
        assert fsm.state == "a.b"

    def test_cyclic_initial_mapping_protected(self):
        """Cyclic initial mappings don't infinite-loop (protected by seen set)."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="start",
            transitions={
                "start": [["go", "a"]],
            },
            initial={
                "a": "b",
                "b": "c",
                "c": "a",  # cycle
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - should not hang
        engine.step()

        # Assert - cycle detected, stops at some state in cycle
        fsm = world.get(eid, FSM)
        # Should be one of a, b, or c (cycle broken by seen set)
        assert fsm.state in ["a", "b", "c"]


class TestHistoryStates:
    """Test history state tracking and restoration."""

    def test_history_overrides_initial_on_reentry(self):
        """Was in 'combat.attack', went to 'idle', back to 'combat' resumes 'combat.attack'."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)

        guards = FSMGuards()
        guards.register("low_health", lambda w, e: w.has(e, Health) and w.get(e, Health).value < 30)
        guards.register("healed", lambda w, e: w.has(e, Health) and w.get(e, Health).value >= 80)

        eid = world.spawn()
        world.attach(eid, Health(value=25))  # low health initially
        world.attach(eid, FSM(
            state="combat.attack",
            transitions={
                "combat": [["low_health", "idle"]],
                "idle": [["healed", "combat"]],
            },
            initial={"combat": "combat.defend"}  # initial default is defend
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - first transition: combat.attack -> idle
        engine.step()
        fsm = world.get(eid, FSM)
        assert fsm.state == "idle"
        assert "combat" in fsm.history  # history should be recorded
        assert fsm.history["combat"] == "combat.attack"

        # Heal up and go back to combat
        world.get(eid, Health).value = 90
        engine.step()

        # Assert - should resume combat.attack (history), not combat.defend (initial)
        fsm = world.get(eid, FSM)
        assert fsm.state == "combat.attack"

    def test_history_recorded_at_each_parent_level(self):
        """Deep hierarchy 'a.b.c' records history at each level."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("leave", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b.c",
            transitions={
                "a": [["leave", "elsewhere"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - history recorded for 'a' and 'a.b'
        fsm = world.get(eid, FSM)
        assert fsm.state == "elsewhere"
        assert fsm.history["a"] == "a.b"
        assert fsm.history["a.b"] == "a.b.c"

    def test_fresh_fsm_uses_initial_not_history(self):
        """Fresh FSM with no history uses initial mapping."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="start",
            transitions={
                "start": [["go", "menu"]],
            },
            initial={"menu": "menu.main"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - no history, uses initial
        fsm = world.get(eid, FSM)
        assert fsm.state == "menu.main"
        assert fsm.history == {}  # no history yet

    def test_history_updates_on_each_transition(self):
        """History is mutable and updates as entity transitions."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b",
            transitions={
                "a": [["always", "x"]],
                "x": [["always", "a"]],
            },
            initial={"a": "a.b"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - first transition from a.b -> x
        engine.step()
        fsm = world.get(eid, FSM)
        assert fsm.state == "x"
        assert fsm.history["a"] == "a.b"

        # Second transition x -> a (resolves via history to a.b)
        engine.step()
        fsm = world.get(eid, FSM)
        assert fsm.state == "a.b"

        # Now move to a different child
        fsm.state = "a.c"
        engine.step()  # a.c -> x

        # Assert - history updated to a.c
        fsm = world.get(eid, FSM)
        assert fsm.state == "x"
        assert fsm.history["a"] == "a.c"  # updated

    def test_history_with_multiple_levels(self):
        """Multi-level hierarchy tracks history correctly."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("exit", lambda w, e: True)
        guards.register("reenter", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="game.play.combat.melee",
            transitions={
                "game": [["exit", "menu"]],
                "menu": [["reenter", "game"]],
            },
            initial={
                "game": "game.play",
                "game.play": "game.play.explore",
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - exit game
        engine.step()
        fsm = world.get(eid, FSM)
        assert fsm.state == "menu"
        # History should be recorded at each level
        assert fsm.history["game"] == "game.play"
        assert fsm.history["game.play"] == "game.play.combat"
        assert fsm.history["game.play.combat"] == "game.play.combat.melee"

        # Re-enter game
        guards.register("exit", lambda w, e: False)  # disable exit
        engine.step()

        # Assert - should restore deep history
        fsm = world.get(eid, FSM)
        assert fsm.state == "game.play.combat.melee"


class TestOnTransitionCallback:
    """Test on_transition callback with hierarchical states."""

    def test_callback_receives_resolved_leaf_state(self):
        """on_transition receives resolved leaf state, not raw target."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="start",
            transitions={
                "start": [["go", "parent"]],
            },
            initial={"parent": "parent.child"}
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - callback receives resolved state 'parent.child', not 'parent'
        assert len(transitions_log) == 1
        assert transitions_log[0] == (eid, "start", "parent.child")

    def test_callback_with_history_resolution(self):
        """on_transition receives history-resolved state."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("leave", lambda w, e: True)
        guards.register("return", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="menu.options",
            transitions={
                "menu": [["leave", "game"]],
                "game": [["return", "menu"]],
            },
            initial={"menu": "menu.main"}
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act - leave menu
        engine.step()
        # Return to menu (should use history)
        guards.register("leave", lambda w, e: False)
        engine.step()

        # Assert - second transition should be to menu.options (history)
        assert len(transitions_log) == 2
        assert transitions_log[0] == (eid, "menu.options", "game")
        assert transitions_log[1] == (eid, "game", "menu.options")

    def test_callback_with_parent_fallback(self):
        """Callback receives correct states when parent transition fires."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("trigger", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="parent.child",
            transitions={
                "parent": [["trigger", "other"]],  # parent fallback
            }
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        assert len(transitions_log) == 1
        assert transitions_log[0] == ("parent.child", "other")


class TestSnapshotRestoreCompatibility:
    """Test snapshot/restore with initial and history fields."""

    def test_fsm_with_initial_and_history_round_trip(self):
        """FSM with initial and history fields survives snapshot/restore."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("leave", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b.c",
            transitions={
                "a": [["leave", "elsewhere"]],
            },
            initial={"a": "a.b"},
            history={}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Transition to record history
        engine.step()
        fsm_before = world.get(eid, FSM)
        assert fsm_before.state == "elsewhere"
        assert fsm_before.history["a"] == "a.b"

        # Act - snapshot
        snapshot = engine.snapshot()

        # Create new engine and restore
        engine2 = Engine(tps=20, seed=100)
        world2 = engine2.world
        world2.register_component(FSM)
        system2 = make_fsm_system(guards)
        engine2.add_system(system2)
        engine2.restore(snapshot)

        # Assert - FSM state, initial, and history preserved
        fsm_after = world2.get(eid, FSM)
        assert fsm_after.state == "elsewhere"
        assert fsm_after.initial == {"a": "a.b"}
        assert fsm_after.history == {"a": "a.b", "a.b": "a.b.c"}

    def test_old_snapshot_missing_initial_history_works(self):
        """Old snapshot (missing initial/history) works with new FSM (defaults to empty dicts)."""
        # This test simulates loading an old FSM that didn't have initial/history.
        # In practice, the dataclass defaults handle this automatically.

        # Arrange - create FSM without explicit initial/history
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={"idle": [["go", "active"]]}
            # initial and history use defaults (empty dicts)
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - snapshot and restore
        snapshot = engine.snapshot()

        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(FSM)
        system2 = make_fsm_system(guards)
        engine2.add_system(system2)
        engine2.restore(snapshot)

        # Assert - works fine with default empty dicts
        fsm = world2.get(eid, FSM)
        assert fsm.state == "idle"
        assert fsm.initial == {}
        assert fsm.history == {}

        # Verify transitions still work
        engine2.step()
        assert world2.get(eid, FSM).state == "active"

    def test_history_persists_through_snapshot(self):
        """History dict persists through snapshot/restore and continues working."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("out", lambda w, e: True)
        guards.register("in", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="menu.settings",
            transitions={
                "menu": [["out", "game"]],
                "game": [["in", "menu"]],
            },
            initial={"menu": "menu.main"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Transition to record history
        engine.step()
        assert world.get(eid, FSM).state == "game"

        # Act - snapshot
        snapshot = engine.snapshot()

        # Restore in new engine
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(FSM)
        system2 = make_fsm_system(guards)
        engine2.add_system(system2)
        engine2.restore(snapshot)

        # Assert - history preserved
        fsm = world2.get(eid, FSM)
        assert fsm.history["menu"] == "menu.settings"

        # Transition back to menu
        guards.register("out", lambda w, e: False)
        engine2.step()

        # Should use history
        fsm = world2.get(eid, FSM)
        assert fsm.state == "menu.settings"


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_state_with_no_transitions_at_any_level(self):
        """State with no transitions at any level stays put."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()

        eid = world.spawn()
        world.attach(eid, FSM(
            state="orphan.child",
            transitions={}  # no transitions defined anywhere
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "orphan.child"

    def test_at_most_one_transition_per_tick_hierarchical(self):
        """At-most-one-transition-per-tick preserved with hierarchical states."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b",
            transitions={
                "a": [["always", "x"]],
                "x": [["always", "y"]],  # would fire if second transition allowed
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - only one transition (a.b -> x), not two (a.b -> x -> y)
        fsm = world.get(eid, FSM)
        assert fsm.state == "x"

    def test_empty_transitions_dict_hierarchical(self):
        """Empty transitions dict is fine with hierarchical state."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()

        eid = world.spawn()
        world.attach(eid, FSM(
            state="some.deep.state",
            transitions={},
            initial={"some": "some.deep"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "some.deep.state"

    def test_transition_to_leaf_no_initial(self):
        """Transition directly to leaf state (no initial mapping) works."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="start",
            transitions={
                "start": [["go", "end.leaf"]],  # direct to leaf
            },
            initial={}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - no initial mapping, stays as target
        fsm = world.get(eid, FSM)
        assert fsm.state == "end.leaf"

    def test_single_dot_state(self):
        """State with single dot (parent.child) works correctly."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("up", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b",
            transitions={
                "a": [["up", "root"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "root"

    def test_parent_and_child_both_have_matching_guards(self):
        """Child guard fires first, parent guard never evaluated."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guard_calls = []

        def child_guard(w, e):
            guard_calls.append("child")
            return True

        def parent_guard(w, e):
            guard_calls.append("parent")
            return True

        guards = FSMGuards()
        guards.register("child_go", child_guard)
        guards.register("parent_go", parent_guard)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="parent.child",
            transitions={
                "parent.child": [["child_go", "c_target"]],
                "parent": [["parent_go", "p_target"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - child guard fires, parent never checked
        assert guard_calls == ["child"]
        fsm = world.get(eid, FSM)
        assert fsm.state == "c_target"

    def test_multiple_children_different_histories(self):
        """Multiple child states of same parent each record separate history."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid1 = world.spawn()
        world.attach(eid1, FSM(
            state="menu.options",
            transitions={"menu": [["go", "game"]]}
        ))

        eid2 = world.spawn()
        world.attach(eid2, FSM(
            state="menu.credits",
            transitions={"menu": [["go", "game"]]}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - each entity has its own history
        fsm1 = world.get(eid1, FSM)
        fsm2 = world.get(eid2, FSM)
        assert fsm1.history["menu"] == "menu.options"
        assert fsm2.history["menu"] == "menu.credits"

    def test_history_and_initial_both_set_history_wins(self):
        """When both history and initial are set, history takes priority."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("out", lambda w, e: True)
        guards.register("back", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="menu.settings",
            transitions={
                "menu": [["out", "game"]],
                "game": [["back", "menu"]],
            },
            initial={"menu": "menu.main"}  # initial says main
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - leave menu (records settings as history)
        engine.step()
        fsm = world.get(eid, FSM)
        assert fsm.state == "game"
        assert fsm.history["menu"] == "menu.settings"

        # Return to menu
        guards.register("out", lambda w, e: False)
        engine.step()

        # Assert - history (settings) wins over initial (main)
        fsm = world.get(eid, FSM)
        assert fsm.state == "menu.settings"


class TestComplexHierarchicalScenarios:
    """Complex scenarios combining multiple hierarchical features."""

    def test_deep_hierarchy_combat_system(self):
        """Realistic combat FSM with deep hierarchy and state switching."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)
        world.register_component(Ammo)

        guards = FSMGuards()
        guards.register("low_health", lambda w, e: w.has(e, Health) and w.get(e, Health).value < 30)
        guards.register("out_of_ammo", lambda w, e: w.has(e, Ammo) and w.get(e, Ammo).value == 0)
        guards.register("healthy", lambda w, e: w.has(e, Health) and w.get(e, Health).value >= 70)
        guards.register("has_ammo", lambda w, e: w.has(e, Ammo) and w.get(e, Ammo).value > 0)

        eid = world.spawn()
        world.attach(eid, Health(value=100))
        world.attach(eid, Ammo(value=0))  # out of ammo
        world.attach(eid, FSM(
            state="combat.offense.ranged",
            transitions={
                "combat.offense.ranged": [["out_of_ammo", "combat.offense.melee"]],
                "combat.offense": [["low_health", "combat.defense"]],
                "combat": [["healthy", "explore"]],
                "explore": [["low_health", "combat"]],
            },
            initial={
                "combat": "combat.offense",
                "combat.offense": "combat.offense.ranged",
                "combat.defense": "combat.defense.cover",
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act & Assert - step through complex state changes

        # Tick 1: out of ammo, switch to melee
        engine.step()
        assert world.get(eid, FSM).state == "combat.offense.melee"

        # Tick 2: take damage, switch to defense
        world.get(eid, Health).value = 25
        engine.step()
        assert world.get(eid, FSM).state == "combat.defense.cover"

        # Tick 3: heal up, exit combat
        world.get(eid, Health).value = 90
        engine.step()
        assert world.get(eid, FSM).state == "explore"

        # Tick 4: get hurt again, re-enter combat (should use history)
        world.get(eid, Health).value = 20
        engine.step()
        # Should resume at combat.defense.cover (history)
        assert world.get(eid, FSM).state == "combat.defense.cover"

    def test_menu_navigation_with_history(self):
        """Menu system tracks last position in each submenu."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        # Use a counter to simulate user input
        @dataclass
        class MenuInput:
            action: str

        world.register_component(MenuInput)

        guards = FSMGuards()
        guards.register("options", lambda w, e: w.has(e, MenuInput) and w.get(e, MenuInput).action == "options")
        guards.register("back", lambda w, e: w.has(e, MenuInput) and w.get(e, MenuInput).action == "back")
        guards.register("gameplay", lambda w, e: w.has(e, MenuInput) and w.get(e, MenuInput).action == "gameplay")

        eid = world.spawn()
        world.attach(eid, MenuInput(action="options"))
        world.attach(eid, FSM(
            state="menu.main",
            transitions={
                "menu": [["options", "menu.options"]],
                "menu.options": [
                    ["gameplay", "menu.options.gameplay"],
                    ["back", "menu"],
                ],
                "menu.options.gameplay": [["back", "menu.options"]],
            },
            initial={
                "menu": "menu.main",
                "menu.options": "menu.options.audio",
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - navigate through menus

        # main -> options (resolves to audio via initial)
        engine.step()
        assert world.get(eid, FSM).state == "menu.options.audio"

        # options.audio -> options.gameplay
        world.get(eid, MenuInput).action = "gameplay"
        engine.step()
        assert world.get(eid, FSM).state == "menu.options.gameplay"

        # gameplay -> back to menu.options (going up clears subtree history,
        # so menu.options resolves via initial → audio)
        world.get(eid, MenuInput).action = "back"
        engine.step()
        assert world.get(eid, FSM).state == "menu.options.audio"

        # audio -> back to menu (going up clears menu subtree history,
        # so menu resolves via initial → main)
        world.get(eid, MenuInput).action = "back"
        engine.step()
        assert world.get(eid, FSM).state == "menu.main"

        # main -> options (lateral: resolves via initial since
        # history was cleared by the previous "back" transitions)
        world.get(eid, MenuInput).action = "options"
        engine.step()
        assert world.get(eid, FSM).state == "menu.options.audio"

    def test_parent_fallback_with_initial_resolution(self):
        """Parent fallback fires, target has initial mapping."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("trigger", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a.b.c",
            transitions={
                "a": [["trigger", "x"]],  # parent fallback
            },
            initial={"x": "x.y"}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - parent transition fires, target x resolves to x.y
        fsm = world.get(eid, FSM)
        assert fsm.state == "x.y"
