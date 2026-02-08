"""Integration tests for FSM extension with colony components."""

import pytest
from tick import Engine
from tick_colony import (
    FSM, FSMGuards, make_fsm_system,
    Timer, make_timer_system,
    NeedSet, NeedHelper,
    make_need_decay_system,
    register_colony_components,
)


class TestFSMIntegration:
    """Test FSM guards, transitions, and on_transition callback in colony context."""

    def test_basic_fsm_transition(self):
        """FSM with 'always' guard transitions immediately."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={"idle": [["always", "working"]]}))

        # Register guard
        guards = FSMGuards()
        guards.register("always", lambda world, eid: True)

        # Add system
        engine.add_system(make_fsm_system(guards))

        # Step once
        engine.step()

        # Verify transition
        fsm = world.get(e1, FSM)
        assert fsm.state == "working"

    def test_guard_blocks_transition(self):
        """FSM guard that checks NeedSet blocks transition when condition not met."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and NeedSet
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={"idle": [["is_hungry", "foraging"]]}))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=80.0, max_val=100.0, decay_rate=1.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        # Register guard that checks hunger < 40
        guards = FSMGuards()
        guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)

        # Add system
        engine.add_system(make_fsm_system(guards))

        # Step once
        engine.step()

        # Verify stays idle (hunger=80, not < 40)
        fsm = world.get(e1, FSM)
        assert fsm.state == "idle"

    def test_guard_allows_transition(self):
        """FSM guard allows transition when condition is met."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and NeedSet
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={"idle": [["is_hungry", "foraging"]]}))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=20.0, max_val=100.0, decay_rate=1.0, critical_threshold=10.0)
        world.attach(e1, need_set)

        # Register guard that checks hunger < 40
        guards = FSMGuards()
        guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)

        # Add system
        engine.add_system(make_fsm_system(guards))

        # Step once
        engine.step()

        # Verify transitions to foraging (hunger=20, which is < 40)
        fsm = world.get(e1, FSM)
        assert fsm.state == "foraging"

    def test_on_transition_callback(self):
        """on_transition callback is invoked with correct parameters."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={"idle": [["always", "foraging"]]}))

        # Register guard
        guards = FSMGuards()
        guards.register("always", lambda w, eid: True)

        # Track transitions
        transitions = []

        def on_transition(world, ctx, eid, old_state, new_state):
            transitions.append((old_state, new_state))

        # Add system with callback
        engine.add_system(make_fsm_system(guards, on_transition=on_transition))

        # Step once
        engine.step()

        # Verify callback called
        assert len(transitions) == 1
        assert transitions[0] == ("idle", "foraging")

    def test_timer_done_guard(self):
        """FSM transitions when Timer completes, using timer_done guard."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and Timer
        e1 = world.spawn()
        world.attach(e1, FSM(state="foraging", transitions={"foraging": [["timer_done", "idle"]]}))
        world.attach(e1, Timer(name="forage", remaining=2))

        # Register guards
        guards = FSMGuards()
        guards.register("timer_done", lambda w, eid: not w.has(eid, Timer))

        # Add systems (timer_system first, then fsm_system)
        def on_fire(world, ctx, eid, timer):
            pass  # Timer auto-detaches

        engine.add_system(make_timer_system(on_fire=on_fire))
        engine.add_system(make_fsm_system(guards))

        # After 1 tick: still foraging (timer not done)
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "foraging"
        assert world.has(e1, Timer)

        # After 2nd tick: Timer fires, then FSM transitions
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "idle"
        assert not world.has(e1, Timer)

    def test_full_decision_cycle(self):
        """Complete idle → foraging → idle cycle with on_transition attaching Timer."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and low hunger
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={
            "idle": [["is_hungry", "foraging"]],
            "foraging": [["timer_done", "idle"]],
        }))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=30.0, max_val=100.0, decay_rate=1.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        # Register guards
        guards = FSMGuards()
        guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)
        guards.register("timer_done", lambda w, eid: not w.has(eid, Timer))

        # On transition to foraging, attach Timer
        def on_transition(world, ctx, eid, old_state, new_state):
            if new_state == "foraging":
                world.attach(eid, Timer(name="forage", remaining=3))

        # Add systems
        def on_fire(world, ctx, eid, timer):
            pass  # Timer auto-detaches

        engine.add_system(make_timer_system(on_fire=on_fire))
        engine.add_system(make_fsm_system(guards, on_transition=on_transition))

        # Tick 1: idle → foraging (is_hungry), Timer attached
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "foraging"
        assert world.has(e1, Timer)

        # Tick 2-3: foraging, Timer counting down
        engine.step()
        assert world.get(e1, FSM).state == "foraging"
        engine.step()
        assert world.get(e1, FSM).state == "foraging"

        # Tick 4: Timer fires, foraging → idle
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "idle"
        assert not world.has(e1, Timer)

    def test_multiple_guards_priority(self):
        """First matching guard wins when multiple guards are true."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and NeedSet
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={
            "idle": [
                ["is_hungry", "foraging"],
                ["is_tired", "resting"],
                ["always", "building"],
            ]
        }))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=30.0, max_val=100.0, decay_rate=1.0, critical_threshold=20.0)
        NeedHelper.add(need_set, "energy", value=15.0, max_val=100.0, decay_rate=1.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        # Register guards (both hungry and tired are true)
        guards = FSMGuards()
        guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)
        guards.register("is_tired", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "energy") < 20.0)
        guards.register("always", lambda w, eid: True)

        # Add system
        engine.add_system(make_fsm_system(guards))

        # Step once
        engine.step()

        # Verify first matching guard wins (is_hungry → foraging)
        fsm = world.get(e1, FSM)
        assert fsm.state == "foraging"

    def test_fsm_with_colony_needs(self):
        """Full integration: FSM + NeedSet + Timer + need_decay_system.

        System order: need_decay → timer → fsm.
        Tick 1: hunger 44→39 (< 40), fsm idle→foraging, Timer(remaining=2) attached.
        Tick 2: hunger 39→34, Timer 2→1, fsm stays foraging.
        Tick 3: hunger 34→29, Timer fires (restored to 100), hunger 100→95 from decay already applied, fsm foraging→idle.
        """
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # Create entity with FSM and NeedSet just above threshold
        e1 = world.spawn()
        world.attach(e1, FSM(state="idle", transitions={
            "idle": [["is_hungry", "foraging"]],
            "foraging": [["timer_done", "idle"]],
        }))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=44.0, max_val=100.0, decay_rate=5.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        # Register guards
        guards = FSMGuards()
        guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)
        guards.register("timer_done", lambda w, eid: not w.has(eid, Timer))

        # On transition to foraging, attach Timer
        def on_transition(world, ctx, eid, old_state, new_state):
            if new_state == "foraging":
                world.attach(eid, Timer(name="forage", remaining=2))

        # Add systems: need_decay first, then timer, then fsm
        def on_fire(world, ctx, eid, timer):
            # Restore hunger when foraging completes
            ns = world.get(eid, NeedSet)
            NeedHelper.set_value(ns, "hunger", 100.0)

        engine.add_system(make_need_decay_system())
        engine.add_system(make_timer_system(on_fire=on_fire))
        engine.add_system(make_fsm_system(guards, on_transition=on_transition))

        # Tick 1: hunger 44→39 (< 40), fsm transitions idle→foraging
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "foraging"
        assert NeedHelper.get_value(need_set, "hunger") == 39.0

        # Tick 2: hunger 39→34, Timer 2→1, still foraging
        engine.step()
        assert world.get(e1, FSM).state == "foraging"
        assert NeedHelper.get_value(need_set, "hunger") == 34.0

        # Tick 3: hunger 34→29, Timer fires (hunger→100), then decayed to 100 (decay already applied), fsm→idle
        engine.step()
        fsm = world.get(e1, FSM)
        assert fsm.state == "idle"
        # Need decay ran first (34→29), then timer fired (29→100)
        assert NeedHelper.get_value(need_set, "hunger") == 100.0
        assert not world.has(e1, Timer)
