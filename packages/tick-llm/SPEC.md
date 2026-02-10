# tick-llm Technical Specification

**Package**: tick-llm
**Version**: 0.1.0
**Status**: Draft
**Date**: 2026-02-10
**Author**: W72 Spec Writer

---

## 1. Product Overview

### 1.1 Problem Statement

The tick-engine ecosystem provides tactical AI (behavior trees, utility AI) and reactive systems (FSM, physics) that operate every tick. These systems excel at moment-to-moment decision-making but lack the capacity for long-horizon strategic reasoning -- the kind of deliberation that makes characters feel truly intelligent.

Large Language Models can provide this strategic reasoning, but they operate on fundamentally different timescales. An engine running at 20 TPS cannot wait 500ms--2s for an API call. A synchronous LLM call would freeze the entire simulation.

### 1.2 Solution

tick-llm provides a **strategic AI layer** that sits above the existing tactical (tick-ai) and reactive (tick-physics, tick-fsm) layers. It manages the full lifecycle of asynchronous LLM queries -- prompt assembly, non-blocking dispatch, response parsing -- and bridges the gap between slow strategic reasoning and fast tactical execution through the **Blackboard** component from tick-ai.

The architecture follows a three-tier AI model:

```
+-----------------------------------------------+
|  STRATEGIC LAYER  (tick-llm)                   |
|  LLM deliberation every N ticks                |
|  Writes high-level directives to Blackboard    |
+-----------------------------------------------+
          |  Blackboard (bridge)  |
+-----------------------------------------------+
|  TACTICAL LAYER  (tick-ai)                     |
|  Behavior trees / utility AI every tick        |
|  Reads Blackboard, picks concrete actions      |
+-----------------------------------------------+
          |  Component mutations  |
+-----------------------------------------------+
|  REACTIVE LAYER  (tick-physics, tick-fsm)      |
|  Physics / state machines every tick           |
|  Immediate responses to world state            |
+-----------------------------------------------+
```

### 1.3 Value Proposition

- Entities can reason about goals, alliances, terrain strategy, and resource allocation at a level behavior trees cannot express
- The LLM never blocks the tick loop -- entities continue acting on stale strategy while new strategy is computed
- Prompt composition is fully modular -- roles, personalities, and context templates are defined independently and mixed freely
- Client-agnostic design means any LLM provider (OpenAI, Anthropic, local models, mock) plugs in via a single protocol
- Observable by design -- every query carries cost, latency, and error metadata

### 1.4 Target Users

- Game developers using tick-engine who want NPCs with emergent, believable behavior
- Simulation builders who need agents that can reason about long-term plans
- Researchers exploring LLM-driven agent architectures within an ECS framework

### 1.5 Success Metrics

- Zero tick-loop stalls: no LLM call ever blocks `Engine.step()` or `Engine.run()`
- Prompt assembly under 1ms per entity per tick
- Graceful degradation: entity behavior is coherent even when LLM is unavailable
- Full testability: all features exercisable with a synchronous mock client

### 1.6 Scope

**In scope (v0.1.0)**:
- LLMAgent component and LLMManager registry
- Composable prompt layers (role, personality, context)
- Async query lifecycle with ThreadPoolExecutor
- Response parsing with Blackboard integration
- LLMClient protocol (abstract interface)
- MockClient for deterministic testing
- Rate limiting (per-tick and per-second)
- Error handling and graceful degradation
- Observable callbacks (on_query, on_response, on_error)
- System factory: `make_llm_system(manager)`

**Out of scope (future versions)**:
- Batching multiple entities into a single LLM call
- Semantic caching / prompt deduplication
- Conversation history / multi-turn dialogue
- Streaming responses
- Token budget management
- Built-in provider implementations (OpenAI, Anthropic, etc.)
- Snapshot/restore of in-flight queries

---

## 2. Functional Requirements

### 2.1 User Stories

**US-1: Define an LLM-driven agent**
As a developer, I want to register roles, personalities, context templates, and parsers by name in an LLMManager, then attach an LLMAgent component to an entity referencing those names, so that the entity periodically queries an LLM for strategic directives.

*Acceptance criteria*:
- Roles, personalities, context templates, and parsers are registered by name
- LLMAgent component references these names and specifies a query interval
- The system validates that all referenced names exist when the first query fires
- Missing definitions produce a logged warning and skip the query (no crash)

**US-2: Non-blocking LLM queries**
As a developer, I want LLM calls to execute asynchronously so that the tick loop never stalls waiting for a response.

*Acceptance criteria*:
- The LLM system submits queries to a thread pool, never blocks the calling thread
- The entity's `pending` flag is set to True while a query is in flight
- The BT/utility system continues running on the entity's existing Blackboard data
- Completed responses are harvested on subsequent ticks

**US-3: Blackboard integration**
As a developer, I want LLM responses to be parsed and written to the entity's Blackboard so that existing behavior trees can read the strategic directives without any coupling to tick-llm.

*Acceptance criteria*:
- A registered parser function receives the raw LLM response string and the entity's Blackboard
- The parser writes structured data to Blackboard keys
- Behavior trees and utility AI read Blackboard keys as normal -- no awareness of tick-llm needed
- If no parser is registered for the agent's parser name, a default JSON parser is used

