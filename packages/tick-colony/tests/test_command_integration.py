"""Tests for tick-command integration in tick-colony."""

from dataclasses import dataclass

from tick import Engine
from tick_colony import (
    CommandQueue,
    make_command_system,
    expand_footprint,
    resolve_footprint,
    NeedSet,
    NeedHelper,
    register_colony_components,
)


@dataclass(frozen=True)
class FeedCmd:
    target: int
    amount: float


@dataclass(frozen=True)
class HealCmd:
    target: int
    amount: float


class TestCommandIntegration:
    """Test tick-command re-exports and colony integration."""

    def test_command_queue_importable(self):
        """CommandQueue importable from tick_colony."""
        queue = CommandQueue()
        assert queue.pending() == 0

    def test_make_command_system_importable(self):
        """make_command_system importable from tick_colony."""
        queue = CommandQueue()
        sys = make_command_system(queue)
        assert callable(sys)

    def test_command_queue_in_colony_engine(self):
        """CommandQueue + make_command_system in engine -- enqueue, step, handler called."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        queue = CommandQueue()
        handled = []

        def handle_feed(cmd: FeedCmd, world, ctx) -> bool:
            handled.append(cmd)
            return True

        queue.handle(FeedCmd, handle_feed)
        engine.add_system(make_command_system(queue))

        # Enqueue a command
        queue.enqueue(FeedCmd(target=1, amount=10.0))
        assert queue.pending() == 1

        # Step engine -- command should be processed
        engine.step()
        assert len(handled) == 1
        assert handled[0].target == 1
        assert handled[0].amount == 10.0
        assert queue.pending() == 0

    def test_handler_modifies_need_set(self):
        """Handler modifies NeedSet on entity via frozen dataclass command."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        register_colony_components(world)

        # Create entity with NeedSet
        eid = world.spawn()
        need_set = NeedSet(data={})
        NeedHelper.add(
            need_set, "hunger", value=50.0, max_val=100.0,
            decay_rate=0.0, critical_threshold=20.0,
        )
        world.attach(eid, need_set)

        queue = CommandQueue()

        def handle_feed(cmd: FeedCmd, world, ctx) -> bool:
            ns = world.get(cmd.target, NeedSet)
            current = NeedHelper.get_value(ns, "hunger")
            NeedHelper.set_value(ns, "hunger", min(current + cmd.amount, 100.0))
            return True

        queue.handle(FeedCmd, handle_feed)
        engine.add_system(make_command_system(queue))

        # Enqueue a feed command
        queue.enqueue(FeedCmd(target=eid, amount=25.0))

        engine.step()

        # Verify need was modified
        assert NeedHelper.get_value(need_set, "hunger") == 75.0

    def test_multiple_commands_fifo(self):
        """Multiple commands processed FIFO in one tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        queue = CommandQueue()
        order = []

        def handle_feed(cmd: FeedCmd, world, ctx) -> bool:
            order.append(("feed", cmd.target))
            return True

        def handle_heal(cmd: HealCmd, world, ctx) -> bool:
            order.append(("heal", cmd.target))
            return True

        queue.handle(FeedCmd, handle_feed)
        queue.handle(HealCmd, handle_heal)
        engine.add_system(make_command_system(queue))

        # Enqueue in specific order
        queue.enqueue(FeedCmd(target=1, amount=10.0))
        queue.enqueue(HealCmd(target=2, amount=5.0))
        queue.enqueue(FeedCmd(target=3, amount=15.0))

        engine.step()

        # Verify FIFO order
        assert order == [("feed", 1), ("heal", 2), ("feed", 3)]

    def test_on_reject_callback(self):
        """on_reject callback fires when handler returns False."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        queue = CommandQueue()
        rejected = []

        def handle_feed(cmd: FeedCmd, world, ctx) -> bool:
            return False  # Always reject

        def on_reject(cmd):
            rejected.append(cmd)

        queue.handle(FeedCmd, handle_feed)
        engine.add_system(make_command_system(queue, on_reject=on_reject))

        queue.enqueue(FeedCmd(target=1, amount=10.0))
        engine.step()

        assert len(rejected) == 1
        assert rejected[0].target == 1

    def test_queue_drains_each_tick(self):
        """Queue drains each tick -- empty on second tick after enqueue."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        queue = CommandQueue()
        call_count = [0]

        def handle_feed(cmd: FeedCmd, world, ctx) -> bool:
            call_count[0] += 1
            return True

        queue.handle(FeedCmd, handle_feed)
        engine.add_system(make_command_system(queue))

        queue.enqueue(FeedCmd(target=1, amount=10.0))

        # First tick -- processes the command
        engine.step()
        assert call_count[0] == 1
        assert queue.pending() == 0

        # Second tick -- nothing to process
        engine.step()
        assert call_count[0] == 1  # Not called again

    def test_expand_footprint(self):
        """expand_footprint returns correct coords for 2x2 at (5, 3)."""
        coords = expand_footprint((5, 3), (2, 2))
        assert len(coords) == 4
        assert (5, 3) in coords
        assert (5, 4) in coords
        assert (6, 3) in coords
        assert (6, 4) in coords

    def test_resolve_footprint_dimensions(self):
        """resolve_footprint with tuple dimensions delegates to expand_footprint."""
        coords = resolve_footprint((5, 3), (2, 2))
        assert len(coords) == 4
        assert (5, 3) in coords
        assert (6, 4) in coords

    def test_resolve_footprint_offsets(self):
        """resolve_footprint with list of offsets translates relative to origin."""
        offsets = [(0, 0), (1, 0), (0, 1), (1, 1)]
        coords = resolve_footprint((5, 3), offsets)
        assert len(coords) == 4
        assert (5, 3) in coords
        assert (6, 3) in coords
        assert (5, 4) in coords
        assert (6, 4) in coords
