# Ecosystem Arena

Predator-prey simulation demonstrating **tick-ai** (behavior trees, utility AI, response curves) and **tick-physics** (kinematics, collision detection, vector math) working together.

## Packages Exercised

- `tick` — Engine, World, TickContext
- `tick-ai` — AIManager, BehaviorTree, Blackboard, UtilityAgent, Status, nodes, curves, system factories
- `tick-physics` — KinematicBody, CircleCollider, Collision, vec, system factories

## How It Works

**Predators** (red circles) use a **behavior tree** that prioritizes chasing visible prey, falling back to wandering. They lose energy each tick and gain energy by catching prey. When energy reaches zero, they die.

**Prey** (green circles) use **utility AI** to choose between three actions each tick:
- **Flee** — activated by a quadratic threat-proximity curve when a predator is nearby
- **Graze** — activated when safe and hungry (multiplicative safety * hunger considerations)
- **Flock** — activated by a logistic isolation curve when far from other prey

Grazing prey accumulate a timer that triggers reproduction when it reaches the threshold, keeping the population balanced.

All movement is force-based through `tick-physics`. Collisions between predators and prey trigger a catch (prey despawned, predator gains energy). Same-species collisions use elastic impulse-based bouncing.

## Controls

| Key | Action |
|-----|--------|
| Space | Pause / Resume |
| P | Spawn predator at cursor |
| E | Spawn prey at cursor |
| C | Clear all entities |
| R | Reset simulation |
| Esc | Quit |

## Running

```bash
cd examples/ecosystem-arena
uv sync
uv run python main.py
```
