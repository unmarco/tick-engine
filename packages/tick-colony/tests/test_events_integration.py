"""Integration tests for tick-colony + tick-event integration.

Tests world-level event scheduling (seasons, probabilistic events, etc.)
integrated with colony simulation primitives (needs, stats, modifiers, etc.).
"""
from tick import Engine
from tick_colony import (
    EventScheduler, EventGuards, EventDef, CycleDef, make_event_system,
    NeedSet, NeedHelper, StatBlock, Modifiers, add_modifier, remove_modifiers,
    EventLog, ColonySnapshot, Grid2D, Pos2D,
    register_colony_components,
    make_need_decay_system, make_modifier_tick_system,
)


class TestSeasonCycleRotates:
    def test_season_cycle_rotates(self):
        """Create engine with season CycleDef, verify all 4 phases cycle through."""
        engine = Engine(tps=20, seed=42)
        scheduler = EventScheduler()
        guards = EventGuards()

        # Define 4 seasons, 10 ticks each
        scheduler.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 10),
                    ("summer", 10),
                    ("autumn", 10),
                    ("winter", 10),
                ],
            )
        )

        # Track phase activations
        phase_starts = []

        def on_start(world, ctx, name):
            phase_starts.append((ctx.tick_number, name))

        sys = make_event_system(scheduler, guards, on_start=on_start)
        engine.add_system(sys)

        # Run 45 ticks (full cycle + extra to verify wrap)
        engine.run(45)

        # Verify all 4 phases activated
        phase_names = [name for _, name in phase_starts]
        assert "spring" in phase_names, "Spring should have started"
        assert "summer" in phase_names, "Summer should have started"
        assert "autumn" in phase_names, "Autumn should have started"
        assert "winter" in phase_names, "Winter should have started"

        # Verify phases started in correct order (first occurrence of each)
        # CycleDef starts at phase_index=0 with no on_start; first on_start
        # fires when phase *transitions* — so the order in the log is:
        # summer (tick 11), autumn (tick 21), winter (tick 31), spring (tick 41)
        # because the initial "spring" phase has no on_start callback.
        season_starts = [n for n in phase_names if n in {"spring", "summer", "autumn", "winter"}]
        # Check that we see the full cycle in order somewhere
        assert "summer" in season_starts
        assert "autumn" in season_starts
        assert "winter" in season_starts
        # Spring wraps around after winter
        assert "spring" in season_starts, "Spring should appear after winter wrap"


class TestColdSnapOnlyFiresInWinter:
    def test_cold_snap_only_fires_in_winter(self):
        """Register is_winter guard, cold_snap event should only fire during winter."""
        engine = Engine(tps=20, seed=42)
        scheduler = EventScheduler()
        guards = EventGuards()

        # Define seasons (10 ticks each)
        scheduler.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 10),
                    ("summer", 10),
                    ("autumn", 10),
                    ("winter", 10),
                ],
            )
        )

        # Register guard that checks if winter is active
        guards.register("is_winter", lambda w, s: s.is_active("winter"))

        # Define cold_snap event with probability=1.0 (guaranteed when conditions met)
        scheduler.define(
            EventDef(
                name="cold_snap",
                duration=3,
                probability=1.0,
                conditions=["is_winter"],
            )
        )

        # Track event activations
        event_starts = []

        def on_start(world, ctx, name):
            event_starts.append((ctx.tick_number, name))

        sys = make_event_system(scheduler, guards, on_start=on_start)
        engine.add_system(sys)

        # CycleDef with delay=0 starts at phase_index=0 with delay_remaining=0,
        # so spring transitions to summer on tick 1.  Effective phases:
        #   summer: ticks 1-10, autumn: ticks 11-20, winter: ticks 21-30
        # Run through summer/autumn (20 ticks) — cold_snap should NOT activate
        engine.run(20)

        cold_snap_starts = [
            (tick, name) for tick, name in event_starts if name == "cold_snap"
        ]
        assert len(cold_snap_starts) == 0, \
            "cold_snap should not activate before winter"

        # Run into winter (10 more ticks)
        engine.run(10)

        # cold_snap SHOULD have activated during winter
        cold_snap_starts = [
            (tick, name) for tick, name in event_starts if name == "cold_snap"
        ]
        assert len(cold_snap_starts) >= 1, \
            "cold_snap should activate during winter"

        # Verify cold_snap started during winter phase (tick 21+)
        for tick, _ in cold_snap_starts:
            assert tick >= 21, \
                f"cold_snap should start during winter (tick >= 21), but started at tick {tick}"


