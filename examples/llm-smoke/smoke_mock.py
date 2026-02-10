"""Frontier Outpost — tick-llm smoke test with MockClient.

Three LLM agents (Scout, Commander, Trader) making strategic decisions
over ~100 ticks using MockClient with simulated latency and error rates.

Run:
    uv run python smoke_mock.py
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from tick import Engine
from tick_ai.components import Blackboard
from tick_llm import (
    LLMAgent,
    LLMConfig,
    LLMManager,
    MockClient,
    make_llm_system,
)

# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@dataclass
class Name:
    """Display name for an entity."""
    value: str


@dataclass
class Health:
    """Entity health points."""
    current: int = 100
    maximum: int = 100


@dataclass
class Supplies:
    """Outpost supply levels."""
    food: int = 50
    water: int = 50
    ammo: int = 30


# ---------------------------------------------------------------------------
# Mock response generator
# ---------------------------------------------------------------------------

def _mock_responses(system_prompt: str, user_message: str) -> str:
    """Generate context-aware mock responses based on the user message."""
    msg = user_message.lower()

    if "scout" in system_prompt.lower() or "reconnaissance" in msg:
        if "threat" in msg or "danger" in msg:
            return json.dumps({
                "action": "retreat",
                "threat_level": "high",
                "report": "Hostile movement detected to the north.",
            })
        if "low" in msg:
            return json.dumps({
                "action": "explore",
                "direction": "east",
                "report": "Eastern ridge looks clear for scouting.",
            })
        return json.dumps({
            "action": "patrol",
            "direction": "north",
            "report": "Perimeter secure. Minor tracks spotted.",
        })

    if "commander" in system_prompt.lower() or "strategic" in system_prompt.lower():
        if "hostile" in msg or "threat" in msg:
            return json.dumps({
                "action": "defend",
                "priority": "fortify_north",
                "orders": "All units to defensive positions.",
            })
        if "clear" in msg or "secure" in msg:
            return json.dumps({
                "action": "expand",
                "priority": "send_scouts_east",
                "orders": "Scout team, push east. Trader, restock supplies.",
            })
        return json.dumps({
            "action": "hold",
            "priority": "maintain_readiness",
            "orders": "Continue standard operations.",
        })

    if "trader" in system_prompt.lower() or "trade" in msg:
        if "low" in msg or "shortage" in msg:
            return json.dumps({
                "action": "buy",
                "resource": "food",
                "quantity": 20,
                "note": "Prioritizing food resupply.",
            })
        return json.dumps({
            "action": "sell",
            "resource": "ammo",
            "quantity": 5,
            "note": "Trading surplus ammunition for profit.",
        })

    return json.dumps({"action": "wait", "note": "No specific orders."})


# ---------------------------------------------------------------------------
# Context functions (read actual world state)
# ---------------------------------------------------------------------------

def _scout_context(world: "tick.World", eid: int) -> str:
    """Build context from scout's perspective — reads own health + supplies."""
    parts = [f"Tick report for reconnaissance unit."]

    if world.has(eid, Health):
        h = world.get(eid, Health)
        parts.append(f"Health: {h.current}/{h.maximum}.")

    # Read outpost supplies from any entity that has them
    for sid, (supplies,) in world.query(Supplies):
        parts.append(
            f"Outpost supplies — food: {supplies.food}, "
            f"water: {supplies.water}, ammo: {supplies.ammo}."
        )
        if supplies.food < 20 or supplies.water < 20:
            parts.append("WARNING: Supply levels critically low.")
        break

    # Check own blackboard for recent activity
    if world.has(eid, Blackboard):
        bb = world.get(eid, Blackboard)
        strategy = bb.data.get("strategy", {})
        if strategy:
            parts.append(f"Previous decision: {strategy.get('action', 'none')}.")
            report = strategy.get("report", "")
            if "hostile" in report.lower() or "threat" in report.lower():
                parts.append("Threat detected in previous report — danger level elevated.")

    return "\n".join(parts)


def _commander_context(world: "tick.World", eid: int) -> str:
    """Build context from commander's perspective — aggregates all reports."""
    parts = ["Strategic briefing for outpost commander."]

    # Aggregate scout reports from all agents' blackboards
    for aid, (bb,) in world.query(Blackboard):
        if aid == eid:
            continue
        strategy = bb.data.get("strategy", {})
        if not strategy:
            continue
        # Get the agent's name if available
        name = "Unknown"
        if world.has(aid, Name):
            name = world.get(aid, Name).value
        action = strategy.get("action", "unknown")
        report = strategy.get("report", strategy.get("note", ""))
        parts.append(f"Agent '{name}' reports: action={action}, detail='{report}'.")

    # Outpost status
    for sid, (supplies,) in world.query(Supplies):
        parts.append(
            f"Outpost supplies — food: {supplies.food}, "
            f"water: {supplies.water}, ammo: {supplies.ammo}."
        )
        break

    if len(parts) == 1:
        parts.append("No field reports available yet.")

    return "\n".join(parts)


