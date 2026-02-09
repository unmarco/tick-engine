"""Tests for tick_ability.systems — make_ability_system factory."""
from __future__ import annotations

from tick import Engine, TickContext, World

from tick_ability.guards import AbilityGuards
from tick_ability.manager import AbilityManager
from tick_ability.systems import make_ability_system
from tick_ability.types import AbilityDef


def _setup(
    seed: int = 42,
) -> tuple[Engine, AbilityManager, AbilityGuards, list[tuple[str, str]]]:
    """Create engine, manager, guards, and a log list."""
    engine = Engine(tps=10, seed=seed)
    manager = AbilityManager()
    guards = AbilityGuards()
    log: list[tuple[str, str]] = []
    return engine, manager, guards, log


class TestCallbacks:
    def test_on_start_fires_on_first_tick_after_invoke(self) -> None:
        if make_ability_system is None:
            return  # Skip if not implemented yet

        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=5))

        # System that invokes the ability
        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        # Ability system
        ability_sys = make_ability_system(
            manager, guards, on_start=lambda w, c, n: log.append(("start", n))
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.step()  # tick 1: invoke happens, ability system processes

        assert ("start", "test") in log

    def test_on_end_fires_when_effect_expires(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager, guards, on_end=lambda w, c, n: log.append(("end", n))
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        # tick 1: invoke, active=3
        # tick 2: active=2
        # tick 3: active=1
        # tick 4: active=0 → on_end fires
        engine.run(4)

        assert ("end", "test") in log

    def test_on_tick_fires_each_tick_while_active(self) -> None:
        engine, manager, guards, _ = _setup()
        tick_log: list[tuple[str, int]] = []
        manager.define(AbilityDef(name="test", duration=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_tick=lambda w, c, n, r: tick_log.append((n, r)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(4)

        # on_tick should fire with remaining ticks (after decrement)
        test_ticks = [(n, r) for n, r in tick_log if n == "test"]
        assert len(test_ticks) >= 2  # at least 2 ticks while active

    def test_instantaneous_ability_fires_start_and_end_same_tick(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="instant", duration=0))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("instant", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.step()  # tick 1

        # Both start and end should fire in the same tick
        assert ("start", "instant") in log
        assert ("end", "instant") in log

    def test_instantaneous_ability_no_on_tick(self) -> None:
        engine, manager, guards, _ = _setup()
        tick_log: list[str] = []
        manager.define(AbilityDef(name="instant", duration=0))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("instant", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_tick=lambda w, c, n, r: tick_log.append(n),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(3)

        # on_tick should NOT fire for instantaneous abilities
        assert "instant" not in tick_log

    def test_callbacks_receive_correct_arguments(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(AbilityDef(name="test", duration=3))

        start_args: list[tuple] = []
        end_args: list[tuple] = []
        tick_args: list[tuple] = []

        def on_start(w, c, n):
            start_args.append((w, c, n))

        def on_end(w, c, n):
            end_args.append((w, c, n))

        def on_tick(w, c, n, r):
            tick_args.append((w, c, n, r))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager, guards, on_start=on_start, on_end=on_end, on_tick=on_tick
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(5)

        # Check on_start
        assert len(start_args) == 1
        w, c, n = start_args[0]
        assert w is engine.world
        assert isinstance(c, TickContext)
        assert n == "test"

        # Check on_tick (should have received remaining count)
        assert len(tick_args) > 0
        for w, c, n, r in tick_args:
            assert w is engine.world
            assert isinstance(c, TickContext)
            assert n == "test"
            assert isinstance(r, int)
            assert r > 0  # remaining should be positive

        # Check on_end
        assert len(end_args) == 1
        w, c, n = end_args[0]
        assert w is engine.world
        assert isinstance(c, TickContext)
        assert n == "test"

    def test_no_callbacks_when_none_passed(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(AbilityDef(name="test", duration=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        # Pass None for all callbacks
        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        # Should not raise any errors
        engine.run(5)


class TestCooldown:
    def test_cooldown_begins_after_effect_ends(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(AbilityDef(name="test", duration=3, cooldown=5))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke(active=3) → step1: on_start, step2: decrement(active=2)
        # tick 2: step2: decrement(active=1)
        # tick 3: step2: decrement(active=0) → on_end, cooldown=5, step4: cd→4
        engine.run(3)

        assert manager.cooldown_remaining("test") == 4

    def test_cooldown_decrements_each_tick(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(AbilityDef(name="test", duration=2, cooldown=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke(active=2) → step1: on_start, step2: decrement(active=1)
        # tick 2: step2: decrement(active=0) → on_end, cd=3, step4: cd→2
        engine.run(2)
        assert manager.cooldown_remaining("test") == 2

        engine.step()  # tick 3: cd→1
        assert manager.cooldown_remaining("test") == 1

        engine.step()  # tick 4: cd→0
        assert manager.cooldown_remaining("test") == 0


class TestChargeRegeneration:
    def test_charge_regen_decrements_each_tick(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(
            AbilityDef(name="test", duration=2, max_charges=3, charge_regen=5)
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke(charges=2, regen=5) → step5: regen→4
        engine.step()
        state = manager.state("test")
        assert state is not None
        assert state.regen_remaining == 4

        engine.step()  # tick 2: regen→3
        assert state.regen_remaining == 3

        engine.step()  # tick 3: regen→2
        assert state.regen_remaining == 2

    def test_charge_restored_when_regen_timer_fires(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(
            AbilityDef(name="test", duration=1, max_charges=3, charge_regen=3)
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke, charges=2, regen=3
        # tick 2: regen=2
        # tick 3: regen=1
        # tick 4: regen=0 → charge restored, charges=3
        engine.run(4)

        assert manager.charges("test") == 3

    def test_regen_stops_when_charges_reach_max(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(
            AbilityDef(name="test", duration=1, max_charges=2, charge_regen=3)
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke, charges=1, regen=3
        # tick 2: regen=2
        # tick 3: regen=1
        # tick 4: regen=0 → charge restored, charges=2 (max), regen stops
        engine.run(4)

        state = manager.state("test")
        assert state is not None
        assert state.charges == 2
        assert state.regen_remaining == 0  # stopped

        # One more tick to verify regen doesn't restart
        engine.step()
        assert state.regen_remaining == 0

    def test_regen_restarts_if_charges_still_below_max(self) -> None:
        engine, manager, guards, _ = _setup()
        manager.define(
            AbilityDef(name="test", duration=1, max_charges=3, charge_regen=3)
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)
            if ctx.tick_number == 2:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke(charges=2, regen=3) → step5: regen→2
        # tick 2: invoke(charges=1, regen still running) → step5: regen→1
        # tick 3: step5: regen→0 → charge restored(charges=2), still<3 → regen=3
        # tick 4: step5: regen→2
        engine.run(4)

        state = manager.state("test")
        assert state is not None
        assert state.charges == 2
        assert state.regen_remaining == 2  # restarted and ticked once


class TestMultipleAbilities:
    def test_multiple_abilities_processed_in_definition_order(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="first", duration=5))
        manager.define(AbilityDef(name="second", duration=5))
        manager.define(AbilityDef(name="third", duration=5))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("first", w, ctx, guards=guards)
                manager.invoke("second", w, ctx, guards=guards)
                manager.invoke("third", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager, guards, on_start=lambda w, c, n: log.append(("start", n))
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.step()

        starts = [n for action, n in log if action == "start"]
        assert starts == ["first", "second", "third"]


class TestRestore:
    def test_no_on_start_refire_after_restore_mid_effect(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=10))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager, guards, on_start=lambda w, c, n: log.append(("start", n))
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # Run for a few ticks
        engine.run(3)
        assert ("start", "test") in log
        start_count = sum(1 for action, _ in log if action == "start")
        assert start_count == 1

        # Snapshot and restore
        snapshot = manager.snapshot()
        manager2 = AbilityManager()
        manager2.define(AbilityDef(name="test", duration=10))
        manager2.restore(snapshot)

        # Create new engine with restored manager
        engine2 = Engine(tps=10, seed=42)
        log2: list[tuple[str, str]] = []
        ability_sys2 = make_ability_system(
            manager2, guards, on_start=lambda w, c, n: log2.append(("start", n))
        )
        engine2.add_system(ability_sys2)

        # Run a few more ticks
        engine2.run(3)

        # on_start should NOT fire again
        assert ("start", "test") not in log2


class TestFullLifecycle:
    def test_full_lifecycle_invoke_to_cooldown_to_available(self) -> None:
        engine, manager, guards, log = _setup()
        # max_charges=2 so one remains after first invoke
        manager.define(AbilityDef(name="test", duration=3, cooldown=2, max_charges=2))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke(active=3, charges=1) → on_start, decrement(active=2)
        engine.step()
        assert manager.is_active("test")
        assert ("start", "test") in log

        # tick 2: decrement(active=1)
        engine.step()
        assert manager.is_active("test")

        # tick 3: decrement(active=0) → on_end, cooldown=2, step4: cd→1
        engine.step()
        assert not manager.is_active("test")
        assert manager.cooldown_remaining("test") == 1
        assert ("end", "test") in log

        # tick 4: cd→0
        engine.step()
        assert manager.cooldown_remaining("test") == 0
        assert manager.is_available("test", engine.world, guards=guards)

    def test_ability_invoked_during_callback_deferred_to_next_tick(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="first", duration=2))
        manager.define(AbilityDef(name="second", duration=2))

        def on_end_callback(w, c, n):
            log.append(("end", n))
            if n == "first":
                # Invoke second ability during first's on_end
                manager.invoke("second", w, c, guards=guards)

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("first", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=on_end_callback,
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # tick 1: invoke first, start first
        # tick 2: active=1
        # tick 3: active=0 → end first, invoke second (deferred)
        # tick 4: start second
        engine.run(4)

        # Verify order: first starts, first ends, second starts
        start_events = [(n,) for action, n in log if action == "start"]
        assert ("first",) in start_events
        assert ("second",) in start_events

        # second should start AFTER first ends
        first_end_idx = next(i for i, (a, n) in enumerate(log) if a == "end" and n == "first")
        second_start_idx = next(
            i for i, (a, n) in enumerate(log) if a == "start" and n == "second"
        )
        # Note: second_start happens in the next system tick after invoke
        assert second_start_idx > first_end_idx

    def test_system_with_no_guards_parameter(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                # Pass guards directly to invoke
                manager.invoke("test", w, ctx, guards=guards)

        # Create system without guards parameter
        ability_sys = make_ability_system(
            manager, None, on_start=lambda w, c, n: log.append(("start", n))
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.step()

        assert ("start", "test") in log