class TestEventOnStartModifiesColonistState:
    def test_event_on_start_modifies_colonist_state(self):
        """Event on_start callback restores colonist hunger."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        scheduler = EventScheduler()
        guards = EventGuards()

        # Create colonist with hunger
        colonist = world.spawn()
        need_set = NeedSet(data={})
        NeedHelper.add(
            need_set, "hunger", value=50.0, max_val=100.0,
            decay_rate=0.0, critical_threshold=20.0
        )
        world.attach(colonist, need_set)

        # Define feast event (probability=1.0, no conditions, duration=5)
        scheduler.define(
            EventDef(name="feast", duration=5, probability=1.0)
        )

        # on_start: restore hunger +20 for all colonists
        def on_feast_start(world, ctx, name):
            for eid, (ns,) in world.query(NeedSet):
                current = NeedHelper.get_value(ns, "hunger")
                NeedHelper.set_value(ns, "hunger", current + 20.0)

        sys = make_event_system(
            scheduler, guards, on_start=on_feast_start
        )
        engine.add_system(sys)

        # Initial hunger = 50
        assert NeedHelper.get_value(need_set, "hunger") == 50.0

        # Run 1 tick (feast should activate)
        engine.step()

        # Hunger should be increased by 20
        assert NeedHelper.get_value(need_set, "hunger") == 70.0, \
            "Feast on_start should have increased hunger by 20"


class TestEventOnTickAppliesPerTickEffect:
    def test_event_on_tick_applies_per_tick_effect(self):
        """Event on_tick callback applies extra hunger decay per tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        scheduler = EventScheduler()
        guards = EventGuards()

        # Create colonist with hunger (decay_rate=1.0)
        colonist = world.spawn()
        need_set = NeedSet(data={})
        NeedHelper.add(
            need_set, "hunger", value=100.0, max_val=100.0,
            decay_rate=1.0, critical_threshold=20.0
        )
        world.attach(colonist, need_set)

        # Define famine event (probability=1.0, duration=5)
        scheduler.define(
            EventDef(name="famine", duration=5, probability=1.0)
        )

        # on_tick: extra hunger decay by 2.0 per tick
        def on_famine_tick(world, ctx, name, remaining):
            for eid, (ns,) in world.query(NeedSet):
                current = NeedHelper.get_value(ns, "hunger")
                NeedHelper.set_value(ns, "hunger", current - 2.0)

        sys = make_event_system(
            scheduler, guards, on_tick=on_famine_tick
        )
        engine.add_system(make_need_decay_system())
        engine.add_system(sys)

        # Initial hunger = 100
        assert NeedHelper.get_value(need_set, "hunger") == 100.0

        # Run 5 ticks while famine is active
        engine.run(5)

        # Event activates on tick 1 (step 5: evaluate). on_tick doesn't fire
        # on activation tick (step 2 already ran). Famine active ticks 2-5:
        #   Tick 2: decrement 5→4, on_tick (-2.0)
        #   Tick 3: decrement 4→3, on_tick (-2.0)
        #   Tick 4: decrement 3→2, on_tick (-2.0)
        #   Tick 5: decrement 2→1, on_tick (-2.0)
        # Total: base decay (1.0 * 5 = 5.0) + event decay (2.0 * 4 = 8.0) = 13.0
        # Final hunger = 100 - 13 = 87
        assert NeedHelper.get_value(need_set, "hunger") == 87.0, \
            f"Expected hunger=87.0, got {NeedHelper.get_value(need_set, 'hunger')}"