**US-4: Rate limiting**
As a developer, I want to configure maximum queries per tick and per second so that I can control API costs and avoid rate-limit errors from providers.

*Acceptance criteria*:
- `max_queries_per_tick` limits how many entities can fire queries in a single tick
- `max_queries_per_second` provides a sliding-window rate limit across ticks
- Excess queries are deferred to the next eligible tick (not dropped)
- Rate limit configuration is set on LLMManager

**US-5: Error handling**
As a developer, I want LLM errors (timeouts, API failures, malformed responses) to be handled gracefully so that entity behavior degrades rather than crashes.

*Acceptance criteria*:
- Network/API errors clear `pending` and increment a retry counter on the agent
- After `max_retries` consecutive failures, the agent enters a cooldown period
- The `on_error` callback fires with error details for observability
- The entity continues acting on its last known Blackboard state
- Parser exceptions are caught, logged via `on_error`, and treated as a failed query

**US-6: Observable lifecycle**
As a developer, I want callbacks for query dispatch, response receipt, and errors so that I can monitor costs, latency, and failure rates.

*Acceptance criteria*:
- `on_query` fires when a query is submitted, with entity ID, assembled prompt size, and tick number
- `on_response` fires when a response is received, with entity ID, latency, response size, and tick number
- `on_error` fires on any failure, with entity ID, error type, error message, and tick number

**US-7: Testability with mock client**
As a developer, I want a mock LLM client that returns deterministic responses so I can write tests without making real API calls.

*Acceptance criteria*:
- MockClient accepts a response mapping or a callable that produces responses
- MockClient conforms to the LLMClient protocol
- MockClient supports configurable latency simulation (including zero for synchronous-feeling tests)
- All tick-llm features are fully testable using MockClient

### 2.2 Feature List (MoSCoW)

**Must have**:
- LLMAgent component
- LLMManager registry (roles, personalities, contexts, parsers, client)
- LLMClient protocol
- Non-blocking query lifecycle via ThreadPoolExecutor
- Blackboard write-through on response
- `make_llm_system(manager)` factory
- `on_query` / `on_response` / `on_error` callbacks
- Rate limiting (per-tick)
- Error handling with retry logic
- MockClient for testing
- Default JSON parser

**Should have**:
- Per-second sliding-window rate limiting
- Cooldown period after max retries
- Query priority (some entities more important than others)
- Configurable thread pool size

**Could have**:
- Prompt cost estimation callback (token counting hook)
- Response validation against a caller-provided JSON schema
- Context hash for detecting unchanged prompts (skip redundant queries)
- Deferred query queue with priority ordering

**Won't have (v0.1.0)**:
- Multi-turn conversation history
- Streaming responses
- Built-in provider clients (OpenAI, Anthropic)
- Batching multiple entities into one LLM call
- Snapshot/restore of pending queries

### 2.3 Business Rules

**BR-1: Query eligibility**
An entity is eligible for a query when ALL of the following are true:
- `tick_number - agent.last_query_tick >= agent.query_interval`
- `agent.pending` is False
- `agent.cooldown_until <= tick_number`
- The per-tick and per-second rate limits have not been exhausted

**BR-2: Prompt assembly order**
The system prompt is assembled as: role text + newline separator + personality text.
The user message is the return value of the context template function.
These are distinct message roles in the LLM call.

**BR-3: Stale strategy**
While a query is pending, the entity's BT/utility system continues executing against whatever is currently in the Blackboard. There is no "waiting" state -- the tactical layer is always active.

**BR-4: Response delivery**
Responses are delivered on the next tick AFTER the future completes. The system never processes futures mid-tick. This ensures consistent world state during a tick.

**BR-5: Error escalation**
On query failure: increment `agent.consecutive_errors`. If `consecutive_errors >= agent.max_retries`, set `agent.cooldown_until = tick_number + agent.cooldown_ticks`. On successful response, reset `consecutive_errors` to 0.

**BR-6: Thread pool lifecycle**
The ThreadPoolExecutor is created when `make_llm_system()` is called and should be shut down when the engine stops. The system factory accepts an optional `on_shutdown` hook, or the caller manages the executor externally.

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
+-------------------------------------------------------------------+
|                        tick Engine Loop                            |
|                                                                   |
|  Systems run sequentially each tick:                              |
|  [signal_sys] [llm_sys] [bt_sys] [utility_sys] [physics_sys] ... |
|                                                                   |
|  llm_sys does THREE things per tick:                              |
|    1. Harvest completed futures -> parse -> write Blackboard      |
|    2. Check eligible entities -> assemble prompts -> submit       |
|    3. Clean up cancelled/timed-out queries                        |
+-------------------------------------------------------------------+
         |                                          ^
         | submit(executor, client.query, ...)      | future.result()
         v                                          |
+-------------------------------------------------------------------+
|                    ThreadPoolExecutor                              |
|  Worker threads make blocking LLM API calls                       |
|  Each call: client.query(system_prompt, user_message) -> str      |
+-------------------------------------------------------------------+
         |
         v
