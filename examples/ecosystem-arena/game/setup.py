"""Build the complete ecosystem arena game state."""
from __future__ import annotations

import math
import random as _rng_mod
from dataclasses import dataclass, field

from tick import Engine
from tick_ai import (
    AIManager,
    Action,
    BehaviorTree,
    Blackboard,
    Condition,
    Selector,
    Sequence,
    Status,
    UtilityAgent,
    curves,
    make_bt_system,
    make_utility_system,
)
from tick_physics import (
    CircleCollider,
    Collision,
    KinematicBody,
    make_collision_system,
    make_physics_system,
    vec,
)

from game.components import Species, Visual
from game.systems import (
    make_boundary_system,
    make_cleanup_system,
    make_energy_system,
    make_perception_system,
    make_prey_action_system,
    make_reproduction_system,
)

# --- Configuration ---
WIDTH, HEIGHT = 1024, 768
FPS = 60
TPS = 20
RESTITUTION = 0.6

# Predator
PRED_RADIUS = 12
PRED_MASS = 2.0
PRED_START_ENERGY = 150.0
PRED_ENERGY_DRAIN = 0.3
PRED_ENERGY_GAIN = 50.0
PRED_CHASE_FORCE = 300.0
PRED_WANDER_FORCE = 120.0
PRED_MAX_SPEED = 160.0
PERCEPTION_RADIUS = 200.0
INITIAL_PREDATORS = 3

# Prey
PREY_RADIUS = 8
PREY_MASS = 1.0
PREY_FLEE_FORCE = 500.0
PREY_FLOCK_FORCE = 150.0
PREY_GRAZE_BRAKE = 80.0
PREY_MAX_SPEED = 200.0
GRAZE_THRESHOLD = 30
MAX_PREY = 40
INITIAL_PREY = 25


@dataclass
class GameState:
    """Holds engine and shared state for the arena."""

    engine: Engine
    manager: AIManager
    paused: bool = False
    predator_count: int = 0
    prey_count: int = 0


def _spawn_predator(
    engine: Engine, manager: AIManager, x: float, y: float,
) -> int:
    """Spawn a predator entity."""
    eid = engine.world.spawn()
    engine.world.attach(eid, KinematicBody(
        position=(x, y),
        velocity=(0.0, 0.0),
        mass=PRED_MASS,
    ))
    engine.world.attach(eid, CircleCollider(radius=float(PRED_RADIUS)))
    engine.world.attach(eid, Species(kind="predator"))
    engine.world.attach(eid, Visual(color=(220, 50, 50), radius=PRED_RADIUS))
    engine.world.attach(eid, BehaviorTree(tree_name="predator_bt"))
    engine.world.attach(eid, Blackboard(data={
        "energy": PRED_START_ENERGY,
        "nearest_prey_eid": -1,
        "nearest_prey_dist": float("inf"),
        "wander_angle": _rng_mod.uniform(0, 2 * math.pi),
    }))
    return eid


def _spawn_prey(
    engine: Engine, manager: AIManager, x: float, y: float,
) -> int:
    """Spawn a prey entity."""
    eid = engine.world.spawn()
    engine.world.attach(eid, KinematicBody(
        position=(x, y),
        velocity=(0.0, 0.0),
        mass=PREY_MASS,
    ))
    engine.world.attach(eid, CircleCollider(radius=float(PREY_RADIUS)))
    engine.world.attach(eid, Species(kind="prey"))
    engine.world.attach(eid, Visual(color=(50, 200, 80), radius=PREY_RADIUS))
    engine.world.attach(eid, UtilityAgent(selector_name="prey_decide"))
    engine.world.attach(eid, Blackboard(data={
        "nearest_pred_dist": float("inf"),
        "nearest_pred_eid": -1,
        "nearest_ally_dist": float("inf"),
        "graze_timer": 0,
    }))
    return eid


