# "Don't Let the Speed Override Sane Engineering": How One Developer Built a 15-Package Game Engine in 48 Hours with Claude

*A tick-by-tick account of building a modular Python simulation engine from first principles -- and what it reveals about AI-assisted software engineering when you refuse to cut corners.*

---

It starts, as many good engineering stories do, with a question nobody asked: *What actually happens inside a game loop?*

Not the Unity version. Not the Unreal version. The stripped-down, nothing-but-the-machinery version. The skeleton of `Update()` with every game-specific bone removed.

The answer, it turns out, is [tick-engine](https://github.com/unmarco/tick-engine): a 15-package Python monorepo containing a minimal ECS (Entity-Component-System) tick engine, 13 independent extension modules, and a colony-builder framework -- all written in 48 hours, with zero external dependencies, strict type checking, and 1,399 passing tests.

The developer behind it -- who goes by unmarco -- built it in collaboration with Claude, Anthropic's AI assistant. But the word "collaboration" undersells what happened here. This wasn't autocomplete on steroids. It was a disciplined engineering process that happened to move at an unusual speed.

## First Principles, Not Frameworks

"The initial motivation is learning," unmarco says when I ask why anyone would build *another* game engine in Python. "I wanted to learn about game engines, event loops in gaming, ticks -- all of that. So I wanted a first-principles approach to the subject matter."

That first-principles impulse produced `tick`, the core package: a 512-line engine that does exactly three things well. It keeps time (a fixed-timestep clock). It maintains state (an ECS world where entities are integer IDs and components are plain dataclasses). And it calls user-defined systems in order, once per tick, forever.

```python
engine = Engine(tps=20)
engine.add_system(movement_system)
engine.add_system(collision_system)
engine.run(n=100)  # 100 deterministic ticks
```

That's it. No rendering. No input handling. No physics. Those are someone else's problem -- or, as it turned out, the problem of 13 extension packages that would follow in rapid succession.

## The Procedure

The git history tells the story in commit timestamps: 77 commits between February 8 and February 10, 2026. The first commit initializes a `uv` workspace monorepo. The last adds an AI ecosystem demo with behavior trees controlling predators and prey. In between: eleven release milestones, each following git-flow branching with conventional commits.

But the speed is misleading if you don't understand the process behind it. unmarco describes a procedure refined across multiple AI-assisted projects:

1. **Evaluate** the current workspace state
2. **Brainstorm** future directions based on what exists and what's missing
3. **Write a spec**
4. **Refine** the spec conversationally
5. **Develop, test, iterate**
6. **Ship** a new release

"The specs were very detailed," unmarco explains. "The idea is that once the spec is settled, we shouldn't go back and touch it. Just build and test it. My input at the start is somewhat loose -- 'I need X to do Y' -- and we refine the details conversationally."

Those specs are still in the repository. The extensions specification alone runs to 900 lines -- covering six packages with method signatures, serialization constraints, design rationale, explicit out-of-scope declarations, colony migration guides, and 40 numbered verification criteria. This is not a prompt. It's a technical specification document that could be handed to any engineer, human or AI.

## The Architecture of Composability

The design philosophy is aggressive modularity. At the bottom: `tick`, the core ECS engine. In the middle: 13 extension packages, each solving exactly one problem -- spatial indexing, finite state machines, timers, tweening, physics, AI, event scheduling, command queues, abilities, resources, blueprints, signal buses, and tile maps. At the top: `tick-colony`, a colony-builder framework that re-exports everything and adds domain-specific primitives like needs, stats, and containment.

```
tick (ECS Core)
  ├── tick-schedule     Countdown timers, periodic triggers
  ├── tick-signal       Pub/sub event bus with deferred flush
  ├── tick-fsm          Hierarchical finite state machines
  ├── tick-tween        Value interpolation with easing
  ├── tick-blueprint    Entity template registry
  ├── tick-spatial      Grid2D, Grid3D, HexGrid, A* pathfinding
  ├── tick-event        World-level event scheduling
  ├── tick-atlas        Cell/tile property maps
  ├── tick-ability      Player-triggered abilities
  ├── tick-command      Typed command queue
  ├── tick-resource     Typed resource inventories
  ├── tick-physics      N-dimensional kinematics + collision
  └── tick-ai           Behavior trees + utility AI + blackboard
```

Every extension depends only on `tick>=0.2.1`. No extension depends on any other extension. You can install `tick-spatial` without pulling in `tick-fsm`. You can use behavior trees without physics. The dependency graph is flat by design.

"The layering and segregation is a core principle," unmarco says. "We want this to be modular and composable."

The constraint that makes this work is also the most unusual: **zero external dependencies**. Every package -- including N-dimensional collision detection, A\* pathfinding, behavior tree evaluation, and utility AI scoring -- is implemented using nothing but the Python standard library.

"Less stuff to learn from, readable APIs and decisions," unmarco says of the choice. It's a constraint that doubles as a teaching tool. When there's no numpy to hide behind, the vector math has to be legible. When there's no third-party event system, you have to understand what a signal bus actually does.

## Determinism as a Feature

One design decision permeates the entire codebase: determinism. The engine seeds its random number generator from `os.urandom(8)` at creation time, then passes that RNG through `TickContext` to every system on every tick. Fixed timestep plus seed-controlled RNG plus snapshot/restore means you can replay any simulation perfectly.

I ask unmarco how important determinism is as a design goal.

"Very. The simulation aspect is as much important as the game engine aspect," he says. "This tries to embody Will Wright's vision of games as 'Toys'."

The Will Wright reference is apt. Wright -- the creator of SimCity, The Sims, and Spore -- famously described his games not as stories with win conditions but as toys: systems you poke at to see what happens. tick-engine is built for that kind of exploration. Snapshot a simulation state, tweak a parameter, replay, compare. The engine doesn't care what you're simulating. It just guarantees that the same inputs produce the same outputs.

## The Colony: A Living Integration Test

The most revealing artifact in the repository isn't the engine -- it's `tick-colony`. What started as the original consumer of the core engine became the forcing function that shaped every extension's API.

"Having this ongoing 'function' -- the colony -- grow along with the library is one of the things that made it work," unmarco says. "Something tangible that actually shows the progress. We went from a 'perfect utopian colony' -- no emergencies, no crisis, no bad stuff essentially happening -- to a realistic scenario with realistic events, seasons, decisions."

You can trace this evolution in the commits. Early colony code manually spawns entities with imperative helper functions. After `tick-blueprint` ships, entity creation becomes data-driven recipes. After `tick-fsm` ships, the decision system moves from `if/elif` chains to declarative state machines with named guards. After `tick-event` ships, seasons arrive. After `tick-ability` ships, entities gain powers with cooldowns and charges.

Each extension didn't just add a feature -- it retroactively improved the colony. And the colony's needs drove what extensions got built next.

## The Test Ratio

One number stands out in the codebase metrics: approximately 24,000 lines of tests for 5,000 lines of implementation. A nearly 5:1 ratio.

I ask whether unmarco drove the testing or pushed back on it.

"I never pushed back on tests, so that's all Claude's thinking," he says. "We may decide to trim them later, if needed."

This is quietly significant. Left to its own judgment on test coverage, Claude produced nearly five lines of test code for every line of implementation -- including edge cases like despawning entities during iteration, filter combinations on queries, snapshot round-trips across every component type, and parametric tests across all three grid topologies. 1,399 tests across 77 test files, all passing, with mypy strict mode enforced across every package.

## Five Demos, One Ecosystem

The repository includes five pygame demonstrations, each exercising different combinations of packages:

- **placement**: Grid-based entity placement with blueprints and terrain
- **easing-gallery**: Animated easing function showcase using tweens, FSMs, and signals
- **colony-sim**: A full colony builder exercising all 13 original packages
- **physics-sandbox**: Interactive 2D collision sandbox
- **ecosystem-arena**: Predator-prey simulation with behavior trees and utility AI

The ecosystem-arena demo is particularly striking. Predators use behavior trees to patrol, chase, and attack. Prey use utility AI to score competing priorities -- flee, forage, rest -- and act on the highest-scoring option. Both species have kinematic bodies with force-based movement and circle colliders for spatial awareness. The entire thing runs on tick-engine's deterministic loop. Same seed, same ecosystem, same outcome.

"I'm impressed at the breadth of what's possible," unmarco says. "Every new piece we added made it exponentially more versatile and gave birth to the most interesting examples."

## What AI-Assisted Engineering Actually Looks Like

There's a tendency in conversations about AI-assisted coding to reach for extremes: either it's a revolution that will replace programmers, or it's autocomplete that can't handle real architecture. tick-engine sits in neither camp. It's evidence of a third thing: a disciplined human-AI engineering process that produces real, tested, well-architected software at an unusual pace.

The key, according to unmarco, is patience.

"Patience in building something in pieces that are small enough to keep in your head," he says. "This served us pretty well in preventing bloat and over-engineering."

Each package targets roughly 200 lines of implementation. Each has a focused responsibility. Each ships with comprehensive tests and strict type checking. The pieces are small enough that a human can review them thoroughly, understand them completely, and catch problems early. The AI handles the volume -- the boilerplate, the edge cases, the test permutations -- while the human maintains the architectural vision.

unmarco's advice for anyone attempting a similar project:

> "Think it through and write everything. Keep notes, review and assess at regular intervals. Don't let the 'speed' the AI affords you override sane engineering principles."

## What's Next: Giving Entities a Mind

The project isn't finished. When I ask what's coming, unmarco shares a spec that makes clear the ambition hasn't dimmed -- if anything, it's escalating.

The next package is `tick-llm`: a strategic AI layer that connects entities to large language models. The design is a three-tier architecture that reads like a thesis on how to make NPCs think:

```
STRATEGIC LAYER  (tick-llm)     — LLM deliberation every N ticks
        ↓ writes to Blackboard
TACTICAL LAYER   (tick-ai)      — Behavior trees / utility AI every tick
        ↓ component mutations
REACTIVE LAYER   (tick-physics)  — Physics / FSM every tick
```

The key insight is the bridge: the LLM never touches the tick loop. Queries are dispatched to a thread pool asynchronously. While the LLM is thinking -- which might take seconds -- the entity keeps acting on its last known strategy. The behavior tree doesn't know or care whether its Blackboard was written by a parser processing an LLM response or by hand. The tactical layer is always running. The strategic layer is eventually consistent.

The spec is characteristically thorough. It defines composable prompt layers (roles, personalities, context templates), a client protocol that accepts any LLM provider, rate limiting, retry logic with cooldown state machines, observability callbacks, and a mock client for deterministic testing. The entity doesn't just call an API -- it has a structured lifecycle for how strategic reasoning enters the simulation without disrupting it.

Consider what this means in practice: a predator entity in the ecosystem-arena demo could have its patrol routes dictated by a behavior tree (tactical, every tick), its physics handled by the collision system (reactive, every tick), and its hunting *strategy* -- where to ambush, which prey to target, when to conserve energy -- reasoned about by an LLM every five seconds. The LLM writes `{"goal": "ambush", "priority_target": 7, "stance": "aggressive"}` to the Blackboard. The behavior tree reads "goal is ambush" and switches to ambush behavior. The entity acts on stale strategy while fresh strategy computes. No tick ever stalls.

It's the logical conclusion of everything tick-engine has been building toward: a simulation framework where entities have reflexes *and* deliberation, operating at different timescales, communicating through the same ECS primitives that have been there since day one.

## The Bigger Picture

What exists today is already a complete, functional ecosystem: a minimal tick engine, 13 composable extensions, a colony-builder framework, five visual demos, 1,399 tests, strict type checking, CI, and a clean git history -- all stdlib-only, all typed, all documented.

But what the tick-llm spec reveals is that this was never just a learning exercise. The architecture -- the Blackboard as a universal data bridge, the protocol-based abstractions, the deterministic core with async-capable edges -- was quietly designed to accommodate something like this from the beginning. The colony grew from utopia to realism. The engine is growing from simulation to cognition.

Whether anyone builds a game on tick-engine matters less than what the project demonstrates about its own construction. This is what AI-assisted engineering looks like when you bring engineering discipline to the AI. Not faster slop. Not magic. Just good software, built at an unusual cadence, by a human who refused to let the speed override the process.

---

*tick-engine is open source at [github.com/unmarco/tick-engine](https://github.com/unmarco/tick-engine). It requires Python 3.11+ and zero external dependencies.*

*The engine and all 14 extension packages are available as a uv workspace monorepo. The entire test suite runs with `uv run pytest`.*

---

**Stats at a glance:**

| Metric | Value |
|--------|-------|
| Development time | ~48 hours |
| Packages | 15 (1 core + 13 extensions + 1 framework) |
| Implementation LOC | ~5,000 |
| Test LOC | ~24,000 |
| Tests passing | 1,399 |
| External dependencies | 0 |
| Git commits | 77 |
| Releases | 11 |
| Type checking | mypy strict, all packages |
| Pygame demos | 5 |