+-------------------------------------------------------------------+
|                    LLMClient (Protocol)                            |
|  Any implementation: OpenAI, Anthropic, local, mock               |
+-------------------------------------------------------------------+
```

### 3.2 Component Interaction

```
LLMManager (registry)
  |-- roles: dict[str, str]
  |-- personalities: dict[str, str]
  |-- contexts: dict[str, ContextFn]
  |-- parsers: dict[str, ParserFn]
  |-- client: LLMClient
  |-- config: LLMConfig (rate limits, thread pool size, timeouts)
  |-- callbacks: on_query, on_response, on_error

LLMAgent (component, attached to entity)
  |-- role: str (references manager.roles)
  |-- personality: str (references manager.personalities)
  |-- context: str (references manager.contexts)
  |-- parser: str (references manager.parsers, "" = default JSON)
  |-- query_interval: int (ticks between queries)
  |-- priority: int (higher = queried first when rate-limited)
  |-- last_query_tick: int
  |-- pending: bool
  |-- consecutive_errors: int
  |-- max_retries: int
  |-- cooldown_ticks: int
  |-- cooldown_until: int

Blackboard (from tick-ai, attached to same entity)
  |-- data: dict[str, Any]
  |-- (written to by parser after LLM response)

make_llm_system(manager) -> System
  |-- creates ThreadPoolExecutor
  |-- returns (World, TickContext) -> None callable
  |-- manages _pending_futures: dict[int, Future]
```

### 3.3 Technology Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Python 3.11+ | Matches ecosystem |
| Async model | `concurrent.futures.ThreadPoolExecutor` | stdlib, non-blocking, works in sync tick loop |
| LLM interface | Protocol class (structural typing) | Client-agnostic, no external deps in tick-llm itself |
| JSON parsing | `json` (stdlib) | Default response format |
| Build system | hatchling | Matches ecosystem |
| Package manager | uv (workspace member) | Matches ecosystem |
| Type checking | mypy strict | Matches ecosystem |

### 3.4 Dependency Policy

tick-llm is the **first tick-engine package to allow external dependencies** in its consumers, but tick-llm itself depends only on:
- `tick >= 0.3.0` (core engine)
- `tick-ai >= 0.1.0` (Blackboard component)

The LLMClient protocol is defined by tick-llm. Provider implementations (OpenAI, Anthropic, etc.) are written by the consumer and depend on the provider's SDK. tick-llm never imports any LLM SDK.

This preserves the "stdlib only" philosophy: tick-llm itself has no external dependencies. The external dependency boundary is pushed to user code that implements the LLMClient protocol.

---

## 4. Data Architecture

### 4.1 Entities

**LLMAgent** -- Mutable dataclass component attached to entities that should query an LLM.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| role | str | (required) | Name of the role definition in LLMManager |
| personality | str | (required) | Name of the personality definition in LLMManager |
| context | str | (required) | Name of the context template in LLMManager |
| parser | str | "" | Name of the parser in LLMManager; empty string = default JSON parser |
| query_interval | int | 100 | Minimum ticks between queries (100 ticks at 20 TPS = 5 seconds) |
| priority | int | 0 | Query priority; higher values are queried first when rate-limited |
| last_query_tick | int | 0 | Tick number of most recent query dispatch |
| pending | bool | False | True while a query is in flight |
| consecutive_errors | int | 0 | Number of consecutive query failures |
| max_retries | int | 3 | Max consecutive errors before cooldown |
| cooldown_ticks | int | 200 | Ticks to wait after hitting max_retries |
| cooldown_until | int | 0 | Tick number when cooldown expires |

**Blackboard** (from tick-ai) -- Already exists. tick-llm writes to it, tick-ai reads from it. No changes needed.

### 4.2 Registry Data (LLMManager Internal State)

| Registry | Key Type | Value Type | Description |
|----------|----------|------------|-------------|
| roles | str | str | Static role text (system prompt component) |
| personalities | str | str | Static personality text (system prompt component) |
| contexts | str | ContextFn | Callable that reads world state, returns user message string |
| parsers | str | ParserFn | Callable that parses LLM response, writes to Blackboard |

**ContextFn** signature: `(World, int) -> str`
- Receives the world and entity ID
- Returns a formatted string describing what the entity currently perceives
- Called on the main thread during prompt assembly (must be fast)

**ParserFn** signature: `(str, Blackboard) -> None`
- Receives the raw LLM response string and the entity's Blackboard
- Writes parsed data to `blackboard.data`
- Called on the main thread during response harvesting
- Should handle malformed responses gracefully (log warning, write nothing)

### 4.3 Configuration Data (LLMConfig)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| max_queries_per_tick | int | 1 | Max new queries dispatched per tick |
| max_queries_per_second | int | 5 | Sliding-window rate limit (should-have) |
| thread_pool_size | int | 4 | ThreadPoolExecutor max workers |
| query_timeout | float | 30.0 | Seconds before a pending query is considered timed out |

### 4.4 In-Flight Query State (System Internal)

The system maintains a dictionary mapping entity IDs to pending futures. This is internal to the system closure -- not a component, not on the manager.

| Field | Type | Description |
|-------|------|-------------|
| entity_id | int | The entity that initiated the query |
| future | Future[str] | The concurrent.futures.Future holding the LLM response |
| submitted_at | float | `time.monotonic()` timestamp for timeout detection |
| submitted_tick | int | Tick number when the query was dispatched |

### 4.5 Data Flow

```
1. PROMPT ASSEMBLY (main thread, during llm_system tick)
   LLMManager.roles[agent.role]         --> system_prompt (part 1)
   LLMManager.personalities[agent.personality] --> system_prompt (part 2)
   LLMManager.contexts[agent.context](world, eid) --> user_message

