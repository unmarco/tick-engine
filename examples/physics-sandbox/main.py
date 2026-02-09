"""
tick-physics Sandbox
Interactive 2D physics demo showcasing tick-physics: circles, AABBs, collisions, gravity.
"""

import math
import random
import sys
from dataclasses import dataclass

import pygame

from tick import Engine
from tick_physics import (
    AABBCollider,
    CircleCollider,
    Collision,
    KinematicBody,
    make_collision_system,
    make_physics_system,
    vec,
)

# --- Configuration ---
WIDTH, HEIGHT = 1024, 768
FPS = 60
TPS = 60
TITLE = "tick-physics Sandbox"

GRAVITY_STRENGTH = 600.0
WALL_MARGIN = 0.0
RESTITUTION = 0.8
INITIAL_ENTITY_COUNT = 12

MIN_CIRCLE_RADIUS = 12.0
MAX_CIRCLE_RADIUS = 35.0
MIN_AABB_HALF = 10.0
MAX_AABB_HALF = 30.0
MIN_SPEED = 40.0
MAX_SPEED = 200.0
MIN_MASS = 0.5
MAX_MASS = 3.0

# Colors
BG_COLOR = (26, 26, 46)
HUD_COLOR = (200, 200, 220)
OUTLINE_COLOR = (255, 255, 255)
ENTITY_COLORS = [
    (0, 255, 255),    # cyan
    (255, 0, 200),    # magenta
    (0, 255, 100),    # lime
    (255, 160, 0),    # orange
    (255, 215, 0),    # gold
    (255, 100, 100),  # coral
    (180, 100, 255),  # violet
    (100, 200, 255),  # sky blue
    (255, 255, 100),  # yellow
    (100, 255, 200),  # mint
]


# --- Visual component (not part of tick-physics, just for rendering) ---
@dataclass
class Visual:
    color: tuple[int, int, int]
    shape: str  # "circle" or "aabb"


def random_color() -> tuple[int, int, int]:
    return random.choice(ENTITY_COLORS)


def random_velocity() -> tuple[float, float]:
    angle = random.uniform(0, 2 * math.pi)
    speed = random.uniform(MIN_SPEED, MAX_SPEED)
    return (math.cos(angle) * speed, math.sin(angle) * speed)


def spawn_circle(engine: Engine, x: float, y: float) -> int:
    radius = random.uniform(MIN_CIRCLE_RADIUS, MAX_CIRCLE_RADIUS)
    mass = (radius / MIN_CIRCLE_RADIUS) * random.uniform(MIN_MASS, MAX_MASS)
    eid = engine.world.spawn()
    engine.world.attach(eid, KinematicBody(
        position=(x, y),
        velocity=random_velocity(),
        mass=mass,
    ))
    engine.world.attach(eid, CircleCollider(radius=radius))
    engine.world.attach(eid, Visual(color=random_color(), shape="circle"))
    return eid


def spawn_aabb(engine: Engine, x: float, y: float) -> int:
    hw = random.uniform(MIN_AABB_HALF, MAX_AABB_HALF)
    hh = random.uniform(MIN_AABB_HALF, MAX_AABB_HALF)
    mass = (hw * hh / (MIN_AABB_HALF * MIN_AABB_HALF)) * random.uniform(MIN_MASS, MAX_MASS)
    eid = engine.world.spawn()
    engine.world.attach(eid, KinematicBody(
        position=(x, y),
        velocity=random_velocity(),
        mass=mass,
    ))
    engine.world.attach(eid, AABBCollider(half_extents=(hw, hh)))
    engine.world.attach(eid, Visual(color=random_color(), shape="aabb"))
    return eid


def make_boundary_system():
    """Reflect velocity when entities hit screen edges."""

    def boundary_system(world, ctx):
        for eid, (body,) in world.query(KinematicBody):
            x, y = body.position
            vx, vy = body.velocity

            if world.has(eid, CircleCollider):
                r = world.get(eid, CircleCollider).radius
                margin_x = r
                margin_y = r
            elif world.has(eid, AABBCollider):
                he = world.get(eid, AABBCollider).half_extents
                margin_x = he[0]
                margin_y = he[1]
            else:
                continue

            changed = False
            if x - margin_x < WALL_MARGIN:
                x = WALL_MARGIN + margin_x
                vx = abs(vx) * RESTITUTION
                changed = True
            elif x + margin_x > WIDTH - WALL_MARGIN:
                x = WIDTH - WALL_MARGIN - margin_x
                vx = -abs(vx) * RESTITUTION
                changed = True

            if y - margin_y < WALL_MARGIN:
                y = WALL_MARGIN + margin_y
                vy = abs(vy) * RESTITUTION
                changed = True
            elif y + margin_y > HEIGHT - WALL_MARGIN:
                y = HEIGHT - WALL_MARGIN - margin_y
                vy = -abs(vy) * RESTITUTION
                changed = True

            if changed:
                body.position = (x, y)
                body.velocity = (vx, vy)

    return boundary_system


