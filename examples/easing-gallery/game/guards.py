"""FSM guards and transition table for orb lifecycle."""
from tick_fsm import FSMGuards
from tick_tween import Tween

guards = FSMGuards()
guards.register("has_tween", lambda w, e: w.has(e, Tween))
guards.register("tween_done", lambda w, e: not w.has(e, Tween))

# waiting -> animating (when Tween attached)
# animating -> completed (when Tween detached after finishing)
TRANSITIONS: dict[str, list[list[str]]] = {
    "waiting": [["has_tween", "animating"]],
    "animating": [["tween_done", "completed"]],
}
