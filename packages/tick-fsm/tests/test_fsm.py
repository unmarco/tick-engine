"""Tests for FSM component and make_fsm_system."""
import pytest
from dataclasses import dataclass
from tick import Engine
from tick_fsm import FSM, FSMGuards, make_fsm_system


@dataclass
class Hunger:
    """Component tracking hunger level."""
    value: float


@dataclass
class Energy:
    """Component tracking energy level."""
    value: float


class TestFSMComponent:
    """Test cases for FSM component and make_fsm_system."""

    def test_basic_transition(self):
        """Entity in 'idle' transitions to 'foraging' when 'hungry' guard is True."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Hunger)

        guards = FSMGuards()
        guards.register("hungry", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value > 50)

        eid = world.spawn()
        world.attach(eid, Hunger(value=75))
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [["hungry", "foraging"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "foraging"

    def test_first_match_wins(self):
        """With multiple guards, first True guard triggers, later ones ignored."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_true_1", lambda w, e: True)
        guards.register("always_true_2", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["always_true_1", "state_a"],
                    ["always_true_2", "state_b"],
                ],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should transition to state_a, not state_b
        fsm = world.get(eid, FSM)
        assert fsm.state == "state_a"

    def test_no_match_stays_in_state(self):
        """When no guards are True, entity stays in current state."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_false", lambda w, e: False)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [["always_false", "foraging"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should still be idle
        fsm = world.get(eid, FSM)
        assert fsm.state == "idle"

    def test_on_transition_callback_fires(self):
        """Callback called with (world, ctx, eid, old_state, new_state)."""
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
            }
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
        assert transitions_log[0] == (eid, "idle", "active")

    def test_on_transition_fires_after_state_update(self):
        """Inside callback, fsm.state already == new_state."""
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
            }
        ))

        captured_state = []

        def on_transition(w, ctx, e, old, new):
            # Capture the fsm.state inside the callback
            current_fsm = w.get(e, FSM)
            captured_state.append(current_fsm.state)

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - state should already be "active" inside callback
        assert len(captured_state) == 1
        assert captured_state[0] == "active"

    def test_no_on_transition_callback(self):
        """System works fine with on_transition=None."""
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
            }
        ))

        system = make_fsm_system(guards, on_transition=None)
        engine.add_system(system)

        # Act - should not raise any errors
        engine.step()

        # Assert
        fsm = world.get(eid, FSM)
        assert fsm.state == "active"

    def test_state_not_in_transitions(self):
        """Entity with state that has no transitions entry stays put, no error."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()

        eid = world.spawn()
        world.attach(eid, FSM(
            state="unknown_state",
            transitions={
                "idle": [["go", "active"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act - should not raise any errors
        engine.step()

        # Assert - should still be in unknown_state
        fsm = world.get(eid, FSM)
        assert fsm.state == "unknown_state"

    def test_at_most_one_transition_per_tick(self):
        """Even if new state has guards that would match, no second transition."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_true", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="state_a",
            transitions={
                "state_a": [["always_true", "state_b"]],
                "state_b": [["always_true", "state_c"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - should be in state_b, not state_c
        fsm = world.get(eid, FSM)
        assert fsm.state == "state_b"

    def test_multiple_entities(self):
        """Each entity transitions independently based on its own FSM and guards."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Hunger)

        guards = FSMGuards()
        guards.register("hungry", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value > 50)

        # Entity 1: hungry
        eid1 = world.spawn()
        world.attach(eid1, Hunger(value=75))
        world.attach(eid1, FSM(
            state="idle",
            transitions={"idle": [["hungry", "foraging"]]}
        ))

        # Entity 2: not hungry
        eid2 = world.spawn()
        world.attach(eid2, Hunger(value=25))
        world.attach(eid2, FSM(
            state="idle",
            transitions={"idle": [["hungry", "foraging"]]}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        assert world.get(eid1, FSM).state == "foraging"  # hungry, transitioned
        assert world.get(eid2, FSM).state == "idle"  # not hungry, stayed

    def test_multi_tick_transitions(self):
        """Entity transitions through multiple states across ticks."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("always_true", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="state_a",
            transitions={
                "state_a": [["always_true", "state_b"]],
                "state_b": [["always_true", "state_c"]],
                "state_c": [["always_true", "state_d"]],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act & Assert - each tick advances one state
        assert world.get(eid, FSM).state == "state_a"

        engine.step()
        assert world.get(eid, FSM).state == "state_b"

        engine.step()
        assert world.get(eid, FSM).state == "state_c"

        engine.step()
        assert world.get(eid, FSM).state == "state_d"

        # No more transitions defined for state_d
        engine.step()
        assert world.get(eid, FSM).state == "state_d"

    def test_guard_checks_entity_specific_state(self):
        """Guard inspects the specific entity's components."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Hunger)
        world.register_component(Energy)

        guards = FSMGuards()
        guards.register("hungry", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value > 50)
        guards.register("tired", lambda w, e: w.has(e, Energy) and w.get(e, Energy).value < 30)

        # Entity 1: hungry but not tired
        eid1 = world.spawn()
        world.attach(eid1, Hunger(value=75))
        world.attach(eid1, Energy(value=50))
        world.attach(eid1, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["hungry", "foraging"],
                    ["tired", "resting"],
                ]
            }
        ))

        # Entity 2: tired but not hungry
        eid2 = world.spawn()
        world.attach(eid2, Hunger(value=25))
        world.attach(eid2, Energy(value=20))
        world.attach(eid2, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["hungry", "foraging"],
                    ["tired", "resting"],
                ]
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert - each entity transitions based on its own state
        assert world.get(eid1, FSM).state == "foraging"  # hungry
        assert world.get(eid2, FSM).state == "resting"   # tired

    def test_fsm_serialization_round_trip(self):
        """FSM with transitions survives snapshot/restore."""
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

        # Advance one tick
        engine.step()
        assert world.get(eid, FSM).state == "active"

        # Act - snapshot and restore
        snapshot = engine.snapshot()

        # Create new engine and restore
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(FSM)
        system2 = make_fsm_system(guards)
        engine2.add_system(system2)
        engine2.restore(snapshot)

        # Assert - state preserved
        assert world2.get(eid, FSM).state == "active"

        # Verify transitions still work
        engine2.step()
        assert world2.get(eid, FSM).state == "done"

    def test_on_transition_can_modify_world(self):
        """Callback can attach/detach components, spawn entities."""
        # Arrange
        @dataclass
        class Marker:
            """Marker component to track callback execution."""
            value: str

        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Marker)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={"idle": [["go", "active"]]}
        ))

        spawned_entities = []

        def on_transition(w, ctx, e, old, new):
            # Attach a marker to the transitioning entity
            w.attach(e, Marker(value=f"transitioned from {old} to {new}"))
            # Spawn a new entity
            new_eid = w.spawn()
            spawned_entities.append(new_eid)

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        assert world.has(eid, Marker)
        marker = world.get(eid, Marker)
        assert marker.value == "transitioned from idle to active"
        assert len(spawned_entities) == 1

    def test_empty_transitions_dict(self):
        """FSM with empty transitions stays in current state."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={}
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()
        engine.step()

        # Assert
        assert world.get(eid, FSM).state == "idle"

    def test_complex_transition_chain(self):
        """Entity goes idle -> foraging -> idle -> resting across ticks as guards change."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)
        world.register_component(Hunger)
        world.register_component(Energy)

        guards = FSMGuards()
        guards.register("hungry", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value > 50)
        guards.register("full", lambda w, e: w.has(e, Hunger) and w.get(e, Hunger).value <= 50)
        guards.register("tired", lambda w, e: w.has(e, Energy) and w.get(e, Energy).value < 30)

        eid = world.spawn()
        world.attach(eid, Hunger(value=75))  # hungry
        world.attach(eid, Energy(value=80))  # energized
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["hungry", "foraging"],
                    ["tired", "resting"],
                ],
                "foraging": [
                    ["full", "idle"],
                    ["tired", "resting"],
                ],
                "resting": [
                    ["hungry", "foraging"],
                ],
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act & Assert - simulate state changes through component modification

        # Tick 1: idle -> foraging (hungry)
        engine.step()
        assert world.get(eid, FSM).state == "foraging"

        # Tick 2: foraging -> foraging (still hungry)
        engine.step()
        assert world.get(eid, FSM).state == "foraging"

        # Tick 3: become full, foraging -> idle
        world.get(eid, Hunger).value = 30
        engine.step()
        assert world.get(eid, FSM).state == "idle"

        # Tick 4: become tired, idle -> resting
        world.get(eid, Energy).value = 20
        engine.step()
        assert world.get(eid, FSM).state == "resting"

        # Tick 5: become hungry again, resting -> foraging
        world.get(eid, Hunger).value = 80
        engine.step()
        assert world.get(eid, FSM).state == "foraging"

    def test_transition_callback_receives_tick_context(self):
        """on_transition receives correct TickContext."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={"idle": [["go", "active"]]}
        ))

        captured_contexts = []

        def on_transition(w, ctx, e, old, new):
            captured_contexts.append({
                "tick": ctx.tick_number,
                "dt": ctx.dt,
                "elapsed": ctx.elapsed,
            })

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        assert len(captured_contexts) == 1
        assert captured_contexts[0]["tick"] == 1
        assert captured_contexts[0]["dt"] == 0.05  # 20 TPS = 0.05s per tick
        assert captured_contexts[0]["elapsed"] == 0.05

    def test_multiple_transitions_logged(self):
        """Track multiple transitions across multiple entities and ticks."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("go", lambda w, e: True)

        eid1 = world.spawn()
        world.attach(eid1, FSM(
            state="a",
            transitions={
                "a": [["go", "b"]],
                "b": [["go", "c"]],
            }
        ))

        eid2 = world.spawn()
        world.attach(eid2, FSM(
            state="x",
            transitions={
                "x": [["go", "y"]],
                "y": [["go", "z"]],
            }
        ))

        transitions_log = []

        def on_transition(w, ctx, e, old, new):
            transitions_log.append((e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()  # Both transition once
        engine.step()  # Both transition again

        # Assert
        assert len(transitions_log) == 4
        # First tick transitions
        assert (eid1, "a", "b") in transitions_log
        assert (eid2, "x", "y") in transitions_log
        # Second tick transitions
        assert (eid1, "b", "c") in transitions_log
        assert (eid2, "y", "z") in transitions_log

    def test_guard_order_matters(self):
        """Guards are evaluated in order; first match wins even if later ones would also match."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        call_order = []

        def guard_1(w, e):
            call_order.append("guard_1")
            return False

        def guard_2(w, e):
            call_order.append("guard_2")
            return True

        def guard_3(w, e):
            call_order.append("guard_3")
            return True

        guards = FSMGuards()
        guards.register("g1", guard_1)
        guards.register("g2", guard_2)
        guards.register("g3", guard_3)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={
                "idle": [
                    ["g1", "state_1"],
                    ["g2", "state_2"],
                    ["g3", "state_3"],
                ]
            }
        ))

        system = make_fsm_system(guards)
        engine.add_system(system)

        # Act
        engine.step()

        # Assert
        # guard_1 called (False), guard_2 called (True, wins), guard_3 NOT called
        assert call_order == ["guard_1", "guard_2"]
        assert world.get(eid, FSM).state == "state_2"

    def test_no_transition_callback_not_called(self):
        """on_transition not called when no transition occurs."""
        # Arrange
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(FSM)

        guards = FSMGuards()
        guards.register("never", lambda w, e: False)

        eid = world.spawn()
        world.attach(eid, FSM(
            state="idle",
            transitions={"idle": [["never", "active"]]}
        ))

        callback_calls = []

        def on_transition(w, ctx, e, old, new):
            callback_calls.append((e, old, new))

        system = make_fsm_system(guards, on_transition=on_transition)
        engine.add_system(system)

        # Act
        engine.step()
        engine.step()

        # Assert
        assert len(callback_calls) == 0
        assert world.get(eid, FSM).state == "idle"