2. QUERY DISPATCH (main thread -> thread pool)
   executor.submit(client.query, system_prompt, user_message) --> Future

3. LLM EXECUTION (worker thread, asynchronous)
   client.query(system_prompt, user_message) --> response_str

4. RESPONSE HARVEST (main thread, next eligible tick)
   future.result() --> response_str
   LLMManager.parsers[agent.parser](response_str, blackboard) --> blackboard.data mutated

5. TACTICAL CONSUMPTION (main thread, every tick)
   BT/Utility system reads blackboard.data --> entity actions
```

---

## 5. API Design

### 5.1 LLMClient Protocol

The abstract interface that any LLM provider must implement. Uses Python's `Protocol` for structural typing (no inheritance required).

**Method**: `query`
- **Purpose**: Send a prompt to an LLM and return the response
- **Accepts**: system_prompt (str), user_message (str)
- **Returns**: response string
- **Behavior**: This is a **blocking** call. It will be invoked inside a thread pool worker. Implementations should make the HTTP request, wait for the response, and return the text content. Errors should be raised as exceptions.
- **Contract**: Implementations may raise any exception on failure. The system catches all exceptions and routes them through error handling.

### 5.2 LLMManager

Central registry following the same pattern as AIManager.

**Constructor**: Accepts an optional LLMConfig for rate limits and threading.

**Definition methods** (all register by name, overwrite on duplicate):

| Method | Parameters | Description |
|--------|-----------|-------------|
| `define_role` | name: str, text: str | Register a static role prompt fragment |
| `define_personality` | name: str, text: str | Register a static personality prompt fragment |
| `define_context` | name: str, fn: ContextFn | Register a context template callable |
| `define_parser` | name: str, fn: ParserFn | Register a response parser callable |
| `register_client` | client: LLMClient | Set the LLM client implementation |

**Lookup methods** (return None if not found):

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `role` | name: str | str or None | Look up a role definition |
| `personality` | name: str | str or None | Look up a personality definition |
| `context` | name: str | ContextFn or None | Look up a context template |
| `parser` | name: str | ParserFn or None | Look up a parser |

**Callback registration** (all optional, multiple allowed):

| Method | Callback Signature | Description |
|--------|-------------------|-------------|
| `on_query` | (eid: int, prompt_size: int, tick: int) -> None | Fired when a query is dispatched |
| `on_response` | (eid: int, latency: float, response_size: int, tick: int) -> None | Fired when a response is received |
| `on_error` | (eid: int, error_type: str, error_msg: str, tick: int) -> None | Fired on any failure |

**Prompt assembly** (used internally by the system):

| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `assemble_prompt` | world: World, eid: int, agent: LLMAgent | (str, str) or None | Returns (system_prompt, user_message) or None if definitions missing |

Prompt assembly concatenates `role_text + "\n\n" + personality_text` for the system prompt. The user message is the return value of the context function. If any referenced definition is missing, returns None and logs a warning.

### 5.3 System Factory

**`make_llm_system(manager: LLMManager) -> System`**

Returns a `(World, TickContext) -> None` callable that manages the full async query lifecycle. Internally creates the ThreadPoolExecutor.

The system performs these steps on each tick, in order:

1. **Harvest**: Check all pending futures for completion. For each completed future:
   - If successful: invoke the parser, write to Blackboard, fire `on_response`, clear `pending`, reset `consecutive_errors`
   - If failed: fire `on_error`, increment `consecutive_errors`, apply cooldown if threshold reached, clear `pending`

2. **Timeout**: Check all pending futures for timeout. Cancel timed-out futures and treat as errors.

3. **Dispatch**: Query eligible entities (sorted by priority descending), up to `max_queries_per_tick`:
   - Assemble prompt via `manager.assemble_prompt()`
   - Submit to thread pool
   - Set `agent.pending = True`, update `agent.last_query_tick`
   - Fire `on_query` callback

The system factory also returns or exposes a `shutdown()` mechanism for the ThreadPoolExecutor. One approach: the system callable has a `.shutdown()` attribute. Another: the manager owns the executor. Design decision deferred to implementation -- the spec requires that clean shutdown is possible.

### 5.4 Default JSON Parser

When `agent.parser` is empty string, the system uses a built-in default parser that:
1. Strips markdown code fences if present (` ```json ... ``` `)
2. Parses the response as JSON
3. Expects a top-level dict
4. Merges all key-value pairs into `blackboard.data` (shallow merge)
5. On parse failure: fires `on_error`, does not modify Blackboard

### 5.5 MockClient

A testing utility bundled with tick-llm.

**Constructor accepts**:
- `responses`: a dict mapping (system_prompt, user_message) tuples to response strings, OR a callable `(str, str) -> str` for dynamic responses
- `latency`: float, simulated delay in seconds (default 0.0 for instant response)
- `error_rate`: float 0.0--1.0, probability of raising an exception (default 0.0)
- `error_exception`: the exception type/instance to raise (default: a generic LLMError)

**Behavior**:
- Conforms to LLMClient protocol
- When `latency > 0`, sleeps for that duration before returning (simulates real-world delay in thread pool)
- When called with a key not in `responses` dict, returns `"{}"` (empty JSON object)
- Thread-safe (multiple workers may call concurrently)

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Metric | Target | Rationale |
|--------|--------|-----------|
| Prompt assembly | < 1ms per entity | Context functions should be lightweight reads |
| System overhead (no queries) | < 0.1ms per tick | Iterating entities + checking eligibility is cheap |
| Response harvest | < 1ms per response | Parsing + Blackboard write is fast |
| Thread pool footprint | 4 threads default | Enough for staggered queries, not overwhelming |

The system should add negligible overhead to the tick loop. The expensive work (LLM API calls) happens entirely in worker threads.

### 6.2 Reliability

- **No crashes from LLM failures**: All exceptions from client.query() are caught and routed through error handling. The tick loop never sees an unhandled exception from tick-llm.
- **Stale strategy is valid strategy**: Entities are always functional, even if their strategic layer is down. The BT/utility layer operates independently.
- **Timeout protection**: Queries exceeding `query_timeout` are cancelled to prevent thread pool exhaustion.
- **Cooldown prevents retry storms**: After `max_retries` failures, the entity backs off for `cooldown_ticks`, preventing rapid-fire retries against a down API.

### 6.3 Security

- tick-llm does not store API keys. Key management is the responsibility of the LLMClient implementation.
- Context template functions have read access to the entire World. Developers must ensure they do not leak sensitive data into prompts.
- Response parsers write to Blackboard. Developers must ensure parsers validate/sanitize LLM output before writing.

### 6.4 Observability

The three callback hooks (`on_query`, `on_response`, `on_error`) provide full visibility into:
- Query volume and rate
- Response latency distribution
- Error rates and types
- Per-entity query patterns

These can be wired to logging, metrics, or dashboards by the consumer.

### 6.5 Testability

- MockClient enables fully deterministic tests with no network calls
- Zero-latency mode means tests run at full speed
- Error simulation (configurable error rate) tests degradation paths
- All public methods are independently testable
- The system factory returns a plain callable -- easy to invoke in test harnesses

---

## 7. Integration Points

### 7.1 tick-ai (Blackboard Bridge)

This is the primary integration. The Blackboard component is the contract between strategic and tactical layers.

**Convention for Blackboard keys written by tick-llm parsers**:

Parsers should write under a `"strategy"` namespace in the Blackboard to avoid collisions with keys written by other systems:

- `blackboard.data["strategy"]` -- dict containing the LLM's parsed directives
- Example keys within strategy: `"goal"`, `"priority_target"`, `"stance"`, `"plan"`

BT conditions and utility considerations then read these keys:

- A BT condition "has_goal" checks `blackboard.data.get("strategy", {}).get("goal")`
- A utility consideration "aggression" reads `blackboard.data.get("strategy", {}).get("stance")`

This is a convention, not enforced by tick-llm. Developers choose their own key structure.

### 7.2 tick-ai (Behavior Trees)

No code changes needed in tick-ai. The BT system already reads Blackboard data. Developers define BT conditions and actions that read the strategy keys:

- **Condition**: "should_retreat" reads `blackboard.data["strategy"]["stance"] == "defensive"`
- **Action**: "move_to_target" reads `blackboard.data["strategy"]["priority_target"]`

The BT handles WHAT to do about the strategy. The LLM decides WHAT the strategy IS.

### 7.3 tick-ai (Utility AI)

Similarly, utility considerations can read Blackboard strategy keys to influence scoring. The LLM might write `"aggression": 0.8` to the Blackboard, which a consideration function reads and returns as a utility score.

### 7.4 tick-signal (Event Summaries)

Context template functions can subscribe to the SignalBus and accumulate recent events into a summary for the LLM. This is done in user code, not by tick-llm:

A developer creates a signal subscriber that collects events into a ring buffer. The context template function reads this buffer and formats it as natural language for the LLM prompt.

Example flow: SignalBus publishes "entity_damaged" events. A subscriber collects the last 10 events. The context function formats them as "You were attacked twice in the last 30 seconds by Entity 7."

### 7.5 tick-blueprint (Agent Templates)

Blueprints can include LLMAgent and Blackboard components in their recipes. A blueprint "llm_predator" might define:

- LLMAgent with role="predator", personality="aggressive", context="predator_ctx", query_interval=100
- Blackboard with initial strategy data
- BehaviorTree with tree_name="predator_bt"
- UtilityAgent with selector_name="predator_utility"

This makes it trivial to stamp out many LLM-driven entities from a template.

### 7.6 tick-colony

tick-colony may eventually integrate tick-llm into its dependency list and re-export it, following the pattern used for all other extensions. This is out of scope for v0.1.0.

### 7.7 System Ordering

The LLM system should run BEFORE the BT and utility systems in the engine's system list:

```
1. signal_system       -- flush events
2. llm_system          -- harvest responses, dispatch new queries
3. bt_system           -- read Blackboard (potentially freshly updated), run BTs
4. utility_system      -- read Blackboard, score actions
5. ability_system      -- execute abilities
6. physics_system      -- simulate physics
```

This ensures that freshly harvested LLM responses are available to the BT/utility systems in the same tick they arrive, minimizing the latency between LLM response and entity behavior change.

---

## 8. Error Handling

### 8.1 Error Categories

| Category | Source | Handling |
|----------|--------|----------|
| Network error | LLMClient raises ConnectionError, TimeoutError, etc. | Increment consecutive_errors, fire on_error, apply cooldown if threshold |
| API error | LLMClient raises provider-specific error (rate limit, auth, etc.) | Same as network error |
| Timeout | Future not complete after query_timeout seconds | Cancel future, treat as error |
| Parse error | ParserFn raises exception or JSON decode fails | Fire on_error, do not modify Blackboard, increment consecutive_errors |
| Missing definition | Role/personality/context name not found in manager | Skip query, fire on_error with "missing_definition" type, do not set pending |
| Missing Blackboard | Entity has LLMAgent but no Blackboard component | Skip entity entirely (warning-level, not error) |
| Missing client | No client registered on manager | Skip all queries, fire on_error once per tick with "no_client" type |

### 8.2 Retry and Cooldown State Machine

```
IDLE
  |-- query eligible --> PENDING