def _trader_context(world: "tick.World", eid: int) -> str:
    """Build context from trader's perspective — focuses on resources."""
    parts = ["Trade assessment for outpost quartermaster."]

    for sid, (supplies,) in world.query(Supplies):
        parts.append(
            f"Current stock — food: {supplies.food}, "
            f"water: {supplies.water}, ammo: {supplies.ammo}."
        )
        if supplies.food < 20:
            parts.append("Food shortage — consider purchasing.")
        if supplies.ammo > 40:
            parts.append("Ammo surplus — opportunity to sell.")
        break

    # Check commander orders
    for aid, (agent, bb) in world.query(LLMAgent, Blackboard):
        if agent.role == "commander":
            strategy = bb.data.get("strategy", {})
            orders = strategy.get("orders", "")
            if orders:
                parts.append(f"Commander's orders: '{orders}'.")
            break

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Supply drain system (makes the scenario dynamic)
# ---------------------------------------------------------------------------

def _supply_drain_system(world: "tick.World", ctx: "tick.clock.TickContext") -> None:
    """Drain supplies to create pressure on the agents."""
    if ctx.tick_number % 5 != 0:
        return
    for eid, (supplies,) in world.query(Supplies):
        supplies.food = max(0, supplies.food - 3)
        supplies.water = max(0, supplies.water - 2)


# ---------------------------------------------------------------------------
# Tracking and display
# ---------------------------------------------------------------------------

class SmokeStats:
    """Collects stats from observable callbacks."""

    def __init__(self) -> None:
        self.queries: int = 0
        self.responses: int = 0
        self.errors: int = 0
        self.total_latency: float = 0.0
        self.entity_names: dict[int, str] = {}

    def bind(self, manager: LLMManager, world: object) -> None:
        manager.on_query(self._on_query)
        manager.on_response(self._on_response)
        manager.on_error(self._on_error)

    def _name(self, eid: int) -> str:
        return self.entity_names.get(eid, f"eid={eid}")

    def _on_query(self, eid: int, prompt_size: int, tick: int) -> None:
        self.queries += 1
        print(f"  [T{tick:03d}] QUERY   {self._name(eid):12s}  ({prompt_size} chars)")

    def _on_response(self, eid: int, latency: float, resp_size: int, tick: int) -> None:
        self.responses += 1
        self.total_latency += latency
        print(
            f"  [T{tick:03d}] RESPOND {self._name(eid):12s}  "
            f"({resp_size} chars, {latency:.3f}s)"
        )

    def _on_error(self, eid: int, error_type: str, error_msg: str, tick: int) -> None:
        self.errors += 1
        print(
            f"  [T{tick:03d}] ERROR   {self._name(eid):12s}  "
            f"[{error_type}] {error_msg}"
        )

    def summary(self) -> str:
        avg_lat = (
            self.total_latency / self.responses if self.responses > 0 else 0.0
        )
        return (
            f"\n{'='*60}\n"
            f"  SMOKE TEST SUMMARY\n"
            f"{'='*60}\n"
            f"  Queries dispatched : {self.queries}\n"
            f"  Responses received : {self.responses}\n"
            f"  Errors encountered : {self.errors}\n"
            f"  Avg latency        : {avg_lat:.3f}s\n"
            f"{'='*60}"
        )


