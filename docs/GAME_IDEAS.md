# tick-engine Game Ideas

A collection of game concepts well-suited to the tick-engine architecture. Each leverages the ECS core, the extension ecosystem, and the upcoming tick-llm strategic AI layer.

---

## 1. The Living Dungeon (Text World)

**Genre**: Modern text adventure / interactive fiction
**Inspiration**: Zork, Infocom, Nozork
**Key packages**: tick, tick-llm, tick-command, tick-atlas, tick-spatial, tick-fsm, tick-event, tick-ability, tick-resource, tick-signal, tick-schedule, tick-blueprint

### Concept

A text adventure where the world simulates whether the player acts or not. NPCs have routines, needs, and agendas. Torches burn down. Water rises. Guards patrol. The dungeon is alive.

The player interacts through natural language, parsed by tick-llm into typed commands (tick-command). The world responds through an LLM narrator that reads actual world state -- not canned descriptions. Every room, object, and NPC is an entity with components. The atlas defines the map. Spatial indexing handles adjacency and line-of-sight. Events drive atmospheric shifts (nightfall, flooding, a distant collapse).

### What makes it tick-native

- **NPCs live on their own clock.** The innkeeper has a NeedSet, an FSM for daily routine, a BT for player interaction, and tick-llm for long-term reasoning ("should I trust this stranger?"). Walk into the tavern and she's mid-conversation, not frozen waiting for input.
- **Time is mechanical.** The torch is a Timer component. It burns down whether you're solving puzzles or standing still. The event scheduler fires "nightfall" every 200 ticks. The signal bus propagates "torch_extinguished" and every system that cares reacts.
- **Puzzles can be emergent.** A locked door has a `Locked` component with a `key_id`. The key is an entity. But the innkeeper also has the `Ability` to unlock doors. You could find the key, pick the lock, break the door, or persuade the innkeeper. Same world state outcome, different paths, none hardcoded.
- **The world has causality.** Flood a room by breaking a pipe. The atlas updates passability. Pathfinding routes change. Three rooms away, an NPC's BT detects rising water via Blackboard. The NPC evacuates -- not scripted, but emergent from composed systems.

### The Nozork connection

Nozork's six AI levels (parser, narrator, dialog, examine, ambient, hints) map onto tick-engine cleanly:

| Nozork AI Level | tick-engine equivalent |
|---|---|
| parser | tick-command + tick-llm (natural language -> typed commands) |
| narrator | tick-llm context template reading world state -> prose |
| dialog | tick-llm agent on the NPC, personality-driven, world-aware |
| examine | tick-llm reading entity components, atlas, nearby signals |
| ambient | tick-event + tick-llm reacting to world events |
| hints | tick-llm agent reading player Blackboard + puzzle state |

The "always playable" fallback principle carries over: if the LLM is down, the BT still runs, the FSM still transitions, the game degrades but never breaks.

### Minimal viable version

One room. One NPC. One puzzle. One torch that burns down. Prove the loop works: natural language in, world state changes, narrator describes what happened in prose.

---

## 2. Office Politics Simulator

**Genre**: Turn-based social simulation
**Inspiration**: The Office, Corporate drama, The Sims at work
**Key packages**: tick, tick-llm, tick-ai, tick-fsm, tick-schedule, tick-signal, tick-event, tick-resource, tick-ability, tick-colony (needs, stats, lifecycle)

### Concept

A turn-based simulation of office life. Each tick is one hour. A workday is 8 ticks. A week is 40. A quarter is ~520. Employees have personalities, ambitions, grudges, and alliances. Projects have deadlines. The coffee machine breaks. Drama emerges.

The player can be a manager making decisions (hire, fire, assign projects, mediate conflicts) or an observer watching the office ecosystem evolve. The LLM provides strategic reasoning for each employee: career goals, social maneuvering, alliance formation, grudge maintenance.

### What makes it tick-native