PENDING
  |-- response received --> parse
  |     |-- parse success --> IDLE (reset consecutive_errors)
  |     |-- parse failure --> ERROR_CHECK
  |-- timeout --> ERROR_CHECK
  |-- API error --> ERROR_CHECK

ERROR_CHECK
  |-- consecutive_errors < max_retries --> IDLE (can retry next interval)
  |-- consecutive_errors >= max_retries --> COOLDOWN

COOLDOWN
  |-- tick_number >= cooldown_until --> IDLE (reset consecutive_errors)
```

---

## 9. Example Usage (Conceptual)

### 9.1 Arena Predator with LLM Strategist

This example shows how all the pieces fit together for a predator entity in an arena simulation. The LLM provides high-level hunting strategy while behavior trees handle moment-to-moment actions.

**Setup flow**:

1. Create an `LLMManager` and register definitions:
   - Role "predator": describes the agent as a predator in an arena, lists available strategic actions (hunt, ambush, patrol, retreat, rest), specifies the expected JSON response format
   - Personality "cunning": describes preference for ambush tactics, patience, energy conservation
   - Context "predator_ctx": a function that reads the entity's position, health, energy, nearby entities, recent events, and current Blackboard strategy, then formats it as a natural-language situation report
   - Parser "strategy_parser": extracts `goal`, `priority_target`, `stance`, and `plan` from JSON response, writes to `blackboard.data["strategy"]`

2. Register an LLMClient implementation (e.g., wrapping the Anthropic SDK)

3. Create BT actions and conditions that read `blackboard.data["strategy"]`:
   - Condition "has_hunt_goal": checks if strategy goal is "hunt"
   - Condition "has_ambush_goal": checks if strategy goal is "ambush"
   - Condition "should_retreat": checks if strategy stance is "defensive"
   - Action "pursue_target": reads strategy.priority_target, moves toward it
   - Action "find_ambush_point": reads strategy.plan, positions for ambush

4. Assemble the engine:
   - `engine.add_system(make_llm_system(manager))` -- strategic layer
   - `engine.add_system(make_bt_system(ai_manager))` -- tactical layer
   - `engine.add_system(physics_system)` -- reactive layer

5. Spawn entity with components: LLMAgent, Blackboard, BehaviorTree, KinematicBody

**Runtime flow at tick 100**:

- Tick 100: LLM system sees entity is eligible (last query was tick 0, interval is 100). Assembles prompt from role + personality + current world state. Submits to thread pool. Sets pending=True.
- Ticks 101-105: BT continues running with stale strategy ("patrol"). Entity moves along patrol route.
- Tick 106: LLM responds with `{"goal": "ambush", "priority_target": 7, "stance": "aggressive", "plan": "hide near water source"}`. Parser writes to Blackboard. BT immediately switches behavior: moves to water source, waits.
- Ticks 107-199: BT executes ambush behavior based on Blackboard strategy.
- Tick 200: Next query eligible. New world state assembled. Cycle continues.

### 9.2 Context Template Example (Conceptual)

A context template function for the predator might produce output like:

```
Current tick: 2450
Your position: (12, 8)
Your health: 73/100
Your energy: 45/100

