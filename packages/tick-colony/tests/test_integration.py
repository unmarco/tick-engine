"""Integration tests for colony package - multi-system scenarios."""

import pytest
from tick_colony import (
    Grid, Position, Action, NeedSet, NeedHelper, StatBlock, Modifiers,
    make_grid_cleanup_system, make_action_system, make_need_decay_system,
    make_modifier_tick_system, effective, add_modifier, EventLog, ColonySnapshot,
    register_colony_components
)
from tick import Engine


class TestMultiSystemScenario:
    def test_entity_with_all_components(self):
        """Entity with Position + Action + NeedSet + StatBlock + Modifiers."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(20, 20)
        event_log = EventLog()

        # Create entity with all component types
        e1 = world.spawn()
        world.attach(e1, Position(x=10, y=10))
        world.attach(e1, Action(name="gather", total_ticks=5))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "hunger", value=100.0, max_val=100.0, decay_rate=2.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        stats = StatBlock(data={"strength": 10.0, "speed": 5.0})
        mods = Modifiers(entries=[])
        add_modifier(mods, "strength", 5.0, duration=3)
        world.attach(e1, stats)
        world.attach(e1, mods)

        grid.rebuild(world)

        # Verify all components attached
        assert world.has(e1, Position)
        assert world.has(e1, Action)
        assert world.has(e1, NeedSet)
        assert world.has(e1, StatBlock)
        assert world.has(e1, Modifiers)

        # Verify initial state
        assert grid.position_of(e1) == (10, 10)
        assert effective(stats, mods, "strength") == 15.0

    def test_systems_run_together(self):
        """Need decay + action progress + modifier tick all working together."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()

        # Action component
        world.attach(e1, Action(name="task", total_ticks=3))

        # NeedSet component
        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "energy", value=50.0, max_val=100.0, decay_rate=5.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        # Stats with modifiers
        stats = StatBlock(data={"power": 10.0})
        mods = Modifiers(entries=[])
        add_modifier(mods, "power", 5.0, duration=2)
        world.attach(e1, stats)
        world.attach(e1, mods)

        # Add systems
        action_completed = []
        def on_complete(world, ctx, eid, action):
            action_completed.append(ctx.tick_number)

        engine.add_system(make_action_system(on_complete=on_complete))
        engine.add_system(make_need_decay_system())
        engine.add_system(make_modifier_tick_system())

        # Tick 1
        engine.step()
        assert world.has(e1, Action)  # Action not done yet
        assert NeedHelper.get_value(need_set, "energy") == 45.0
        assert effective(stats, mods, "power") == 15.0  # Modifier still active (1 tick left)

        # Tick 2
        engine.step()
        assert world.has(e1, Action)
        assert NeedHelper.get_value(need_set, "energy") == 40.0
        assert effective(stats, mods, "power") == 10.0  # Modifier expired

        # Tick 3
        engine.step()
        assert not world.has(e1, Action)  # Action completed
        assert NeedHelper.get_value(need_set, "energy") == 35.0
        assert len(action_completed) == 1

    def test_deterministic_replay_scenario(self):
        """Run N ticks, snapshot, run M more; new engine restore, run M more, compare."""
        # First run
        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        grid1 = Grid(20, 20)
        event_log1 = EventLog()
        snapper1 = ColonySnapshot(grid=grid1, event_log=event_log1)

        # Create entity with multiple components
        e1 = world1.spawn()
        world1.attach(e1, Position(x=10, y=10))

        need_set1 = NeedSet(data={})
        NeedHelper.add(need_set1, "hunger", value=100.0, max_val=100.0, decay_rate=3.0, critical_threshold=20.0)
        world1.attach(e1, need_set1)

        stats1 = StatBlock(data={"strength": 10.0})
        mods1 = Modifiers(entries=[])
        add_modifier(mods1, "strength", 5.0, duration=5)
        world1.attach(e1, stats1)
        world1.attach(e1, mods1)

        grid1.rebuild(world1)

        # Add systems
        engine1.add_system(make_need_decay_system())
        engine1.add_system(make_modifier_tick_system())

        # Run N=5 ticks
        for _ in range(5):
            engine1.step()
            event_log1.emit(tick=engine1.clock.tick_number, type="tick")

        # Capture state after 5 ticks
        hunger_after_5 = NeedHelper.get_value(need_set1, "hunger")
        strength_after_5 = effective(stats1, mods1, "strength")

        # Take snapshot
        snapshot = snapper1.snapshot(engine1)

        # Continue for M=3 more ticks
        for _ in range(3):
            engine1.step()
            event_log1.emit(tick=engine1.clock.tick_number, type="tick")

        hunger_after_8 = NeedHelper.get_value(need_set1, "hunger")
        strength_after_8 = effective(stats1, mods1, "strength")

        # Second run: restore from snapshot and run M=3 ticks
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        grid2 = Grid(20, 20)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        # Add systems to engine2
        engine2.add_system(make_need_decay_system())
        engine2.add_system(make_modifier_tick_system())

        # Restore snapshot
        snapper2.restore(engine2, snapshot)

        # Verify state after restore matches state after 5 ticks
        need_set2 = world2.get(e1, NeedSet)
        stats2 = world2.get(e1, StatBlock)
        mods2 = world2.get(e1, Modifiers)

        assert NeedHelper.get_value(need_set2, "hunger") == hunger_after_5
        assert effective(stats2, mods2, "strength") == strength_after_5

        # Run M=3 more ticks
        for _ in range(3):
            engine2.step()
            event_log2.emit(tick=engine2.clock.tick_number, type="tick")

        # Verify final state matches
        assert NeedHelper.get_value(need_set2, "hunger") == hunger_after_8
        assert effective(stats2, mods2, "strength") == strength_after_8
        assert len(event_log2) == len(event_log1)

    def test_all_six_primitives_working_together(self):
        """Grid + Actions + Needs + Stats + Events + Containment."""
        from tick_colony import Container, ContainedBy, add_to_container, contents

        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(30, 30)
        event_log = EventLog()

        # Create a container entity (e.g., a chest)
        chest = world.spawn()
        world.attach(chest, Position(x=15, y=15))
        world.attach(chest, Container(items=[], capacity=10))
        grid.place(chest, 15, 15)

        # Create an actor entity
        actor = world.spawn()
        world.attach(actor, Position(x=10, y=10))
        world.attach(actor, Action(name="move_to_chest", total_ticks=5))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "stamina", value=100.0, max_val=100.0, decay_rate=1.0, critical_threshold=30.0)
        world.attach(actor, need_set)

        stats = StatBlock(data={"speed": 5.0})
        mods = Modifiers(entries=[])
        world.attach(actor, stats)
        world.attach(actor, mods)

        grid.place(actor, 10, 10)

        # Create an item
        item = world.spawn()

        # Add systems
        critical_events = []
        def on_critical(world, ctx, eid, need_name):
            critical_events.append((ctx.tick_number, eid, need_name))
            event_log.emit(tick=ctx.tick_number, type="critical", entity_id=eid, need=need_name)

        completed_actions = []
        def on_complete(world, ctx, eid, action):
            completed_actions.append(action.name)
            event_log.emit(tick=ctx.tick_number, type="action_complete", entity_id=eid, action=action.name)
            # Move actor to chest and pick up item
            grid.move(eid, 15, 15)
            add_to_container(world, chest, item)

        engine.add_system(make_action_system(on_complete=on_complete))
        engine.add_system(make_need_decay_system(on_critical=on_critical))
        engine.add_system(make_modifier_tick_system())
        engine.add_system(make_grid_cleanup_system(grid))

        # Run simulation
        for _ in range(10):
            engine.step()

        # Verify all primitives worked
        # 1. Grid: actor moved
        assert grid.position_of(actor) == (15, 15)

        # 2. Actions: action completed
        assert "move_to_chest" in completed_actions

        # 3. Needs: stamina decayed
        assert NeedHelper.get_value(need_set, "stamina") == 90.0

        # 4. Stats: stats still present
        assert world.has(actor, StatBlock)

        # 5. Events: events logged
        assert len(event_log) > 0
        action_events = event_log.query(type="action_complete")
        assert len(action_events) == 1

        # 6. Containment: item in chest
        assert item in contents(world, chest)

    def test_grid_cleanup_with_dead_entities(self):
        """Verify grid cleanup system removes dead entities."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        grid = Grid(20, 20)

        # Create entities
        e1 = world.spawn()
        e2 = world.spawn()
        e3 = world.spawn()

        world.attach(e1, Position(x=5, y=5))
        world.attach(e2, Position(x=10, y=10))
        world.attach(e3, Position(x=15, y=15))

        grid.rebuild(world)

        # Add cleanup system
        engine.add_system(make_grid_cleanup_system(grid))

        # Despawn e2
        world.despawn(e2)

        # Run tick
        engine.step()

        # Verify e2 removed from grid
        assert grid.position_of(e1) == (5, 5)
        assert grid.position_of(e2) is None
        assert grid.position_of(e3) == (15, 15)

    def test_need_critical_threshold_triggers_event(self):
        """Verify need critical callback integration."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        event_log = EventLog()

        e1 = world.spawn()
        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "health", value=25.0, max_val=100.0, decay_rate=10.0, critical_threshold=20.0)
        world.attach(e1, need_set)

        critical_log = []
        def on_critical(world, ctx, eid, need_name):
            critical_log.append((ctx.tick_number, eid, need_name))
            event_log.emit(tick=ctx.tick_number, type="need_critical", entity_id=eid, need=need_name)

        engine.add_system(make_need_decay_system(on_critical=on_critical))

        engine.step()  # Health becomes 15.0, triggers critical

        assert len(critical_log) == 1
        assert critical_log[0] == (1, e1, "health")

        critical_events = event_log.query(type="need_critical")
        assert len(critical_events) == 1
        assert critical_events[0].data["entity_id"] == e1

    def test_modifier_expiration_changes_effective_value(self):
        """Verify modifier tick system integration with effective calculation."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        stats = StatBlock(data={"attack": 10.0})
        mods = Modifiers(entries=[])
        add_modifier(mods, "attack", 5.0, duration=2)
        world.attach(e1, stats)
        world.attach(e1, mods)

        engine.add_system(make_modifier_tick_system())

        # Tick 0: effective = 15
        assert effective(stats, mods, "attack") == 15.0

        # Tick 1: modifier still active
        engine.step()
        assert effective(stats, mods, "attack") == 15.0

        # Tick 2: modifier expires
        engine.step()
        assert effective(stats, mods, "attack") == 10.0  # Back to base

    def test_snapshot_restore_preserves_all_primitives(self):
        """Full integration: snapshot/restore with all 6 primitives."""
        from tick_colony import Container, add_to_container, contents, register_colony_components

        engine1 = Engine(tps=20, seed=42)
        world1 = engine1.world
        register_colony_components(world1)

        grid1 = Grid(20, 20)
        event_log1 = EventLog()
        snapper1 = ColonySnapshot(grid=grid1, event_log=event_log1)

        # Create entities with all components
        container_ent = world1.spawn()
        world1.attach(container_ent, Position(x=5, y=5))
        world1.attach(container_ent, Container(items=[], capacity=5))
        grid1.place(container_ent, 5, 5)

        actor = world1.spawn()
        world1.attach(actor, Position(x=10, y=10))
        world1.attach(actor, Action(name="wait", total_ticks=10))

        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "energy", value=100.0, max_val=100.0, decay_rate=2.0, critical_threshold=20.0)
        world1.attach(actor, need_set)

        stats = StatBlock(data={"strength": 10.0})
        mods = Modifiers(entries=[])
        add_modifier(mods, "strength", 3.0, duration=5)
        world1.attach(actor, stats)
        world1.attach(actor, mods)

        grid1.place(actor, 10, 10)

        item = world1.spawn()
        add_to_container(world1, container_ent, item)

        event_log1.emit(tick=0, type="init", message="test")

        # Snapshot
        snapshot = snapper1.snapshot(engine1)

        # Restore to new engine
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        register_colony_components(world2)

        grid2 = Grid(20, 20)
        event_log2 = EventLog()
        snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2)

        snapper2.restore(engine2, snapshot)

        # Verify all primitives restored
        # 1. Grid
        assert grid2.position_of(container_ent) == (5, 5)
        assert grid2.position_of(actor) == (10, 10)

        # 2. Actions
        action2 = world2.get(actor, Action)
        assert action2.name == "wait"

        # 3. Needs
        need_set2 = world2.get(actor, NeedSet)
        assert NeedHelper.get_value(need_set2, "energy") == 100.0

        # 4. Stats
        stats2 = world2.get(actor, StatBlock)
        mods2 = world2.get(actor, Modifiers)
        assert effective(stats2, mods2, "strength") == 13.0

        # 5. Events
        assert len(event_log2) == 1

        # 6. Containment
        assert item in contents(world2, container_ent)
