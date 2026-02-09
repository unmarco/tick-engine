"""Integration tests for tick-ability — full engine scenarios."""
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


class TestFullEngineIntegration:
    def test_define_invoke_run_verify_callbacks_and_state(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=5, cooldown=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
            on_tick=lambda w, c, n, r: log.append(("tick", f"{n}:{r}")),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # Run full lifecycle
        engine.run(10)

        # Verify callbacks fired
        assert ("start", "test") in log
        assert ("end", "test") in log
        tick_events = [item for item in log if item[0] == "tick"]
        assert len(tick_events) > 0

        # Verify state at end
        assert not manager.is_active("test")
        assert manager.cooldown_remaining("test") == 0  # cooldown should have expired

    def test_multiple_abilities_with_interleaved_invocations(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="fast", duration=2, cooldown=1))
        manager.define(AbilityDef(name="slow", duration=5, cooldown=2))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("fast", w, ctx, guards=guards)
            if ctx.tick_number == 3:
                manager.invoke("slow", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(10)

        # Both should have started and ended
        start_events = [n for action, n in log if action == "start"]
        assert "fast" in start_events
        assert "slow" in start_events

        end_events = [n for action, n in log if action == "end"]
        assert "fast" in end_events
        assert "slow" in end_events

    def test_snapshot_restore_mid_effect_verify_continuity(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=10, cooldown=5))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        tick_log: list[tuple[str, int]] = []

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
            on_tick=lambda w, c, n, r: tick_log.append((n, r)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # Run for 3 ticks, then snapshot
        engine.run(3)
        assert ("start", "test") in log
        snapshot = manager.snapshot()

        # Create new manager and restore
        manager2 = AbilityManager()
        manager2.define(AbilityDef(name="test", duration=10, cooldown=5))
        manager2.restore(snapshot)

        # Create new engine
        engine2 = Engine(tps=10, seed=42)
        log2: list[tuple[str, str]] = []
        tick_log2: list[tuple[str, int]] = []

        ability_sys2 = make_ability_system(
            manager2,
            guards,
            on_start=lambda w, c, n: log2.append(("start", n)),
            on_end=lambda w, c, n: log2.append(("end", n)),
            on_tick=lambda w, c, n, r: tick_log2.append((n, r)),
        )

        engine2.add_system(ability_sys2)

        # Continue running
        engine2.run(10)

        # on_start should NOT re-fire
        assert ("start", "test") not in log2

        # on_tick should continue
        assert len(tick_log2) > 0

        # on_end should eventually fire
        assert ("end", "test") in log2

    def test_deterministic_behavior_with_seeded_rng(self) -> None:
        results: list[list[bool]] = []

        for _ in range(2):
            engine, manager, guards, _ = _setup(seed=99)
            manager.define(AbilityDef(name="random", duration=(3, 10)))

            def invoke_system(w: World, ctx: TickContext) -> None:
                if ctx.tick_number == 1:
                    manager.invoke("random", w, ctx, guards=guards)

            ability_sys = make_ability_system(manager, guards)

            engine.add_system(invoke_system)
            engine.add_system(ability_sys)

            run_results: list[bool] = []
            for _ in range(15):
                engine.step()
                run_results.append(manager.is_active("random"))

            results.append(run_results)

        # Same seed should produce identical activation patterns
        assert results[0] == results[1]

    def test_guard_integration_with_external_state(self) -> None:
        engine, manager, guards, log = _setup()

        # External state (closure)
        mana = {"current": 50}

        def has_mana(w, m):
            return mana["current"] >= 30

        guards.register("has_mana", has_mana)
        manager.define(AbilityDef(name="spell", duration=5, conditions=["has_mana"]))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                # Should succeed (50 >= 30)
                result = manager.invoke("spell", w, ctx, guards=guards)
                log.append(("invoke1", str(result)))

            if ctx.tick_number == 10:
                # Reduce mana
                mana["current"] = 20
                # Should fail (20 < 30)
                result = manager.invoke("spell", w, ctx, guards=guards)
                log.append(("invoke2", str(result)))

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(15)

        assert ("invoke1", "True") in log
        assert ("invoke2", "False") in log

    def test_ability_with_multiple_charges_use_and_regen(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(
            AbilityDef(name="multi", duration=2, max_charges=3, charge_regen=4)
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("multi", w, ctx, guards=guards)
                log.append(("invoke1", str(manager.charges("multi"))))
            if ctx.tick_number == 5:
                manager.invoke("multi", w, ctx, guards=guards)
                log.append(("invoke2", str(manager.charges("multi"))))

        ability_sys = make_ability_system(manager, guards)

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(10)

        # Verify charges were consumed and regenerated
        assert ("invoke1", "2") in log  # after first use
        # After several ticks, one charge should have regenerated
        # So we should have at least 1 charge left after second use
        assert ("invoke2", "1") in log or ("invoke2", "2") in log

    def test_instantaneous_ability_full_engine(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="instant", duration=0, cooldown=3))

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
        engine.run(5)

        # Start and end should both fire
        assert ("start", "instant") in log
        assert ("end", "instant") in log

        # Should have cooldown after
        # tick 1: invoke, tick 2: start+end+cooldown=3, tick 3: cd=2, tick 4: cd=1, tick 5: cd=0
        engine.step()  # one more tick
        assert manager.cooldown_remaining("instant") == 0

    def test_invoke_from_on_end_callback_chain_abilities(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="first", duration=2))
        manager.define(AbilityDef(name="second", duration=3))

        def on_end_callback(w, c, n):
            log.append(("end", n))
            if n == "first":
                # Chain to second
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
        engine.run(10)

        # Both should have started
        start_events = [n for action, n in log if action == "start"]
        assert "first" in start_events
        assert "second" in start_events

        # Verify order: first starts, first ends, second starts
        first_end_idx = next(i for i, (a, n) in enumerate(log) if a == "end" and n == "first")
        second_start_idx = next(
            i for i, (a, n) in enumerate(log) if a == "start" and n == "second"
        )
        assert second_start_idx > first_end_idx

    def test_ability_with_all_features(self) -> None:
        engine, manager, guards, log = _setup()

        # Guard with external state
        allowed = {"value": True}

        guards.register("is_allowed", lambda w, m: allowed["value"])

        manager.define(
            AbilityDef(
                name="complex",
                duration=(3, 5),  # random
                cooldown=4,
                max_charges=2,
                charge_regen=6,
                conditions=["is_allowed"],
            )
        )

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                result = manager.invoke("complex", w, ctx, guards=guards)
                log.append(("invoke1", str(result)))

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)
        engine.run(20)

        # Verify it worked
        assert ("invoke1", "True") in log
        assert ("start", "complex") in log
        assert ("end", "complex") in log

        # Verify state evolved correctly
        state = manager.state("complex")
        assert state is not None
        # Should have consumed one charge and potentially regenerated
        assert state.charges >= 0

    def test_redefine_ability_preserves_runtime_state(self) -> None:
        engine, manager, guards, log = _setup()
        manager.define(AbilityDef(name="test", duration=5, max_charges=3))

        def invoke_system(w: World, ctx: TickContext) -> None:
            if ctx.tick_number == 1:
                manager.invoke("test", w, ctx, guards=guards)

        ability_sys = make_ability_system(
            manager,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
        )

        engine.add_system(invoke_system)
        engine.add_system(ability_sys)

        # Run for 2 ticks
        engine.run(2)

        # Re-define with different parameters
        manager.define(AbilityDef(name="test", duration=10, max_charges=5))

        # Continue running
        engine.run(5)

        # Should still work, state preserved
        assert ("start", "test") in log
        state = manager.state("test")
        assert state is not None
        # Charges were consumed during first invoke (should still be 2)
        assert state.charges == 2