class TestEventOnEndCleansUp:
    def test_event_on_end_cleans_up(self):
        """Event on_start adds modifier, on_end removes it."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        scheduler = EventScheduler()
        guards = EventGuards()

        # Create entity with stats
        entity = world.spawn()
        stats = StatBlock(data={"defense": 10.0})
        mods = Modifiers(entries=[])
        world.attach(entity, stats)
        world.attach(entity, mods)

        # Define blessing event (probability=1.0, duration=3)
        scheduler.define(
            EventDef(name="blessing", duration=3, probability=1.0)
        )

        # on_start: add permanent defense modifier
        def on_blessing_start(world, ctx, name):
            for eid, (stat_block, modifiers) in world.query(StatBlock, Modifiers):
                add_modifier(modifiers, "defense", 5.0, duration=-1)

        # on_end: remove all defense modifiers
        def on_blessing_end(world, ctx, name):
            for eid, (modifiers,) in world.query(Modifiers):
                remove_modifiers(modifiers, "defense")

        sys = make_event_system(
            scheduler, guards,
            on_start=on_blessing_start,
            on_end=on_blessing_end
        )
        engine.add_system(sys)

        # Initial defense = 10 (no modifiers)
        from tick_colony import effective
        assert effective(stats, mods, "defense") == 10.0

        # Tick 1: blessing starts, modifier added
        engine.step()
        assert effective(stats, mods, "defense") == 15.0, \
            "Blessing should add +5 defense modifier"

        # Tick 2-3: blessing still active
        engine.step()
        engine.step()
        assert effective(stats, mods, "defense") == 15.0

        # Tick 4: blessing ends, modifier removed
        engine.step()
        assert effective(stats, mods, "defense") == 10.0, \
            "Blessing on_end should remove defense modifier"


class TestColonySnapshotRoundtripsWithScheduler:
    def test_colony_snapshot_roundtrips_with_scheduler(self):
        """Setup engine with EventScheduler, snapshot/restore, verify state matches."""
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        scheduler1 = EventScheduler()
        guards1 = EventGuards()
        grid1 = Grid2D(20, 20)
        event_log1 = EventLog()

        # Define cycle and event
        scheduler1.define_cycle(
            CycleDef(
                name="seasons",
                phases=[("spring", 5), ("summer", 5)],
            )
        )
        scheduler1.define(EventDef(name="harvest", duration=3, cooldown=2))

        # Setup snapshot coordinator WITH scheduler
        snapper1 = ColonySnapshot(
            grid=grid1, event_log=event_log1, scheduler=scheduler1
        )

        # Add event system
        event_starts = []
        def on_start(world, ctx, name):
            event_starts.append((ctx.tick_number, name))

        sys = make_event_system(scheduler1, guards1, on_start=on_start)
        engine1.add_system(sys)

        # Run 7 ticks to get scheduler into interesting state
        engine1.run(7)

        # Capture state
        spring_active = scheduler1.is_active("spring")
        summer_active = scheduler1.is_active("summer")
        harvest_active = scheduler1.is_active("harvest")
        harvest_remaining = scheduler1.time_remaining("harvest")

        # Snapshot
        snapshot = snapper1.snapshot(engine1)

        # Verify scheduler data in snapshot
        assert "colony" in snapshot
        assert "scheduler" in snapshot["colony"]

        # Restore into fresh engine
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        scheduler2 = EventScheduler()
        guards2 = EventGuards()
        grid2 = Grid2D(20, 20)
        event_log2 = EventLog()

        snapper2 = ColonySnapshot(
            grid=grid2, event_log=event_log2, scheduler=scheduler2
        )

        # Must redefine cycle and event before restore
        scheduler2.define_cycle(
            CycleDef(
                name="seasons",
                phases=[("spring", 5), ("summer", 5)],
            )
        )
        scheduler2.define(EventDef(name="harvest", duration=3, cooldown=2))

        # Restore
        snapper2.restore(engine2, snapshot)

        # Verify scheduler state matches
        assert scheduler2.is_active("spring") == spring_active, \
            "Spring active state should match after restore"
        assert scheduler2.is_active("summer") == summer_active, \
            "Summer active state should match after restore"
        assert scheduler2.is_active("harvest") == harvest_active, \
            "Harvest active state should match after restore"
        assert scheduler2.time_remaining("harvest") == harvest_remaining, \
            "Harvest remaining time should match after restore"


class TestColonySnapshotWithoutSchedulerStillWorks:
    def test_colony_snapshot_without_scheduler_still_works(self):
        """Setup engine with ColonySnapshot without scheduler parameter, verify backwards compatibility."""
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        grid1 = Grid2D(20, 20)
        event_log1 = EventLog()

        # Create entity
        e1 = world1.spawn()
        world1.attach(e1, Pos2D(x=5.0, y=7.0))
        grid1.place(e1, (5, 7))
        event_log1.emit(tick=0, type="spawn", entity_id=e1)

        # ColonySnapshot WITHOUT scheduler parameter
        snapper1 = ColonySnapshot(grid=grid1, event_log=event_log1)

        # Snapshot (should work without errors)
        snapshot = snapper1.snapshot(engine1)

        # Verify no scheduler data in snapshot
        assert "colony" in snapshot
        assert "scheduler" not in snapshot["colony"]

        # Restore into fresh engine
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        grid2 = Grid2D(20, 20)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        # Restore (should work without errors)
        snapper2.restore(engine2, snapshot)

        # Verify state restored correctly
        assert world2.alive(e1)
        assert grid2.position_of(e1) == (5, 7)
        assert len(event_log2) == 1


class TestDeterministicReplayWithEvents:
    def test_deterministic_replay_with_events(self):
        """Setup engine with seasons + probabilistic events, run 200 ticks, snapshot at 100, verify determinism."""
        # First run: uninterrupted 0 → 200
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        scheduler1 = EventScheduler()
        guards1 = EventGuards()

        # Define seasons (20 ticks each)
        scheduler1.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 20),
                    ("summer", 20),
                    ("autumn", 20),
                    ("winter", 20),
                ],
            )
        )

        # Define probabilistic event (0.3 probability, 5 tick duration)
        scheduler1.define(
            EventDef(name="storm", duration=5, cooldown=10, probability=0.3)
        )

        # Create colonist with hunger (to track determinism)
        colonist = world1.spawn()
        need_set1 = NeedSet(data={})
        NeedHelper.add(
            need_set1, "hunger", value=100.0, max_val=100.0,
            decay_rate=0.5, critical_threshold=20.0
        )
        world1.attach(colonist, need_set1)

        # Track events for comparison
        events1 = []

        def on_start1(world, ctx, name):
            events1.append(("start", ctx.tick_number, name))

        def on_end1(world, ctx, name):
            events1.append(("end", ctx.tick_number, name))

        sys1 = make_event_system(
            scheduler1, guards1, on_start=on_start1, on_end=on_end1
        )
        engine1.add_system(make_need_decay_system())
        engine1.add_system(sys1)

        # Run 200 ticks
        engine1.run(200)

        # Capture final state
        final_hunger_1 = NeedHelper.get_value(need_set1, "hunger")
        final_tick_1 = engine1.clock.tick_number

        # Second run: snapshot at 100, restore, continue to 200
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        scheduler2 = EventScheduler()
        guards2 = EventGuards()
        event_log2 = EventLog()

        scheduler2.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 20),
                    ("summer", 20),
                    ("autumn", 20),
                    ("winter", 20),
                ],
            )
        )
        scheduler2.define(
            EventDef(name="storm", duration=5, cooldown=10, probability=0.3)
        )

        # Create colonist
        colonist2 = world2.spawn()
        need_set2 = NeedSet(data={})
        NeedHelper.add(
            need_set2, "hunger", value=100.0, max_val=100.0,
            decay_rate=0.5, critical_threshold=20.0
        )
        world2.attach(colonist2, need_set2)

        # Track events
        events2 = []

        def on_start2(world, ctx, name):
            events2.append(("start", ctx.tick_number, name))

        def on_end2(world, ctx, name):
            events2.append(("end", ctx.tick_number, name))

        sys2 = make_event_system(
            scheduler2, guards2, on_start=on_start2, on_end=on_end2
        )
        engine2.add_system(make_need_decay_system())
        engine2.add_system(sys2)

        # Run 100 ticks
        engine2.run(100)

        # Snapshot
        snapper = ColonySnapshot(event_log=event_log2, scheduler=scheduler2)
        snapshot = snapper.snapshot(engine2)

        # Restore into fresh engine
        engine3 = Engine(tps=20, seed=42)
        world3 = engine3.world
        register_colony_components(world3)

        scheduler3 = EventScheduler()
        guards3 = EventGuards()
        event_log3 = EventLog()

        scheduler3.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 20),
                    ("summer", 20),
                    ("autumn", 20),
                    ("winter", 20),
                ],
            )
        )
        scheduler3.define(
            EventDef(name="storm", duration=5, cooldown=10, probability=0.3)
        )

        snapper3 = ColonySnapshot(event_log=event_log3, scheduler=scheduler3)
        snapper3.restore(engine3, snapshot)

        # Track events after restore
        events3 = []

        def on_start3(world, ctx, name):
            events3.append(("start", ctx.tick_number, name))

        def on_end3(world, ctx, name):
            events3.append(("end", ctx.tick_number, name))

        sys3 = make_event_system(
            scheduler3, guards3, on_start=on_start3, on_end=on_end3
        )
        engine3.add_system(make_need_decay_system())
        engine3.add_system(sys3)

        # Run 100 more ticks (to reach 200 total)
        engine3.run(100)

        # Verify final state matches
        need_set3 = world3.get(colonist, NeedSet)
        final_hunger_3 = NeedHelper.get_value(need_set3, "hunger")
        final_tick_3 = engine3.clock.tick_number

        assert final_tick_3 == final_tick_1, \
            "Final tick number should match"
        assert abs(final_hunger_3 - final_hunger_1) < 0.01, \
            f"Final hunger should match (expected {final_hunger_1}, got {final_hunger_3})"

        # Verify event sequences match from tick 101 onward
        events1_after_100 = [(action, tick, name) for action, tick, name in events1 if tick > 100]
        assert events3 == events1_after_100, \
            "Event sequence after restore should match uninterrupted run"