Nearby entities:
- Entity 7 (prey) at (15, 10), health 90/100, moving east
- Entity 12 (predator, ally) at (5, 5), health 40/100, idle

Recent events (last 50 ticks):
- Tick 2420: You attacked Entity 7, dealt 15 damage
- Tick 2425: Entity 7 fled north
- Tick 2440: Entity 12 was attacked by Entity 3

Current strategy: hunting Entity 7
Current stance: aggressive

What is your strategic plan? Respond with JSON.
```

### 9.3 Expected LLM Response Format

```json
{
  "goal": "ambush",
  "priority_target": 7,
  "stance": "aggressive",
  "plan": "Entity 7 is wounded and heading toward the water source at (18, 12). Move to (17, 11) and wait. Ally Entity 12 is low health, do not count on support.",
  "fallback_goal": "patrol"
}
```

---

## 10. Implementation Guidance

### 10.1 Module Structure

```
packages/tick-llm/
    pyproject.toml
    tick_llm/
        __init__.py          -- public API re-exports
        py.typed             -- PEP 561 marker
        components.py        -- LLMAgent dataclass
        config.py            -- LLMConfig dataclass
        client.py            -- LLMClient protocol, MockClient
        manager.py           -- LLMManager registry
        systems.py           -- make_llm_system() factory
        parsers.py           -- default JSON parser, utility helpers
    tests/
        __init__.py
        test_components.py
        test_manager.py
        test_client.py
        test_systems.py
        test_parsers.py
        test_integration.py