def make_gravity_system(enabled_ref: list[bool]):
    """Apply gravity force when enabled. enabled_ref is a mutable list[bool] for toggling."""

    def gravity_system(world, ctx):
        if not enabled_ref[0]:
            return
        for eid, (body,) in world.query(KinematicBody):
            body.forces.append((0.0, GRAVITY_STRENGTH * body.mass))

    return gravity_system


def on_collision(world, ctx, col: Collision):
    """Elastic collision response with positional correction."""
    body_a = world.get(col.entity_a, KinematicBody)
    body_b = world.get(col.entity_b, KinematicBody)

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


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(TITLE)
    pg_clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 14)

    # --- Engine setup ---
    engine = Engine(tps=TPS)
    engine.world.register_component(KinematicBody)
    engine.world.register_component(CircleCollider)
    engine.world.register_component(AABBCollider)
    engine.world.register_component(Visual)

    gravity_enabled = [False]

    engine.add_system(make_gravity_system(gravity_enabled))
    engine.add_system(make_physics_system())
    engine.add_system(make_collision_system(on_collision))
    engine.add_system(make_boundary_system())

    # --- Spawn initial entities ---
    all_eids: list[int] = []
    for _ in range(INITIAL_ENTITY_COUNT):
        x = random.uniform(80, WIDTH - 80)
        y = random.uniform(80, HEIGHT - 80)
        if random.random() < 0.6:
            all_eids.append(spawn_circle(engine, x, y))
        else:
            all_eids.append(spawn_aabb(engine, x, y))

    # --- State ---
    paused = False
    running = True

    while running:
        pg_clock.tick(FPS)

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_g:
                    gravity_enabled[0] = not gravity_enabled[0]
                elif event.key == pygame.K_c:
                    for eid in all_eids:
                        engine.world.despawn(eid)
                    all_eids.clear()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                if event.button == 1:
                    all_eids.append(spawn_circle(engine, float(mx), float(my)))
                elif event.button == 3:
                    all_eids.append(spawn_aabb(engine, float(mx), float(my)))

        # --- Update ---
        if not paused:
            engine.step()

        # --- Draw ---
        screen.fill(BG_COLOR)

        entity_count = 0
        for eid, (body,) in engine.world.query(KinematicBody):
            if not engine.world.has(eid, Visual):
                continue
            vis = engine.world.get(eid, Visual)
            x, y = body.position
            entity_count += 1

            if vis.shape == "circle" and engine.world.has(eid, CircleCollider):
                radius = int(engine.world.get(eid, CircleCollider).radius)
                pygame.draw.circle(screen, vis.color, (int(x), int(y)), radius)
                pygame.draw.circle(screen, OUTLINE_COLOR, (int(x), int(y)), radius, 1)

            elif vis.shape == "aabb" and engine.world.has(eid, AABBCollider):
                he = engine.world.get(eid, AABBCollider).half_extents
                rect = pygame.Rect(
                    int(x - he[0]), int(y - he[1]),
                    int(he[0] * 2), int(he[1] * 2),
                )
                pygame.draw.rect(screen, vis.color, rect)
                pygame.draw.rect(screen, OUTLINE_COLOR, rect, 1)

        # --- HUD ---
        fps_val = pg_clock.get_fps()
        grav_str = "ON" if gravity_enabled[0] else "OFF"
        pause_str = "  [PAUSED]" if paused else ""

        hud_lines = [
            f"Entities: {entity_count}   FPS: {fps_val:.0f}   Gravity: {grav_str}{pause_str}",
            "LClick=Circle  RClick=AABB  G=Gravity  Space=Pause  C=Clear  Esc=Quit",
        ]
        for i, line in enumerate(hud_lines):
            surf = font.render(line, True, HUD_COLOR)
            screen.blit(surf, (10, 8 + i * 20))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