def _register_predator_bt(manager: AIManager, engine: Engine) -> None:
    """Define the predator behavior tree and register actions/conditions."""

    # Condition: is there a prey within perception radius?
    def sees_prey(world: "World", eid: int) -> bool:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard):
            return False
        bb = world.get(eid, Blackboard)
        dist = bb.data.get("nearest_prey_dist", float("inf"))
        return dist < PERCEPTION_RADIUS

    # Action: apply force toward nearest prey
    def chase_prey(world: "World", ctx: "TickContext", eid: int) -> Status:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard) or not world.has(eid, KinematicBody):
            return Status.FAILURE
        bb = world.get(eid, Blackboard)
        body = world.get(eid, KinematicBody)
        prey_eid = bb.data.get("nearest_prey_eid", -1)
        if prey_eid < 0 or not world.has(prey_eid, KinematicBody):
            return Status.FAILURE
        prey_body = world.get(prey_eid, KinematicBody)
        direction = vec.sub(prey_body.position, body.position)
        mag = vec.magnitude(direction)
        if mag > 0.0:
            force = vec.scale(vec.normalize(direction), PRED_CHASE_FORCE)
            body.forces.append(force)
        return Status.SUCCESS

    # Action: wander in a slowly rotating direction
    def wander(world: "World", ctx: "TickContext", eid: int) -> Status:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard) or not world.has(eid, KinematicBody):
            return Status.FAILURE
        bb = world.get(eid, Blackboard)
        body = world.get(eid, KinematicBody)
        angle = bb.data.get("wander_angle", 0.0)
        angle += ctx.random.uniform(-0.3, 0.3)
        bb.data["wander_angle"] = angle
        fx = math.cos(angle) * PRED_WANDER_FORCE
        fy = math.sin(angle) * PRED_WANDER_FORCE
        body.forces.append((fx, fy))
        return Status.SUCCESS

    manager.register_condition("sees_prey", sees_prey)
    manager.register_action("chase_prey", chase_prey)
    manager.register_action("wander", wander)

    nodes = {
        "root": Selector(id="root", children=("chase_seq", "wander")),
        "chase_seq": Sequence(id="chase_seq", children=("sees_prey", "chase_prey")),
        "sees_prey": Condition(id="sees_prey", condition="sees_prey"),
        "chase_prey": Action(id="chase_prey", action="chase_prey"),
        "wander": Action(id="wander", action="wander"),
    }
    manager.define_tree("predator_bt", "root", nodes)


def _register_prey_utility(manager: AIManager) -> None:
    """Define the prey utility selector and considerations."""

    # Consideration: threat_proximity — high when predator is near (quadratic)
    def threat_proximity(world: "World", eid: int) -> float:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard):
            return 0.0
        bb = world.get(eid, Blackboard)
        dist = bb.data.get("nearest_pred_dist", float("inf"))
        if dist >= PERCEPTION_RADIUS:
            return 0.0
        # Normalize: 0 at edge of perception, 1 at distance 0
        t = 1.0 - min(dist / PERCEPTION_RADIUS, 1.0)
        return curves.quadratic(t, exp=2.0)

    # Consideration: safety — inverse of threat (high when predator is far)
    def safety(world: "World", eid: int) -> float:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard):
            return 1.0
        bb = world.get(eid, Blackboard)
        dist = bb.data.get("nearest_pred_dist", float("inf"))
        if dist >= PERCEPTION_RADIUS:
            return 1.0
        t = min(dist / PERCEPTION_RADIUS, 1.0)
        return curves.linear(t)

    # Consideration: hunger — how long since last graze (higher = hungrier)
    def hunger(world: "World", eid: int) -> float:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard):
            return 0.5
        bb = world.get(eid, Blackboard)
        timer = bb.data.get("graze_timer", 0)
        # Normalize: approaches 1.0 as timer approaches threshold
        t = min(timer / max(GRAZE_THRESHOLD, 1), 1.0)
        return curves.inverse(t, steepness=1.0)  # high when timer is LOW (hasn't grazed)

    # Consideration: isolation — high when far from other prey (logistic)
    def isolation(world: "World", eid: int) -> float:  # type: ignore[name-defined]
        if not world.has(eid, Blackboard):
            return 0.5
        bb = world.get(eid, Blackboard)
        dist = bb.data.get("nearest_ally_dist", float("inf"))
        if dist >= PERCEPTION_RADIUS:
            return 1.0
        t = min(dist / PERCEPTION_RADIUS, 1.0)
        return curves.logistic(t, k=8.0, midpoint=0.4)

    manager.register_consideration("threat_proximity", threat_proximity)
    manager.register_consideration("safety", safety)
    manager.register_consideration("hunger", hunger)
    manager.register_consideration("isolation", isolation)

    # Define utility actions with their consideration lists
    manager.define_utility_action("flee", ["threat_proximity"])
    manager.define_utility_action("graze", ["safety", "hunger"])
    manager.define_utility_action("flock", ["isolation"])

    # Define selector
    manager.define_utility_selector("prey_decide", ["flee", "graze", "flock"])


