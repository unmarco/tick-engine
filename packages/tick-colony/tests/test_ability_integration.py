"""Tests for tick-ability integration in tick-colony."""

import random

from tick import Engine
from tick_colony import (
    AbilityDef,
    AbilityState,
    AbilityGuards,
    AbilityManager,
    make_ability_system,
    NeedSet,
    NeedHelper,
    ColonySnapshot,
    register_colony_components,
)


class TestAbilityIntegration:
    """Test tick-ability re-exports and colony integration."""

    def test_all_exports_importable(self):
        """All 5 tick-ability exports importable from tick_colony."""
        assert AbilityDef is not None
        assert AbilityState is not None
        assert AbilityGuards is not None
        assert AbilityManager is not None
        assert callable(make_ability_system)

    def test_invoke_and_system_processing(self):
        """AbilityManager invoke + make_ability_system tick processing."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        mgr = AbilityManager()
        mgr.define(AbilityDef(name="heal", duration=3, cooldown=2, max_charges=2))

        started = []
        ended = []

        def on_start(world, ctx, name):
            started.append((ctx.tick_number, name))

        def on_end(world, ctx, name):
            ended.append((ctx.tick_number, name))

        engine.add_system(make_ability_system(mgr, on_start=on_start, on_end=on_end))

        # Invoke heal ability
        ctx = engine.clock.context(lambda: None, random.Random(42))
        assert mgr.invoke("heal", world, ctx)

        # Ability should be pending (active_started_at set, active_remaining=3)
        state = mgr.state("heal")
        assert state is not None
        assert state.active_remaining == 3
        assert state.active_started_at != -1
        assert mgr.charges("heal") == 1  # consumed one charge

        # Step 1: on_start fires, active_remaining decremented 3->2
        engine.step()
        assert len(started) == 1
        assert started[0][1] == "heal"
        assert mgr.is_active("heal")

        # Step 2: active_remaining 2->1
        engine.step()
        assert mgr.is_active("heal")

        # Step 3: active_remaining 1->0, on_end fires
        engine.step()
        assert not mgr.is_active("heal")
        assert len(ended) == 1
        assert ended[0][1] == "heal"

    def test_ability_guards_with_need_set(self):
        """AbilityGuards checking world state (NeedSet threshold)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        # Create entity with low energy
        eid = world.spawn()
        need_set = NeedSet(data={})
        NeedHelper.add(
            need_set, "energy", value=10.0, max_val=100.0,
            decay_rate=0.0, critical_threshold=20.0,
        )
        world.attach(eid, need_set)

        mgr = AbilityManager()
        mgr.define(AbilityDef(
            name="sprint", duration=5, max_charges=1,
            conditions=["has_energy"],
        ))

        guards = AbilityGuards()
        # Guard: at least one entity must have energy >= 30
        guards.register("has_energy", lambda w, m: any(
            NeedHelper.get_value(ns, "energy") >= 30.0
            for _, (ns,) in w.query(NeedSet)
        ))

        engine.add_system(make_ability_system(mgr, guards=guards))

        # Invoke should fail -- energy is 10 (< 30)
        ctx = engine.clock.context(lambda: None, random.Random(42))
        assert not mgr.invoke("sprint", world, ctx, guards=guards)

        # Restore energy to 50
        NeedHelper.set_value(need_set, "energy", 50.0)

        # Now invoke should succeed
        ctx2 = engine.clock.context(lambda: None, random.Random(42))
        assert mgr.invoke("sprint", world, ctx2, guards=guards)

    def test_ability_manager_snapshot_via_colony_snapshot(self):
        """AbilityManager snapshot roundtrip via ColonySnapshot."""
        mgr = AbilityManager()
        mgr.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))

        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        # Invoke to create some runtime state
        ctx = engine.clock.context(lambda: None, random.Random(42))
        mgr.invoke("heal", engine.world, ctx)

        # Snapshot
        snapper = ColonySnapshot(ability_manager=mgr)
        data = snapper.snapshot(engine)
        assert "ability_manager" in data["colony"]

        # Capture state for comparison
        orig_state = mgr.state("heal")
        assert orig_state is not None
        orig_charges = orig_state.charges
        orig_active = orig_state.active_remaining

        # Restore into fresh manager
        mgr2 = AbilityManager()
        mgr2.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot(ability_manager=mgr2)
        snapper2.restore(engine2, data)

        # Verify state matches
        restored_state = mgr2.state("heal")
        assert restored_state is not None
        assert restored_state.charges == orig_charges
        assert restored_state.active_remaining == orig_active

    def test_colony_snapshot_without_ability_manager(self):
        """ColonySnapshot without ability_manager still works."""
        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        engine.world.attach(eid, NeedSet(data={}))

        snapper = ColonySnapshot()
        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert "ability_manager" not in snapshot["colony"]

        # Restore should work without error
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot()
        snapper2.restore(engine2, snapshot)
        assert engine2.world.alive(eid)

    def test_deterministic_replay(self):
        """Snapshot, restore, run same ticks, same state."""
        # First run
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        mgr1 = AbilityManager()
        mgr1.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))

        engine1.add_system(make_ability_system(mgr1))

        # Invoke and run a few ticks
        ctx = engine1.clock.context(lambda: None, random.Random(42))
        mgr1.invoke("heal", world1, ctx)

        engine1.run(3)

        # Snapshot at tick 3
        snapper1 = ColonySnapshot(ability_manager=mgr1)
        data = snapper1.snapshot(engine1)

        # Continue first run for 5 more ticks
        engine1.run(5)

        state1_final = mgr1.state("heal")
        assert state1_final is not None

        # Second run: restore from tick 3, run same 5 more ticks
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        mgr2 = AbilityManager()
        mgr2.define(AbilityDef(name="heal", duration=5, cooldown=3, max_charges=2))

        snapper2 = ColonySnapshot(ability_manager=mgr2)
        snapper2.restore(engine2, data)

        engine2.add_system(make_ability_system(mgr2))

        engine2.run(5)

        # Verify state matches
        state2_final = mgr2.state("heal")
        assert state2_final is not None
        assert state2_final.charges == state1_final.charges
        assert state2_final.cooldown_remaining == state1_final.cooldown_remaining
        assert state2_final.active_remaining == state1_final.active_remaining
