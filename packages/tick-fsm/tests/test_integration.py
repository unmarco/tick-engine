"""Integration tests for tick-fsm module."""
import pytest
from dataclasses import dataclass
from tick import Engine
from tick_fsm import FSM, FSMGuards, make_fsm_system


@dataclass
class Health:
    """Health component."""
    value: int


@dataclass
class Hunger:
    """Hunger component."""
    value: int


@dataclass
class Position:
    """Position component."""
    x: int
    y: int


class TestFSMIntegration:
    """Integration tests combining FSMGuards and FSM systems."""

    def test_ai_behavior_simulation(self):
        """Simulate complete AI behavior with multiple states and conditions."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)
        world.register_component(Hunger)

        guards = FSMGuards()
        guards.register("healthy", lambda w, e: w.has(e, Health) and w.get(e, Health).value > 70)
        guards.register("injured", lambda w, e: w.has(e, Health) and w.get(e, Health).value < 30)
        guards.register("hungry", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value > 60)
        guards.register("fed", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value < 20)

        # Create entity with complex FSM
        eid = world.spawn()
        world.attach(eid, Health(value=80))
        world.attach(eid, Hunger(value=10))
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["hungry", "foraging"],
                    ["injured", "fleeing"],
                ],
                "foraging": [
                    ["fed", "idle"],
                    ["injured", "fleeing"],
                ],
                "fleeing": [
                    ["healthy", "idle"],
                ],
            }
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((ctx.tick_number, e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act & Assert - simulate dynamic behavior
        # Tick 1: idle (healthy, fed)
        engine.step()
        assert world.get(eid, FSM).state == "idle"
        assert len(transitions_log) == 0

        # Tick 2: become hungry -> foraging
        world.get(eid, Hunger).value = 70
        engine.step()
        assert world.get(eid, FSM).state == "foraging"
        assert transitions_log[-1] == (2, eid, "idle", "foraging")

        # Tick 3: get injured while foraging -> fleeing
        world.get(eid, Health).value = 20
        engine.step()
        assert world.get(eid, FSM).state == "fleeing"
        assert transitions_log[-1] == (3, eid, "foraging", "fleeing")

        # Tick 4: heal up -> idle
        world.get(eid, Health).value = 80
        engine.step()
        assert world.get(eid, FSM).state == "idle"
        assert transitions_log[-1] == (4, eid, "fleeing", "idle")

    def test_multiple_entities_different_states(self):
        """Multiple entities with different FSMs operate independently."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Position)

        guards = FSMGuards()
        guards.register("at_origin", lambda w, e: w.has(e, Position) and w.get(e, Position).x == 0 and w.get(e, Position).y == 0)
        guards.register("not_at_origin", lambda w, e: w.has(e, Position) and (w.get(e, Position).x != 0 or w.get(e, Position).y != 0))

        # Entity 1: Binary FSM (on/off)
        e1 = world.spawn()
        world.attach(e1, FSM(
            state="on",
            transitions={
                "on": [["at_origin", "off"]],
                "off": [["not_at_origin", "on"]],
            }
        ))
        world.attach(e1, Position(x=5, y=5))

        # Entity 2: Three-state FSM
        e2 = world.spawn()
        world.attach(e2, FSM(
            state="a",
            transitions={
                "a": [["not_at_origin", "b"]],
                "b": [["at_origin", "c"]],
                "c": [["not_at_origin", "a"]],
            }
        ))
        world.attach(e2, Position(x=0, y=0))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - e1 stays on (not at origin), e2 stays a (at origin)
        assert world.get(e1, FSM).state == "on"
        assert world.get(e2, FSM).state == "a"

        # Move e1 to origin, e2 away from origin
        world.get(e1, Position).x = 0
        world.get(e1, Position).y = 0
        world.get(e2, Position).x = 3
        world.get(e2, Position).y = 3

        engine.step()

        # Assert - e1 off, e2 b
        assert world.get(e1, FSM).state == "off"
        assert world.get(e2, FSM).state == "b"

    def test_nested_callback_state_changes(self):
        """on_transition callback modifying components affects next tick."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)

        guards = FSMGuards()
        guards.register("healthy", lambda w, e: w.has(e, Health) and w.get(e, Health).value > 50)
        guards.register("wounded", lambda w, e: w.has(e, Health) and w.get(e, Health).value <= 50)

        eid = world.spawn()
        world.attach(eid, Health(value=100))
        world.attach(eid, FSM(
            state="fighting",
            transitions={
                "fighting": [["wounded", "retreating"]],
                "retreating": [["healthy", "fighting"]],
            }
        ))

        def on_transition(w, ctx, e, old, new):
            # When retreating, heal by 60 points
            if new == "retreating":
                health = w.get(e, Health)
                health.value = min(100, health.value + 60)

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        # Tick 1: fighting (healthy)
        engine.step()
        assert world.get(eid, FSM).state == "fighting"

        # Damage the entity
        world.get(eid, Health).value = 30

        # Tick 2: fighting -> retreating (callback heals to 90)
        engine.step()
        assert world.get(eid, FSM).state == "retreating"
        assert world.get(eid, Health).value == 90

        # Tick 3: retreating -> fighting (now healthy)
        engine.step()
        assert world.get(eid, FSM).state == "fighting"

    def test_entity_despawn_during_transition(self):
        """Callback can despawn entities without breaking iteration."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_true", lambda w, e: True)

        # Create multiple entities
        entities = []
        for _ in range(5):
            eid = world.spawn()
            world.attach(eid, FSM(
                state="alive",
                transitions={"alive": [["always_true", "dead"]]}
            ))
            entities.append(eid)

        despawned = []

        def on_transition(w, ctx, e, old, new):
            if new == "dead":
                # Despawn the entity
                w.despawn(e)
                despawned.append(e)

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - all entities transitioned to dead and were despawned
        assert len(despawned) == 5
        for eid in entities:
            assert not world.has(eid, FSM)  # Entity no longer exists

    def test_guard_exception_propagates(self):
        """Exceptions in guards propagate to caller."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()

        def bad_guard(w, e):
            raise ValueError("Guard error")

        guards.register("bad", bad_guard)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a",
            transitions={"a": [["bad", "b"]]}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act & Assert
        with pytest.raises(ValueError, match="Guard error"):
            engine.step()

    def test_callback_exception_propagates(self):
        """Exceptions in on_transition callback propagate to caller."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a",
            transitions={"a": [["go", "b"]]}
        ))

        def bad_callback(w, ctx, e, old, new):
            raise RuntimeError("Callback error")

        system = make_fsm_system(guards, on_transition=bad_callback)
        engine.add_system(system)

        # Act & Assert
        with pytest.raises(RuntimeError, match="Callback error"):
            engine.step()

    def test_large_number_of_entities(self):
        """System handles many entities efficiently."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("flip", lambda w, e: e % 2 == 0)  # Even entities transition

        # Create 100 entities
        entities = []
        for i in range(100):
            eid = world.spawn()
            world.attach(eid, FSM(
                state="off",
                transitions={"off": [["flip", "on"]]}
            ))
            entities.append(eid)

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - even entities transitioned, odd didn't
        for eid in entities:
            fsm = world.get(eid, FSM)
            if eid % 2 == 0:
                assert fsm.state == "on"
            else:
                assert fsm.state == "off"

    def test_snapshot_restore_with_system(self):
        """FSM state persists through snapshot/restore cycle."""
        # Arrange
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        world1.register_component(FSM)

        guards1 = FSMGuards()
        guards1.register("go", lambda w, e: True)

        e1 = world1.spawn()
        world1.attach(e1, FSM(
            state="a",
            transitions={
                "a": [["go", "b"]],
                "b": [["go", "c"]],
            }
        ))

        system1 = make_fsm_system(guards1)
        engine1.add_system(system1)

        # Advance to state b
        engine1.step()
        assert world1.get(e1, FSM).state == "b"

        # Snapshot
        snapshot = engine1.snapshot()

        # Create new engine and restore
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(FSM)

        guards2 = FSMGuards()
        guards2.register("go", lambda w, e: True)

        system2 = make_fsm_system(guards2)
        engine2.add_system(system2)

        engine2.restore(snapshot)

        # Assert - state preserved
        assert world2.get(e1, FSM).state == "b"

        # Continue from restored state
        engine2.step()
        assert world2.get(e1, FSM).state == "c"

    def test_mixed_entities_with_and_without_fsm(self):
        """Entities without FSM are ignored by FSM system."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Health)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        # Entity with FSM
        e1 = world.spawn()
        world.attach(e1, FSM(state="a", transitions={"a": [["go", "b"]]}))

        # Entity without FSM
        e2 = world.spawn()
        world.attach(e2, Health(value=100))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - e1 transitioned, e2 unaffected
        assert world.get(e1, FSM).state == "b"
        assert world.get(e2, Health).value == 100
        assert not world.has(e2, FSM)

    def test_circular_transitions(self):
        """Circular state graphs work correctly."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_true", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="a",
            transitions={
                "a": [["always_true", "b"]],
                "b": [["always_true", "c"]],
                "c": [["always_true", "a"]],  # Back to a
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act & Assert - cycle through states
        assert world.get(eid, FSM).state == "a"

        engine.step()
        assert world.get(eid, FSM).state == "b"

        engine.step()
        assert world.get(eid, FSM).state == "c"

        engine.step()
        assert world.get(eid, FSM).state == "a"  # Back to start

        engine.step()
        assert world.get(eid, FSM).state == "b"  # Continues cycling