```

### 10.2 Package Configuration

- **name**: tick-llm
- **version**: 0.1.0
- **requires-python**: >=3.11
- **dependencies**: tick>=0.3.0, tick-ai>=0.1.0
- **sources**: tick = { workspace = true }, tick-ai = { workspace = true }
- **build**: hatchling, packages = ["tick_llm"]
- **pytest**: testpaths = ["tests"], addopts = ["--import-mode=importlib"]

### 10.3 Development Phases

**Phase 1: Foundation**
- LLMClient protocol and MockClient
- LLMAgent component and LLMConfig
- LLMManager with all define/lookup methods
- Prompt assembly logic
- Default JSON parser
- Unit tests for all of the above

**Phase 2: System**
- make_llm_system() factory
- ThreadPoolExecutor integration
- Future harvesting and dispatch logic
- Rate limiting (per-tick)
- Error handling and retry logic
- Integration tests with MockClient

**Phase 3: Observability and Polish**
- on_query / on_response / on_error callbacks
- Timeout detection and cancellation
- Cooldown state machine
- Per-second rate limiting (should-have)
- Priority-based dispatch ordering
- Edge case tests (despawned entities, detached components mid-query)

### 10.4 Testing Approach

**Unit tests**:
- LLMAgent component creation and field defaults
- LLMConfig validation
- LLMManager define/lookup/assemble_prompt
- Default JSON parser (valid JSON, malformed JSON, code-fenced JSON)
- MockClient conformance to protocol

**Integration tests**:
- Full lifecycle: define roles + spawn entity + step engine + harvest response
- Rate limiting: spawn N entities, verify only max_queries_per_tick fire per tick
- Error handling: MockClient with error_rate=1.0, verify retry + cooldown
- Timeout: MockClient with high latency + low query_timeout, verify cancellation
- Blackboard integration: verify parser writes appear in Blackboard, BT reads them
- Entity despawn during pending query: verify graceful cleanup
- Component detach during pending query: verify graceful cleanup

**Edge case tests**:
- Entity has LLMAgent but no Blackboard
- Referenced role/personality/context/parser name missing from manager
- Parser raises exception
- Client not registered
- Zero query_interval (query every tick)
- Multiple entities with same role/personality/context but different parsers

### 10.5 Type Checking

- mypy strict mode, matching ecosystem convention
- `py.typed` marker in package root
- All public functions fully annotated
- Protocol class for LLMClient enables structural subtyping
- TYPE_CHECKING imports for World and TickContext to avoid circular deps

---

## 11. Risks and Mitigations

### 11.1 Technical Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Thread pool exhaustion | High | Medium | Timeout + cancellation + configurable pool size + rate limiting |
| LLM response format drift | Medium | High | Parsers are user-defined, default parser is lenient, on_error reports parse failures |
| Entity despawned while query pending | Medium | Medium | Harvest step checks entity is alive before writing to Blackboard |
| Prompt too large for model context | Medium | Medium | Context functions are user-defined -- document best practice of limiting output size |
| Thread safety of World access | High | Low | Context functions run on main thread. Only client.query runs on worker thread. Worker never touches World. |
| Python GIL limits parallelism | Low | Certain | LLM calls are I/O-bound, not CPU-bound -- GIL is not a bottleneck. ThreadPoolExecutor is correct choice for I/O. |

### 11.2 Design Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Breaking "stdlib only" philosophy | Medium | tick-llm itself has zero external deps. External deps live in user's LLMClient implementation. Document this distinction clearly. |
| Blackboard key collisions | Low | Document "strategy" namespace convention. Not enforced -- user's responsibility. |
| Over-engineering for v0.1.0 | Medium | Strict MoSCoW prioritization. Batching, caching, streaming deferred to future versions. |

### 11.3 Open Questions

1. **Executor ownership**: Should the ThreadPoolExecutor be created by `make_llm_system()` (system owns it) or by `LLMManager` (manager owns it)? System ownership is simpler but makes shutdown less accessible. Manager ownership centralizes lifecycle but adds state to what should be a registry.

   *Recommendation*: System creates it, system callable exposes a `shutdown()` attribute. Document that callers should invoke `system.shutdown()` on engine stop or use the `engine.on_stop()` hook.

2. **Query cancellation on despawn**: When an entity is despawned while a query is pending, should the future be cancelled immediately (via `future.cancel()`)? Or should the response be silently discarded at harvest time?

   *Recommendation*: Discard at harvest time. `future.cancel()` only prevents execution if the future hasn't started -- it cannot interrupt a blocking HTTP call. Checking alive-ness at harvest is simpler and covers all cases.

3. **Multiple clients**: Should LLMManager support multiple named clients (e.g., "fast" for GPT-4o-mini, "smart" for Claude), selectable per agent? Or one client per manager?

   *Recommendation*: One client per manager for v0.1.0. Multiple managers can be created for multiple clients, each with its own system. This avoids complexity and follows the tick-engine pattern of simple registries.

4. **Snapshot/restore**: Should LLMAgent state (last_query_tick, consecutive_errors, cooldown_until) be serializable? In-flight futures cannot be serialized, but the agent metadata can.

   *Recommendation*: Yes, LLMAgent should be a plain dataclass and serialize normally via World.snapshot(). In-flight queries are lost on restore (pending resets to False). Document this behavior.

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **Strategic layer** | LLM-driven high-level reasoning (tick-llm). Operates every N ticks. |
| **Tactical layer** | Behavior tree and utility AI decision-making (tick-ai). Operates every tick. |
| **Reactive layer** | Physics, FSM, and other immediate-response systems. Operates every tick. |
| **Role** | Static prompt text defining WHAT an agent IS and what actions are available. |
| **Personality** | Static prompt text defining HOW an agent tends to behave. |
| **Context template** | A function that reads world state and formats it as a prompt section. |
| **Parser** | A function that extracts structured data from an LLM response and writes it to a Blackboard. |
| **Blackboard** | Per-entity key-value store (from tick-ai) that bridges strategic and tactical layers. |
| **Query interval** | Minimum ticks between LLM queries for an entity. |
| **Cooldown** | Period of forced inactivity after repeated query failures. |
| **Stale strategy** | The Blackboard's current content, which remains valid while a new query is pending. |

---

## Appendix A: Prompt Assembly Detail

The system prompt is assembled from two components separated by a double newline:

```
{role_text}

