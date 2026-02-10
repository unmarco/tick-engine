"""Frontier Outpost — tick-llm smoke test with real LLM via LM Studio.

Same theme as smoke_mock.py but uses actual LLM inference through
LM Studio's local API (OpenAI and Anthropic-compatible endpoints).

Features episodic memory: agents remember past decisions, track outcomes,
and cross-reference what other agents said over time.

Requires LM Studio running with a loaded model.

Run:
    uv run python smoke_lmstudio.py
    uv run python smoke_lmstudio.py --model my-model --ticks 20
    uv run python smoke_lmstudio.py --endpoint openai --ticks 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from dataclasses import dataclass
from typing import Any

from tick import Engine
from tick_ai.components import Blackboard
from tick_llm import (
    LLMAgent,
    LLMConfig,
    LLMManager,
    make_llm_system,
    strip_code_fences,
)

from clients import LMStudioAnthropicClient, LMStudioOpenAIClient, list_models

MEMORY_DEPTH = 8  # how many past decisions each agent remembers


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@dataclass
class Name:
    """Display name for an entity."""
    value: str


@dataclass
class Supplies:
    """Outpost supply levels."""
    food: int = 50
    water: int = 40
    ammo: int = 30


# ---------------------------------------------------------------------------
# Memory-aware parser
# ---------------------------------------------------------------------------

def memory_parser(response: str, bb: Blackboard) -> None:
    """Parse LLM response and append to decision log.

    Maintains:
      bb.data["strategy"]  — latest decision (for other agents to read)
      bb.data["log"]       — list of past decisions with tick stamps
    """
    cleaned = strip_code_fences(response)
    parsed: Any = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")

    # Current strategy (for cross-agent reads)
    bb.data["strategy"] = parsed

    # Append to episodic log
    tick = bb.data.get("_tick", 0)
    entry: dict[str, Any] = {"tick": tick, **parsed}
    log: list[dict[str, Any]] = bb.data.setdefault("log", [])
    log.append(entry)

    # Evict oldest entries beyond memory depth
    if len(log) > MEMORY_DEPTH:
        bb.data["log"] = log[-MEMORY_DEPTH:]


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def _tick_stamp_system(world: Any, ctx: Any) -> None:
    """Stamp current tick number onto every blackboard.

    Runs before the LLM system so the parser can read it.
    """
    for eid, (bb,) in world.query(Blackboard):
        bb.data["_tick"] = ctx.tick_number


def _supply_snapshot_system(world: Any, ctx: Any) -> None:
    """Record supply levels alongside each new log entry.

    Runs after the LLM system so harvested responses already exist.
    Annotates the latest log entry with a supply snapshot and computes
    deltas vs the previous entry.
    """
    # Get current supply levels
    supplies = None
    for _sid, (s,) in world.query(Supplies):
        supplies = {"food": s.food, "water": s.water, "ammo": s.ammo}
        break
    if supplies is None:
        return

    for eid, (bb,) in world.query(Blackboard):
        log: list[dict[str, Any]] = bb.data.get("log", [])
        if not log:
            continue

        latest = log[-1]
        # Only annotate once (skip if already has supplies)
        if "supplies" in latest:
            continue

        latest["supplies"] = supplies

        # Compute deltas vs previous entry
        if len(log) >= 2:
            prev = log[-2]
            prev_sup = prev.get("supplies")
            if prev_sup:
                latest["delta"] = {
                    k: supplies[k] - prev_sup[k] for k in supplies
                }


def _supply_drain_system(world: Any, ctx: Any) -> None:
    """Drain supplies to create pressure on the agents."""
    if ctx.tick_number % 5 != 0:
        return
    for eid, (supplies,) in world.query(Supplies):
        supplies.food = max(0, supplies.food - 2)
        supplies.water = max(0, supplies.water - 1)


# ---------------------------------------------------------------------------
# Context functions with memory
# ---------------------------------------------------------------------------

def _format_log_entry(entry: dict[str, Any]) -> str:
    """Format one log entry as a human-readable line."""
    tick = entry.get("tick", "?")
    action = entry.get("action", "?")
    report = entry.get("report", entry.get("orders", entry.get("note", "")))
    sup = entry.get("supplies")
    delta = entry.get("delta")

    line = f"  T{tick}: {action}"
    if report:
        line += f' — "{report}"'
    if sup:
        line += f" [food={sup['food']}, water={sup['water']}, ammo={sup['ammo']}]"
    if delta:
        changes = [f"{k}{d:+d}" for k, d in delta.items() if d != 0]
        if changes:
            line += f" ({', '.join(changes)})"
    return line


def _analyze_history(log: list[dict[str, Any]]) -> list[str]:
    """Derive editorial observations from the decision log."""
    if len(log) < 2:
        return []

    observations: list[str] = []

    # Detect repeated actions
    actions = [e.get("action") for e in log[-4:]]
    if len(set(actions)) == 1 and len(actions) >= 3:
        observations.append(
            f"You have chosen '{actions[0]}' for {len(actions)} consecutive decisions."
        )

    # Detect oscillation (A-B-A-B pattern)
    if len(actions) >= 4:
        if actions[-1] == actions[-3] and actions[-2] == actions[-4] and actions[-1] != actions[-2]:
            observations.append(
                f"You are oscillating between '{actions[-1]}' and '{actions[-2]}'. "
                "Consider a different approach."
            )

    # Track supply trend
    deltas = [e.get("delta", {}) for e in log[-3:] if e.get("delta")]
    if deltas:
        food_deltas = [d.get("food", 0) for d in deltas]
        if all(d < 0 for d in food_deltas):
            total = sum(food_deltas)
            observations.append(
                f"Food has dropped by {abs(total)} over your last {len(food_deltas)} decisions. "
                "Your actions have not stopped the decline."
            )
        elif all(d == 0 for d in food_deltas):
            observations.append("Supply levels have stabilized.")

    return observations


def _scout_context(world: Any, eid: int) -> str:
    """Build scout context with episodic memory."""
    parts = ["Reconnaissance report request."]

    # Current world state
    for _sid, (supplies,) in world.query(Supplies):
        parts.append(
            f"Outpost supplies — food: {supplies.food}, "
            f"water: {supplies.water}, ammo: {supplies.ammo}."
        )
        if supplies.food < 10 or supplies.water < 10:
            parts.append("CRITICAL: Supplies near zero.")
        elif supplies.food < 20 or supplies.water < 20:
            parts.append("WARNING: Supply levels critically low.")
        break

    # Decision history
    if world.has(eid, Blackboard):
        bb = world.get(eid, Blackboard)
        log = bb.data.get("log", [])
        if log:
            parts.append(f"\nYour decision history (last {len(log)}):")
            for entry in log:
                parts.append(_format_log_entry(entry))

            # Editorial observations
            obs = _analyze_history(log)
            if obs:
                parts.append("\nObservations:")
                for o in obs:
                    parts.append(f"  * {o}")

        # What the commander last ordered
        for aid, (agent, abb) in world.query(LLMAgent, Blackboard):
            if agent.role == "commander":
                cmd_strategy = abb.data.get("strategy", {})
                orders = cmd_strategy.get("orders", "")
                if orders:
                    parts.append(f'\nCommander\'s latest orders: "{orders}"')
                break

    parts.append(
        "\nAssess the situation considering your past decisions and their outcomes. "
        "Respond ONLY with a JSON object, no other text."
    )
    return "\n".join(parts)


def _commander_context(world: Any, eid: int) -> str:
    """Build commander context with cross-agent memory."""
    parts = ["Strategic briefing for outpost commander."]

    # Current supplies
    for _sid, (supplies,) in world.query(Supplies):
        parts.append(
            f"Outpost supplies — food: {supplies.food}, "
            f"water: {supplies.water}, ammo: {supplies.ammo}."
        )
        break

    # Cross-agent reports with history
    has_reports = False
    for aid, (agent, abb) in world.query(LLMAgent, Blackboard):
        if aid == eid:
            continue
        name = "Unknown"
        if world.has(aid, Name):
            name = world.get(aid, Name).value

        log = abb.data.get("log", [])
        if log:
            has_reports = True
            parts.append(f"\n{name}'s recent reports:")
            for entry in log[-4:]:
                parts.append(_format_log_entry(entry))

    if not has_reports:
        parts.append("No field reports available yet.")

    # Own decision history
    if world.has(eid, Blackboard):
        bb = world.get(eid, Blackboard)
        log = bb.data.get("log", [])
        if log:
            parts.append(f"\nYour previous orders (last {len(log)}):")
            for entry in log:
                parts.append(_format_log_entry(entry))

            # Editorial observations
            obs = _analyze_history(log)
            if obs:
                parts.append("\nObservations about your command decisions:")
                for o in obs:
                    parts.append(f"  * {o}")

    parts.append(
        "\nIssue strategic orders considering the full history of reports and outcomes. "
        "Respond ONLY with a JSON object, no other text."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

class SmokeStats:
    def __init__(self) -> None:
        self.queries: int = 0
        self.responses: int = 0
        self.errors: int = 0
        self.total_latency: float = 0.0
        self.entity_names: dict[int, str] = {}

    def bind(self, manager: LLMManager) -> None:
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
            f"({resp_size} chars, {latency:.1f}s)"
        )

    def _on_error(self, eid: int, error_type: str, error_msg: str, tick: int) -> None:
        self.errors += 1
        print(
            f"  [T{tick:03d}] ERROR   {self._name(eid):12s}  "
            f"[{error_type}] {error_msg}"
        )

    def summary(self) -> str:
        avg_lat = self.total_latency / self.responses if self.responses > 0 else 0.0
        return (
            f"\n{'='*60}\n"
            f"  RESULTS\n"
            f"{'='*60}\n"
            f"  Queries dispatched : {self.queries}\n"
            f"  Responses received : {self.responses}\n"
            f"  Errors encountered : {self.errors}\n"
            f"  Avg latency        : {avg_lat:.1f}s\n"
            f"{'='*60}"
        )


def _dump_blackboards(world: Any, stats: SmokeStats, tick: int) -> None:
    print(f"\n  --- Blackboard dump at tick {tick} ---")
    for eid, (bb,) in world.query(Blackboard):
        name = stats.entity_names.get(eid, f"eid={eid}")
        strategy = bb.data.get("strategy", {})
        log = bb.data.get("log", [])
        print(f"    {name} (decisions: {len(log)}):")
        if strategy:
            print(f"      latest: {json.dumps(strategy)}")
        else:
            print(f"      latest: (none yet)")
        if log and len(log) > 1:
            print(f"      history: {' -> '.join(e.get('action', '?') for e in log)}")
    print()


# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------

def _check_connectivity(base_url: str) -> list[dict[str, str]]:
    """Verify LM Studio is reachable and return available models."""
    try:
        models = list_models(base_url)
    except (urllib.error.URLError, OSError) as exc:
        print(f"\n  ERROR: Cannot reach LM Studio at {base_url}")
        print(f"         {exc}")
        print("\n  Make sure LM Studio is running with a model loaded.")
        print("  Default URL: http://localhost:1234\n")
        sys.exit(1)
    return models


def _resolve_model(
    models: list[dict[str, str]], requested: str | None,
) -> str:
    """Auto-detect or validate the model name."""
    if requested:
        return requested

    if len(models) == 0:
        print("\n  ERROR: No models loaded in LM Studio.")
        print("  Load a model and try again.\n")
        sys.exit(1)

    if len(models) == 1:
        model_id = models[0]["id"]
        print(f"  Auto-detected model: {model_id}")
        return model_id

    print("\n  Multiple models available — please specify one with --model:")
    for m in models:
        print(f"    - {m['id']}")
    print()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Phase runner
# ---------------------------------------------------------------------------

def run_phase(
    phase_name: str,
    client: object,
    model: str,
    ticks: int,
) -> SmokeStats:
    """Run a single test phase with the given client."""
    print(f"\n{'='*60}")
    print(f"  PHASE: {phase_name} (model: {model})")
    print(f"  Memory depth: {MEMORY_DEPTH} decisions")
    print(f"{'='*60}\n")

    engine = Engine(tps=10, seed=42)
    world = engine.world

    world.register_component(Name)
    world.register_component(Supplies)
    world.register_component(LLMAgent)
    world.register_component(Blackboard)

    config = LLMConfig(
        max_queries_per_tick=1,
        max_queries_per_second=2,
        thread_pool_size=2,
        query_timeout=60.0,
    )
    manager = LLMManager(config)

    # Roles with explicit JSON schema instructions for real LLMs
    manager.define_role("scout", (
        "You are a frontier scout for a remote outpost. "
        "Your job is reconnaissance — patrol, detect threats, and report. "
        "You will be shown your past decisions and their outcomes. "
        "Learn from what worked and what didn't. Avoid repeating failed strategies. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"action": "<patrol|explore|retreat|forage>", '
        '"threat_level": "<none|low|medium|high>", '
        '"report": "<brief situation report referencing past outcomes>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))
    manager.define_role("commander", (
        "You are the commanding officer of a frontier outpost. "
        "You receive field reports and issue strategic orders. "
        "You will be shown the full history of your orders and your agents' reports. "
        "Notice patterns — if a strategy isn't working, change course. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"action": "<hold|defend|expand|retreat|forage>", '
        '"priority": "<string describing top priority>", '
        '"orders": "<orders referencing specific past events or agent reports>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))

    manager.define_personality("cautious", (
        "You are careful and methodical. You track what you've tried before "
        "and avoid repeating actions that didn't improve the situation."
    ))
    manager.define_personality("strategic", (
        "You think long-term and notice trends. When supply deltas are negative, "
        "you adjust strategy. You reference your agents' past reports by tick number."
    ))

    manager.define_context("scout_ctx", _scout_context)
    manager.define_context("commander_ctx", _commander_context)
    manager.define_parser("memory", memory_parser)

    manager.register_client(client)

    stats = SmokeStats()
    stats.bind(manager)

    # Spawn outpost
    outpost = world.spawn()
    world.attach(outpost, Name(value="Outpost"))
    world.attach(outpost, Supplies(food=50, water=40, ammo=30))

    # Scout
    scout = world.spawn()
    world.attach(scout, Name(value="Scout"))
    world.attach(scout, Blackboard(data={}))
    world.attach(scout, LLMAgent(
        role="scout",
        personality="cautious",
        context="scout_ctx",
        parser="memory",
        query_interval=10,
        priority=0,
        max_retries=2,
        cooldown_ticks=10,
    ))
    stats.entity_names[scout] = "Scout"

    # Commander
    commander = world.spawn()
    world.attach(commander, Name(value="Commander"))
    world.attach(commander, Blackboard(data={}))
    world.attach(commander, LLMAgent(
        role="commander",
        personality="strategic",
        context="commander_ctx",
        parser="memory",
        query_interval=10,
        priority=5,
        max_retries=2,
        cooldown_ticks=10,
    ))
    stats.entity_names[commander] = "Commander"

    # Systems — order matters:
    # 1. tick_stamp (before LLM, so parser has current tick)
    # 2. llm_system (dispatch + harvest)
    # 3. supply_snapshot (after LLM, annotates new log entries)
    # 4. supply_drain (world state changes)
    engine.add_system(_tick_stamp_system)
    llm_system = make_llm_system(manager)
    engine.add_system(llm_system)
    engine.add_system(_supply_snapshot_system)
    engine.add_system(_supply_drain_system)

    print(f"  Running {ticks} ticks (0.5s between steps for LLM latency)...\n")

    for tick_num in range(1, ticks + 1):
        engine.step()
        # Slower pacing for real LLM inference
        time.sleep(0.5)

        if tick_num % 10 == 0 or tick_num == ticks:
            _dump_blackboards(world, stats, tick_num)

    llm_system.shutdown()

    print(stats.summary())

    # Print full memory state
    print("\n  Final memory state:")
    for eid, (bb,) in world.query(Blackboard):
        name = stats.entity_names.get(eid, f"eid={eid}")
        log = bb.data.get("log", [])
        print(f"\n    {name} — {len(log)} memories:")
        for entry in log:
            print(f"    {_format_log_entry(entry)}")
    print()

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="tick-llm smoke test with LM Studio (with episodic memory)",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model identifier (auto-detects if omitted)",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:1234",
        help="LM Studio base URL (default: http://localhost:1234)",
    )
    parser.add_argument(
        "--ticks", type=int, default=30,
        help="Number of ticks to run per phase (default: 30)",
    )
    parser.add_argument(
        "--endpoint", choices=["openai", "anthropic", "both"],
        default="anthropic",
        help="Which endpoint to test (default: anthropic)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  FRONTIER OUTPOST — tick-llm Smoke Test (LM Studio)")
    print("  with Episodic Memory")
    print("=" * 60)

    # Connectivity check
    print(f"\n  Checking LM Studio at {args.base_url}...")
    models = _check_connectivity(args.base_url)
    model = _resolve_model(models, args.model)
    print(f"  Using model: {model}")
    print(f"  Endpoint(s): {args.endpoint}")
    print(f"  Ticks per phase: {args.ticks}")

    results: list[tuple[str, SmokeStats]] = []

    if args.endpoint in ("openai", "both"):
        client = LMStudioOpenAIClient(
            model=model,
            base_url=args.base_url,
            temperature=0.7,
            max_tokens=256,
        )
        stats = run_phase("OpenAI Endpoint", client, model, args.ticks)
        results.append(("OpenAI", stats))

    if args.endpoint in ("anthropic", "both"):
        client = LMStudioAnthropicClient(
            model=model,
            base_url=args.base_url,
            temperature=0.7,
            max_tokens=256,
        )
        stats = run_phase("Anthropic Endpoint", client, model, args.ticks)
        results.append(("Anthropic", stats))

    # Comparison summary
    if len(results) > 1:
        print(f"\n{'='*60}")
        print("  COMPARISON")
        print(f"{'='*60}")
        for name, st in results:
            avg = st.total_latency / st.responses if st.responses > 0 else 0.0
            print(
                f"  {name:12s}: "
                f"{st.queries} queries, "
                f"{st.responses} responses, "
                f"{st.errors} errors, "
                f"avg {avg:.1f}s"
            )
        print(f"{'='*60}\n")

    # Overall pass/fail
    all_ok = all(st.responses > 0 for _, st in results)
    if all_ok:
        print("  SMOKE TEST PASSED")
    else:
        print("  SMOKE TEST FAILED — no responses received on some endpoints")
    print()


if __name__ == "__main__":
    main()