def _dump_blackboards(world: object, stats: SmokeStats, tick: int) -> None:
    """Print all agents' blackboard strategy data."""
    print(f"\n  --- Blackboard dump at tick {tick} ---")
    for eid, (bb,) in world.query(Blackboard):
        name = stats.entity_names.get(eid, f"eid={eid}")
        strategy = bb.data.get("strategy", {})
        if strategy:
            print(f"    {name}: {json.dumps(strategy, indent=6)}")
        else:
            print(f"    {name}: (empty)")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  FRONTIER OUTPOST — tick-llm Smoke Test (MockClient)")
    print("=" * 60)
    print()

    # Engine at 10 TPS
    engine = Engine(tps=10, seed=42)
    world = engine.world

    # Register components
    world.register_component(Name)
    world.register_component(Health)
    world.register_component(Supplies)
    world.register_component(LLMAgent)
    world.register_component(Blackboard)

    # --- LLM Manager setup ---
    config = LLMConfig(
        max_queries_per_tick=3,
        max_queries_per_second=10,
        thread_pool_size=4,
        query_timeout=5.0,
    )
    manager = LLMManager(config)

    # Roles
    manager.define_role("scout", (
        "You are a frontier scout for a remote outpost. "
        "Your job is reconnaissance — patrol, detect threats, and report findings. "
        "Respond with a JSON object: {\"action\": ..., \"report\": ...}"
    ))
    manager.define_role("commander", (
        "You are the commanding officer of a frontier outpost. "
        "You receive field reports and issue strategic orders. "
        "Respond with a JSON object: {\"action\": ..., \"priority\": ..., \"orders\": ...}"
    ))
    manager.define_role("trader", (
        "You are the quartermaster and trader for a frontier outpost. "
        "You manage supplies and negotiate trades. "
        "Respond with a JSON object: {\"action\": ..., \"resource\": ..., \"quantity\": ...}"
    ))

    # Personalities
    manager.define_personality("cautious", (
        "You are careful and methodical. You prefer safe options and always "
        "consider worst-case scenarios before acting."
    ))
    manager.define_personality("strategic", (
        "You think long-term and weigh costs vs benefits. You coordinate "
        "multiple units and plan several steps ahead."
    ))
    manager.define_personality("opportunistic", (
        "You look for deals and advantages. You act quickly when you see "
        "profit potential and always keep one eye on the bottom line."
    ))

    # Contexts
    manager.define_context("scout_ctx", _scout_context)
    manager.define_context("commander_ctx", _commander_context)
    manager.define_context("trader_ctx", _trader_context)

    # MockClient with 50ms latency, callable responses
    scout_client = MockClient(
        responses=_mock_responses,
        latency=0.05,
        error_rate=0.10,
    )
    manager.register_client(scout_client)

    # Stats tracker
    stats = SmokeStats()
    stats.bind(manager, world)

    # --- Spawn entities ---
    # Outpost (holds supplies)
    outpost = world.spawn()
    world.attach(outpost, Name(value="Outpost"))
    world.attach(outpost, Supplies(food=50, water=50, ammo=30))

    # Scout
    scout = world.spawn()
    world.attach(scout, Name(value="Scout"))
    world.attach(scout, Health(current=80, maximum=100))
    world.attach(scout, Blackboard(data={}))
    world.attach(scout, LLMAgent(
        role="scout",
        personality="cautious",
        context="scout_ctx",
        query_interval=5,
        priority=0,
        max_retries=3,
        cooldown_ticks=10,
    ))
    stats.entity_names[scout] = "Scout"

    # Commander
    commander = world.spawn()
    world.attach(commander, Name(value="Commander"))
    world.attach(commander, Health(current=100, maximum=100))
    world.attach(commander, Blackboard(data={}))
    world.attach(commander, LLMAgent(
        role="commander",
        personality="strategic",
        context="commander_ctx",
        query_interval=10,
        priority=5,
        max_retries=3,
        cooldown_ticks=20,
    ))
    stats.entity_names[commander] = "Commander"

    # Trader
    trader = world.spawn()
    world.attach(trader, Name(value="Trader"))
    world.attach(trader, Blackboard(data={}))
    world.attach(trader, LLMAgent(
        role="trader",
        personality="opportunistic",
        context="trader_ctx",
        query_interval=15,
        priority=0,
        max_retries=3,
        cooldown_ticks=15,
    ))
    stats.entity_names[trader] = "Trader"

    # --- Systems ---
    llm_system = make_llm_system(manager)
    engine.add_system(llm_system)
    engine.add_system(_supply_drain_system)

    # --- Run ---
    total_ticks = 100
    print(f"  Running {total_ticks} ticks at {engine.clock.tps} TPS...\n")

    for tick_num in range(1, total_ticks + 1):
        engine.step()

        # Allow async futures to complete (must exceed MockClient latency)
        time.sleep(0.06)

        # Blackboard dump every 20 ticks
        if tick_num % 20 == 0:
            _dump_blackboards(world, stats, tick_num)

    # Final dump (skip if already printed by periodic dump)
    if total_ticks % 20 != 0:
        _dump_blackboards(world, stats, total_ticks)

    # Shutdown
    llm_system.shutdown()

    # Summary
    print(stats.summary())

    # Validate expectations
    print("\n  Validation:")
    ok = True
    if stats.queries == 0:
        print("    FAIL: No queries were dispatched!")
        ok = False
    else:
        print(f"    OK: {stats.queries} queries dispatched")

    if stats.responses == 0:
        print("    FAIL: No responses received!")
        ok = False
    else:
        print(f"    OK: {stats.responses} responses received")

    if stats.errors == 0:
        print("    NOTE: No errors (scout error_rate=10% — might happen)")
    else:
        print(f"    OK: {stats.errors} errors handled (expected with 10% error rate)")

    # Check that at least some blackboards have strategy data
    agents_with_data = 0
    for eid, (bb,) in world.query(Blackboard):
        if bb.data.get("strategy"):
            agents_with_data += 1
    if agents_with_data == 0:
        print("    FAIL: No agents have strategy data in blackboards!")
        ok = False
    else:
        print(f"    OK: {agents_with_data} agents have strategy data")

    print()
    if ok:
        print("  SMOKE TEST PASSED")
    else:
        print("  SMOKE TEST FAILED")
    print()


if __name__ == "__main__":
    main()