{personality_text}
```

The user message is the return value of the context template function:

```
{context_fn(world, eid)}
```

These map directly to LLM API concepts:
- System prompt = "system" message role (persistent instructions)
- User message = "user" message role (current situation / question)

The LLM's response is the "assistant" message, which is passed to the parser.

This two-message structure (system + user) is universal across LLM providers (OpenAI, Anthropic, local models) and maps cleanly to the LLMClient protocol's `query(system_prompt, user_message)` signature.

---

## Appendix B: Comparison with Existing tick-ai Patterns

| Aspect | tick-ai (AIManager) | tick-llm (LLMManager) |
|--------|--------------------|-----------------------|
| Definitions | Trees, actions, conditions, considerations | Roles, personalities, contexts, parsers |
| Component | BehaviorTree, UtilityAgent | LLMAgent |
| System | make_bt_system, make_utility_system | make_llm_system |
| Execution | Synchronous, every tick | Async (ThreadPoolExecutor), every N ticks |
| Data bridge | Blackboard (read) | Blackboard (write) |
| Callbacks | on_status, on_select | on_query, on_response, on_error |
| External deps | None | None (client protocol; user provides impl) |
| Snapshot | Components only (re-register defs) | Components only (re-register defs, lose in-flight) |

The patterns are intentionally parallel. Developers familiar with tick-ai will find tick-llm's API immediately recognizable.

---

## Appendix C: Future Directions (Post v0.1.0)

**v0.2.0 candidates**:
- **Batching**: Collect multiple entities' context into a single multi-entity prompt. Reduces API calls but increases complexity of parsing.
- **Context hashing**: Hash the assembled prompt and skip queries when the context hasn't changed since the last response. Saves API calls for entities in stable situations.
- **Conversation history**: Maintain a sliding window of past (context, response) pairs per entity. Enables the LLM to reference its own prior reasoning.
- **Token budget**: Estimate prompt token count before dispatch. Trim context if it would exceed the model's context window.

**v0.3.0 candidates**:
- **Streaming**: Process partial responses as they arrive, enabling the parser to begin writing to Blackboard before the full response is complete.
- **Multi-client routing**: LLMAgent specifies which named client to use. Fast/cheap models for routine queries, expensive models for critical decisions.
- **Built-in providers**: Optional sub-packages (tick-llm-openai, tick-llm-anthropic) with ready-made LLMClient implementations.