- **The three-tier AI is purpose-built for social dynamics.**
  - Reactive: FSM tracks emotional state (focused, frustrated, gossiping, on-break). Periodic timers fire for meetings, lunch, end of day.
  - Tactical: BT handles moment-to-moment decisions. "Am I in a meeting? Attend. Task blocked? Ask for help. Energy low? Break room. Otherwise, work." Utility AI scores competing priorities.
  - Strategic: LLM reasons about alliances, grudges, career ambitions. "I'm going to undermine Karen's promotion because she took credit for my work." Writes stance, goals, and social strategy to Blackboard.
- **Consequences are mechanical, not flavor text.** Karen's hostile stance changes her BT behavior, which lowers her collaboration stat, which reduces project velocity, which misses the deadline, which triggers the quarterly review event, which the boss's LLM agent reads in its context template.
- **Gossip propagates through the signal bus.** "Did you hear what happened in the meeting?" is a signal. Employees subscribed to social signals update their Blackboard. Their next LLM query incorporates the gossip. Alliances shift. Drama compounds.
- **Colony primitives fit naturally.** NeedSet tracks stress, motivation, social energy, hunger. StatBlock holds productivity, charisma, technical skill. Lifecycle handles hiring and departure. Containment puts employees in departments.

### New components needed

- **Relationship**: Tracks sentiment between entity pairs (trust, rivalry, friendship, resentment). Could be a dict on a component or a separate entity per relationship.
- **Reputation**: A "public Blackboard" -- observable traits and standing that other entities' context templates can read.

### Turn structure

```
1 tick = 1 hour
8 ticks = 1 workday
40 ticks = 1 work week
~520 ticks = 1 quarter

LLM query interval: ~8 ticks (once per day)
"Employee goes home, reflects, comes back with updated priorities"
```

### Minimal viable version

One department. One manager (player or AI). Three employees with distinct personalities. One project with a deadline. Watch who cooperates, who slacks, who blames whom when things go wrong.

---

## 3. Plague Town

**Genre**: Crisis management roguelike
**Inspiration**: Plague Inc (inverted), Frostpunk, Pathologic
**Key packages**: tick, tick-llm, tick-colony, tick-spatial, tick-atlas, tick-event, tick-fsm, tick-ability, tick-resource, tick-schedule, tick-signal

### Concept

A medieval town hit by plague. The player is the town physician. Each tick is one day. Citizens have health, infection status, social roles, and needs. The disease spreads through spatial proximity and social interaction. Resources (medicine, food, clean water) are scarce. Events escalate: quarantine riots, fleeing refugees, the church demanding prayer over medicine, the lord demanding the gates stay open for trade.

The player makes decisions through the command queue: quarantine a district, allocate medicine, order a curfew, burn infected houses. Every decision has mechanical consequences and social fallout.

### What makes it tick-native

