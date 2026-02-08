"""Tests for tick_colony.containment module - entity hierarchy."""

import pytest
from tick_colony import Container, ContainedBy, add_to_container, remove_from_container, transfer, contents, parent_of
from tick import Engine


class TestContainer:
    def test_container_creation(self):
        container = Container(items=[], capacity=10)
        assert container.items == []
        assert container.capacity == 10

    def test_container_unlimited_capacity(self):
        container = Container(items=[], capacity=-1)
        assert container.capacity == -1

    def test_container_with_items(self):
        container = Container(items=[1, 2, 3], capacity=5)
        assert container.items == [1, 2, 3]


class TestContainedBy:
    def test_containedby_creation(self):
        contained = ContainedBy(parent=42)
        assert contained.parent == 42


class TestAddToContainer:
    def test_add_to_container_success(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child = world.spawn()

        world.attach(parent, Container(items=[], capacity=10))

        result = add_to_container(world, parent, child)

        assert result is True
        container = world.get(parent, Container)
        assert child in container.items
        contained_by = world.get(child, ContainedBy)
        assert contained_by.parent == parent

    def test_add_to_container_at_capacity(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child1 = world.spawn()
        child2 = world.spawn()

        world.attach(parent, Container(items=[], capacity=1))

        result1 = add_to_container(world, parent, child1)
        assert result1 is True

        result2 = add_to_container(world, parent, child2)
        assert result2 is False

        container = world.get(parent, Container)
        assert child1 in container.items
        assert child2 not in container.items
        assert not world.has(child2, ContainedBy)

    def test_add_to_container_unlimited_capacity(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        world.attach(parent, Container(items=[], capacity=-1))

        children = [world.spawn() for _ in range(100)]

        for child in children:
            result = add_to_container(world, parent, child)
            assert result is True

        container = world.get(parent, Container)
        assert len(container.items) == 100

    def test_add_to_container_bidirectional_consistency(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child = world.spawn()

        world.attach(parent, Container(items=[], capacity=5))

        add_to_container(world, parent, child)

        # Check parent -> child link
        container = world.get(parent, Container)
        assert child in container.items

        # Check child -> parent link
        contained_by = world.get(child, ContainedBy)
        assert contained_by.parent == parent


class TestRemoveFromContainer:
    def test_remove_from_container(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child = world.spawn()

        world.attach(parent, Container(items=[], capacity=5))
        add_to_container(world, parent, child)

        assert world.has(child, ContainedBy)

        remove_from_container(world, parent, child)

        container = world.get(parent, Container)
        assert child not in container.items
        assert not world.has(child, ContainedBy)

    def test_remove_from_container_not_present(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child = world.spawn()

        world.attach(parent, Container(items=[], capacity=5))

        # Should not raise
        remove_from_container(world, parent, child)

    def test_remove_from_container_multiple_items(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        children = [world.spawn() for _ in range(3)]

        world.attach(parent, Container(items=[], capacity=10))

        for child in children:
            add_to_container(world, parent, child)

        remove_from_container(world, parent, children[1])

        container = world.get(parent, Container)
        assert children[0] in container.items
        assert children[1] not in container.items
        assert children[2] in container.items


class TestTransfer:
    def test_transfer_between_containers(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        old_parent = world.spawn()
        new_parent = world.spawn()
        child = world.spawn()

        world.attach(old_parent, Container(items=[], capacity=10))
        world.attach(new_parent, Container(items=[], capacity=10))

        add_to_container(world, old_parent, child)

        result = transfer(world, child, old_parent, new_parent)

        assert result is True

        old_container = world.get(old_parent, Container)
        new_container = world.get(new_parent, Container)
        contained_by = world.get(child, ContainedBy)

        assert child not in old_container.items
        assert child in new_container.items
        assert contained_by.parent == new_parent

    def test_transfer_new_container_at_capacity(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        old_parent = world.spawn()
        new_parent = world.spawn()
        child = world.spawn()
        blocker = world.spawn()

        world.attach(old_parent, Container(items=[], capacity=10))
        world.attach(new_parent, Container(items=[], capacity=1))

        add_to_container(world, old_parent, child)
        add_to_container(world, new_parent, blocker)

        result = transfer(world, child, old_parent, new_parent)

        assert result is False

        old_container = world.get(old_parent, Container)
        new_container = world.get(new_parent, Container)
        contained_by = world.get(child, ContainedBy)

        # Child should remain in old container
        assert child in old_container.items
        assert child not in new_container.items
        assert contained_by.parent == old_parent

    def test_transfer_unlimited_capacity(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        old_parent = world.spawn()
        new_parent = world.spawn()

        world.attach(old_parent, Container(items=[], capacity=5))
        world.attach(new_parent, Container(items=[], capacity=-1))

        children = [world.spawn() for _ in range(10)]

        for child in children:
            add_to_container(world, old_parent, child)

        # Transfer all children to unlimited container
        for i, child in enumerate(children[:5]):  # Only first 5 fit in old_parent
            result = transfer(world, child, old_parent, new_parent)
            assert result is True


class TestContents:
    def test_contents_returns_items_list(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        children = [world.spawn() for _ in range(3)]

        world.attach(parent, Container(items=[], capacity=10))

        for child in children:
            add_to_container(world, parent, child)

        items = contents(world, parent)
        assert set(items) == set(children)

    def test_contents_empty_container(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        world.attach(parent, Container(items=[], capacity=10))

        items = contents(world, parent)
        assert items == []

    def test_contents_no_container_component(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()

        with pytest.raises(KeyError):
            contents(world, parent)


class TestParentOf:
    def test_parent_of_returns_parent_entity(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        parent = world.spawn()
        child = world.spawn()

        world.attach(parent, Container(items=[], capacity=10))
        add_to_container(world, parent, child)

        parent_id = parent_of(world, child)
        assert parent_id == parent

    def test_parent_of_returns_none_if_not_contained(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        child = world.spawn()

        parent_id = parent_of(world, child)
        assert parent_id is None


class TestBidirectionalConsistency:
    def test_consistency_after_multiple_operations(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        container1 = world.spawn()
        container2 = world.spawn()
        item1 = world.spawn()
        item2 = world.spawn()

        world.attach(container1, Container(items=[], capacity=10))
        world.attach(container2, Container(items=[], capacity=10))

        # Add items to container1
        add_to_container(world, container1, item1)
        add_to_container(world, container1, item2)

        # Verify consistency
        assert set(contents(world, container1)) == {item1, item2}
        assert parent_of(world, item1) == container1
        assert parent_of(world, item2) == container1

        # Transfer item1 to container2
        transfer(world, item1, container1, container2)

        # Verify consistency
        assert contents(world, container1) == [item2]
        assert contents(world, container2) == [item1]
        assert parent_of(world, item1) == container2
        assert parent_of(world, item2) == container1

        # Remove item2
        remove_from_container(world, container1, item2)

        # Verify consistency
        assert contents(world, container1) == []
        assert parent_of(world, item2) is None
