"""System factory for tween interpolation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from tick_tween.components import Tween
from tick_tween.easing import EASINGS

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


def make_tween_system(
    on_complete: Callable[[World, TickContext, EntityId, Tween], None] | None = None,
) -> Callable[[World, TickContext], None]:
    def tween_system(world: World, ctx: TickContext) -> None:
        for eid, (tween,) in list(world.query(Tween)):
            tween.elapsed += 1

            t = min(tween.elapsed / tween.duration, 1.0)

            easing_fn = EASINGS.get(tween.easing)
            if easing_fn is None:
                continue

            eased_t = easing_fn(t)
            value = tween.start_val + (tween.end_val - tween.start_val) * eased_t

            target_type = world._registry.get(tween.target)
            if target_type is None:
                continue

            if not world.has(eid, target_type):
                continue

            target_comp: Any = world.get(eid, target_type)

            if not hasattr(target_comp, tween.field):
                continue

            setattr(target_comp, tween.field, value)

            if tween.elapsed >= tween.duration:
                setattr(target_comp, tween.field, tween.end_val)
                world.detach(eid, Tween)
                if on_complete is not None:
                    on_complete(world, ctx, eid, tween)

    return tween_system