def _make_collision_handler(engine: Engine) -> "Callable":  # type: ignore[name-defined]
    """Build the collision callback for predator-prey catches and bouncing."""

    def on_collision(world: "World", ctx: "TickContext", col: Collision) -> None:  # type: ignore[name-defined]
        eid_a, eid_b = col.entity_a, col.entity_b

        # Both must still exist
        if not world.has(eid_a, Species) or not world.has(eid_b, Species):
            return

        sp_a = world.get(eid_a, Species)
        sp_b = world.get(eid_b, Species)

        # Predator catches prey
        if sp_a.kind == "predator" and sp_b.kind == "prey":
            if world.has(eid_a, Blackboard):
                bb = world.get(eid_a, Blackboard)
                bb.data["energy"] = bb.data.get("energy", 0.0) + PRED_ENERGY_GAIN
            world.despawn(eid_b)
            return
        if sp_b.kind == "predator" and sp_a.kind == "prey":
            if world.has(eid_b, Blackboard):
                bb = world.get(eid_b, Blackboard)
                bb.data["energy"] = bb.data.get("energy", 0.0) + PRED_ENERGY_GAIN
            world.despawn(eid_a)
            return

        # Same species — elastic bounce
        if not world.has(eid_a, KinematicBody) or not world.has(eid_b, KinematicBody):
            return
        body_a = world.get(eid_a, KinematicBody)
        body_b = world.get(eid_b, KinematicBody)

        total_mass = body_a.mass + body_b.mass

        # Separate overlapping bodies
        body_a.position = vec.add(
            body_a.position,
            vec.scale(col.normal, -col.depth * (body_b.mass / total_mass)),
        )
        body_b.position = vec.add(
            body_b.position,
            vec.scale(col.normal, col.depth * (body_a.mass / total_mass)),
        )

        # Impulse-based elastic bounce
        rel_vel = vec.sub(body_a.velocity, body_b.velocity)
        vel_along_normal = vec.dot(rel_vel, col.normal)

        if vel_along_normal > 0:
            return  # already separating

        j = -(1 + RESTITUTION) * vel_along_normal
        j /= (1.0 / body_a.mass) + (1.0 / body_b.mass)

        impulse = vec.scale(col.normal, j)
        body_a.velocity = vec.add(
            body_a.velocity, vec.scale(impulse, 1.0 / body_a.mass)
        )
        body_b.velocity = vec.sub(
            body_b.velocity, vec.scale(impulse, 1.0 / body_b.mass)
        )

    return on_collision


def build_game(seed: int = 42) -> GameState:
    """Wire up the complete ecosystem arena."""
    engine = Engine(tps=TPS, seed=seed)
    w = engine.world

    # Register components
    w.register_component(KinematicBody)
    w.register_component(CircleCollider)
    w.register_component(Species)
    w.register_component(Visual)
    w.register_component(BehaviorTree)
    w.register_component(Blackboard)
    w.register_component(UtilityAgent)

    # AI manager
    manager = AIManager()
    _register_predator_bt(manager, engine)
    _register_prey_utility(manager)

    # Spawn helper closures (capture engine + manager)
    def spawn_predator(x: float, y: float) -> int:
        return _spawn_predator(engine, manager, x, y)

    def spawn_prey(x: float, y: float) -> int:
        return _spawn_prey(engine, manager, x, y)

    # Collision handler
    on_collision = _make_collision_handler(engine)

    # Systems — order matters!
    engine.add_system(make_perception_system(PERCEPTION_RADIUS))           # 1
    engine.add_system(make_bt_system(manager))                             # 2
    engine.add_system(make_utility_system(manager))                        # 3
    engine.add_system(make_prey_action_system(                             # 4
        PREY_FLEE_FORCE, PREY_FLOCK_FORCE, PREY_GRAZE_BRAKE,
    ))
    engine.add_system(make_energy_system(PRED_ENERGY_DRAIN))               # 5
    engine.add_system(make_reproduction_system(                            # 6
        spawn_prey, WIDTH, HEIGHT, MAX_PREY, GRAZE_THRESHOLD,
    ))
    engine.add_system(make_physics_system())                               # 7
    engine.add_system(make_collision_system(on_collision))                  # 8
    engine.add_system(make_boundary_system(WIDTH, HEIGHT, RESTITUTION))    # 9
    engine.add_system(make_cleanup_system(PRED_MAX_SPEED, PREY_MAX_SPEED)) # 10

    # Spawn initial entities
    rng = _rng_mod.Random(seed)
    for _ in range(INITIAL_PREDATORS):
        x = rng.uniform(80, WIDTH - 80)
        y = rng.uniform(80, HEIGHT - 80)
        spawn_predator(x, y)

    for _ in range(INITIAL_PREY):
        x = rng.uniform(80, WIDTH - 80)
        y = rng.uniform(80, HEIGHT - 80)
        spawn_prey(x, y)

    state = GameState(engine=engine, manager=manager)
    return state
