# tick-physics

N-dimensional kinematics and collision detection for the tick engine. Semi-implicit Euler integration, circle and AABB colliders, impulse callbacks. Stdlib only.

## Install

```bash
pip install tick-physics
```

```python
from tick_physics import KinematicBody, CircleCollider, AABBCollider, make_physics_system, make_collision_system, vec
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine
from tick_physics import KinematicBody, CircleCollider, Collision, make_physics_system, make_collision_system, vec

def bounce(world, ctx, col: Collision):
    a = world.get(col.entity_a, KinematicBody)
    b = world.get(col.entity_b, KinematicBody)
    # Reflect velocities along collision normal
    rel = vec.dot(vec.sub(a.velocity, b.velocity), col.normal)
    if rel > 0:
        return
    impulse = vec.scale(col.normal, -rel)
    a.velocity = vec.add(a.velocity, impulse)
    b.velocity = vec.sub(b.velocity, impulse)

engine = Engine(tps=60)
engine.add_system(make_physics_system())
engine.add_system(make_collision_system(bounce))

e1 = engine.world.spawn()
engine.world.attach(e1, KinematicBody(position=(0.0, 0.0), velocity=(1.0, 0.0)))
engine.world.attach(e1, CircleCollider(radius=5.0))

e2 = engine.world.spawn()
engine.world.attach(e2, KinematicBody(position=(8.0, 0.0), velocity=(-1.0, 0.0)))
engine.world.attach(e2, CircleCollider(radius=5.0))

engine.run(10)
```

## API Reference

### Components

| Component | Fields | Description |
|-----------|--------|-------------|
| `KinematicBody` | `position`, `velocity`, `mass=1.0`, `forces=[]` | Physics-enabled entity. Position and velocity are `tuple[float, ...]`. Forces are accumulated and cleared each tick. |
| `CircleCollider` | `radius` | Circle/sphere collider. Center derived from `KinematicBody.position`. |
| `AABBCollider` | `half_extents` | Axis-aligned bounding box. Half-extents from center (`KinematicBody.position`). |
| `Collision` | `entity_a`, `entity_b`, `normal`, `depth` | Frozen dataclass passed to collision callbacks. Not a component. |

### Systems

```python
make_physics_system() -> System
```

Semi-implicit Euler integrator. Each tick: accumulates forces into velocity, then integrates velocity into position. Forces are cleared after processing.

```python
make_collision_system(on_collision: Callable[[World, TickContext, Collision], None]) -> System
```

O(n^2) broadphase collision detection between all entities with colliders. Supports circle-circle, AABB-AABB, and circle-AABB pairs. Calls `on_collision` for each detected overlap -- the callback decides the response (bounce, destroy, etc.).

### Vector Math (`vec`)

All functions operate on `tuple[float, ...]` and work in any dimension.

| Function | Description |
|----------|-------------|
| `vec.add(a, b)` | Component-wise addition |
| `vec.sub(a, b)` | Component-wise subtraction |
| `vec.scale(v, s)` | Scalar multiplication |
| `vec.dot(a, b)` | Dot product |
| `vec.magnitude(v)` | Length |
| `vec.normalize(v)` | Unit vector |
| `vec.distance(a, b)` | Euclidean distance |
| `vec.zero(n)` | Zero vector of `n` dimensions |
| `vec.clamp_magnitude(v, max)` | Clamp to maximum length |

## Part of [tick-engine](../../README.md)

MIT License
