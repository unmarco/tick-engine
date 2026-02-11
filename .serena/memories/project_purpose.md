# tick-engine: Project Purpose

## What is tick-engine?
A minimal, general-purpose tick engine ecosystem in Python. This is the skeleton of a game loop stripped of everything game-specific — entities, components, systems, a fixed-timestep clock, and nothing else.

## Educational Goal
Built as an educational project to understand the tick pattern from first principles. The engine demonstrates:
- Entity-Component-System (ECS) architecture
- Fixed timestep game loops
- Deterministic simulation
- Component-based design

## Philosophy
- **Minimal**: No external dependencies (stdlib only)
- **Mechanisms, not decisions**: Provides tools, not game logic
- **Composable**: Mix and match packages as needed
- **Testable**: Everything is tested (1644 tests)

## What it's NOT
- NOT a game engine (no rendering, input, audio)
- NOT opinionated about game design
- NOT a framework (it's a library)

## Use Cases
- Learning ECS architecture
- Building roguelikes and colony sims
- Prototyping simulation games
- Understanding tick-based systems
- Educational projects