- **Disease is spatial.** Infection spreads via tick-spatial proximity checks. The atlas tracks contamination per tile. Pathfinding avoids contaminated zones (for NPCs that know about them). Grid2D's `in_radius` finds exposure candidates every tick.
- **The colony primitives model a town perfectly.** NeedSet: health, hunger, morale, faith. StatBlock: constitution, social standing, wealth. Lifecycle: birth, aging, death. Containment: citizens belong to households, households to districts.
- **Events drive escalation.** tick-event schedules the plague's phases (first case, outbreak, peak, decline or collapse). Probabilistic events: a rat migration, a traveling merchant carrying a new strain, a miracle cure rumor. Cycles: seasons affect disease virulence and crop yields.
- **Abilities model player powers.** "Quarantine district" is an Ability with a cooldown (you can't keep declaring emergencies), a resource cost (guards, barricades), and an effect pipeline (updates atlas passability, fires signal, triggers NPC reactions).
- **NPCs reason about survival.** The LLM strategic layer gives citizens agency. The blacksmith's LLM decides to flee the city, weighing his family's safety against losing his livelihood. The priest's LLM decides to defy quarantine orders because faith matters more. The merchant's LLM decides to hoard medicine and sell it at markup. Every NPC's strategy is legible in their Blackboard.
- **Deterministic replay enables "what if."** Same plague, same town, different decisions. Snapshot at day 10, try quarantine. Restore, try isolation. Compare outcomes. Will Wright's "toy" philosophy in action.

### Minimal viable version

A 10x10 grid town. 20 citizens in 5 households. One disease with simple spatial spread. Three resources: food, medicine, morale. One event: "the plague arrives." Watch it unfold, make one decision (quarantine or don't), see the divergence.

---

## 4. Merchant Caravan

**Genre**: Turn-based trading roguelike
**Inspiration**: Oregon Trail, Curious Expedition, Silk Road history
**Key packages**: tick, tick-llm, tick-spatial, tick-atlas, tick-resource, tick-event, tick-fsm, tick-schedule, tick-ability, tick-signal, tick-command, tick-blueprint

### Concept

Lead a caravan across a procedurally described trade network. Each tick is one day of travel. Nodes on the map are cities with different goods, prices, cultures, and dangers. The space between cities is where things go wrong: bandits, weather, illness, broken wheels, mutiny.

Crew members are entities with personalities, skills, and loyalty. The LLM gives them strategic reasoning about whether to stay with the caravan or desert, whether to support the player's risky shortcut through bandit territory, whether to steal from the cargo.

### What makes it tick-native

- **The trade network is a graph on the atlas/spatial layer.** Cities are coordinates on a HexGrid. Edges have travel cost (tick-atlas movement cost). Pathfinding finds optimal routes. Events modify edge costs (road washed out, bandits on the mountain pass).
- **Resources are the core mechanic.** tick-resource tracks cargo (silk, spice, iron, water, food). Recipes model trade: buy low here, sell high there. Decay models spoilage. Inventory capacity forces decisions.
- **Crew members are colony-style entities.** NeedSet: hunger, morale, health. StatBlock: navigation, combat, trading, medicine. FSM: loyal, grumbling, plotting, deserted. BT: day-to-day behavior. LLM: strategic loyalty decisions.
- **Events punctuate the journey.** Sandstorm (3-day duration, movement cost doubled). Oasis discovered (probabilistic, resource windfall). Bandit ambush (triggers combat sub-system). Festival at destination city (prices shift).
- **The command queue handles player decisions.** "Set course for Damascus." "Ration water." "Hire the mercenary." "Bribe the border guard." Each command has mechanical consequences validated by the queue's handler.

### Minimal viable version

Three cities in a triangle. One caravan with a player and two crew members. Three trade goods. One route hazard (bandits, resolved by crew combat stats). Buy low, sell high, don't die.

---

## 5. Ecosystem Terrarium

**Genre**: Observation / sandbox simulation
**Inspiration**: SimLife, Spore (cell stage), virtual aquariums, Conway's Game of Life
**Key packages**: tick, tick-ai, tick-physics, tick-spatial, tick-atlas, tick-resource, tick-event, tick-schedule, tick-fsm, tick-signal

### Concept

A self-contained ecosystem in a bottle. No player agency -- just observation and occasional parameter tweaking. Species evolve behaviors over generations. Plants grow based on light and water (atlas properties). Herbivores eat plants. Predators eat herbivores. Scavengers clean up. The ecosystem finds equilibrium or collapses.

This is the ecosystem-arena demo taken to its logical conclusion. The difference: longer timescales, reproduction, mutation, and environmental pressure.

### What makes it tick-native

- **Already half-built.** The ecosystem-arena demo proves the predator-prey loop works with BTs and utility AI on tick-engine. This extends it with reproduction (lifecycle + blueprint spawning), mutation (randomized stat variation on spawn), and environmental factors (atlas-driven terrain with resource distribution).
- **No LLM needed (but could benefit).** The tactical layer (BT + utility AI) is sufficient for creature behavior. The LLM could be added later for "narrator mode" -- an observer AI that describes what's happening in the ecosystem in natural language, like a nature documentary.
- **Determinism enables experimentation.** Same seed, same ecosystem. Tweak one parameter (predator speed +10%), replay, watch the cascade. This is the Will Wright "toy" at its purest.
- **Emergent complexity from simple rules.** Each creature has: KinematicBody (movement), BehaviorTree (decisions), NeedSet (hunger, energy, reproduction drive), StatBlock (speed, perception range, attack power), Lifecycle (age, max lifespan). Reproduction spawns a new entity via blueprint with slightly mutated stats. Natural selection emerges from the simulation, not from code.

### Minimal viable version

A 30x30 grid. Grass (grows on Periodic timer). 10 herbivores (eat grass, flee predators, reproduce). 3 predators (hunt herbivores, reproduce). Run for 10,000 ticks. Plot population curves. Watch equilibrium or extinction.

---

## 6. Haunted Mansion Mystery

**Genre**: Turn-based investigative horror
**Inspiration**: Clue, Return of the Obra Dinn, Betrayal at House on the Hill
**Key packages**: tick, tick-llm, tick-spatial, tick-atlas, tick-fsm, tick-event, tick-signal, tick-schedule, tick-command, tick-ability

### Concept

A group of characters trapped in a mansion. One is a murderer (or something worse). The player investigates: explore rooms, examine evidence, interrogate suspects, piece together what happened. The twist: the mansion simulates in real time. NPCs move between rooms on their own schedules. Events fire (lights go out, a scream from the library, a door locks behind you). The killer acts on their own BT + LLM strategy.

### What makes it tick-native

- **NPCs have autonomous schedules and secrets.** Each character has an FSM (calm, nervous, hiding, fleeing, attacking), a BT for moment-to-moment behavior, and an LLM strategic layer that reasons about self-preservation, deception, and their hidden agenda. The butler's LLM knows he saw something and is deciding whether to tell you. The heiress's LLM is fabricating an alibi.
- **The mansion is spatial and reactive.** Atlas tracks room properties (lit/dark, locked/unlocked, trapped). Spatial indexing handles who's in which room. Signals propagate sound ("you hear footsteps above"). Events schedule the horror: the storm intensifies, the power cuts, a secret passage opens at midnight.
- **Evidence is mechanical, not scripted.** A bloodstain is an entity with components: location, timestamp (tick created), associated entity (the victim). The murder weapon is an entity the killer detached from their inventory. The player's investigation is querying the world state. The LLM narrator presents it atmospherically, but the facts are in the ECS.
- **Every playthrough is different.** The killer is assigned randomly (seed-controlled). Their LLM strategic layer adapts to what happens. If the player gets close to the truth, the killer's strategy shifts. Deterministic replay lets you verify: "was the clue there all along?"

### Minimal viable version

Five rooms. Three suspects. One victim (found at game start). Three clues hidden in the world. One killer with an LLM-driven deception strategy. Interrogate, explore, accuse. Get it right or don't.

---

## Comparison Matrix

| Idea | Tick = | Core tension | LLM role | MVP scope |
|------|--------|-------------|----------|-----------|
| Living Dungeon | 1 action/moment | Exploration vs. time pressure | Parser, narrator, NPC minds | 1 room, 1 NPC, 1 puzzle |
| Office Politics | 1 hour | Productivity vs. social dynamics | Employee strategic reasoning | 3 employees, 1 project |
| Plague Town | 1 day | Public health vs. social order | Citizen survival reasoning | 20 citizens, 1 disease |
| Merchant Caravan | 1 day of travel | Profit vs. survival vs. crew loyalty | Crew loyalty and strategy | 3 cities, 2 crew members |
| Ecosystem Terrarium | 1 moment | Population balance | Optional narrator | Grass + 13 creatures |
| Haunted Mansion | 1 minute | Investigation vs. the killer's plan | Deception, alibi fabrication | 5 rooms, 3 suspects |

---

## Common Patterns

All of these share structural traits that tick-engine handles well:

1. **Time is discrete and meaningful.** Each tick represents a concrete unit (hour, day, moment). This maps to the fixed-timestep model naturally.
2. **Entities have inner life.** The three-tier AI (strategic/tactical/reactive) gives characters depth without scripting.
3. **The world simulates independently of the player.** Things happen whether you act or not. The engine doesn't wait.
4. **Consequences compound.** Small state changes cascade through systems. The signal bus and Blackboard propagate information. Emergent behavior arises from composition.
5. **Determinism enables replay and experimentation.** Same seed, different choices, compare outcomes. The "toy" philosophy.
6. **The LLM enhances but isn't required.** Every game works without the strategic layer. The BT/FSM tactical layer keeps entities functional. The LLM adds depth, not dependency.
