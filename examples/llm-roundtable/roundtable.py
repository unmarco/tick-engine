"""LLM Roundtable — Multi-Agent Structured Debate.

A panel discussion where a moderator and three panelists with opposing
viewpoints debate a topic over multiple rounds. Each speaker sees the full
transcript of everything said before them. Positions evolve as agents
reference each other's past arguments, concede points, and shift stance.

Exercises tick-llm's cross-agent context reads, episodic memory, and
turn-based coordination in a conversational format.

Run:
    uv run python roundtable.py --topic "Should AI have persistent memory?"
    uv run python roundtable.py --topic "Is open source AI safer?" --rounds 5
    uv run python roundtable.py --rounds 3 --base-url http://192.168.1.3:5150
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
from dataclasses import dataclass, field
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

DEFAULT_TOPIC = "Should AI systems have persistent memory across conversations?"


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

@dataclass
class Name:
    """Display name for an entity."""
    value: str


@dataclass
class Panelist:
    """Marks an entity as a roundtable participant."""
    speaker_order: int


# ---------------------------------------------------------------------------
# Shared transcript
# ---------------------------------------------------------------------------

transcript: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Turn Manager
# ---------------------------------------------------------------------------

class TurnManager:
    """Enforces strict round-robin turn order across LLM agents.

    Only one agent is eligible to query at any time. The next agent becomes
    eligible only after the previous agent's response is harvested and parsed.
    """

    def __init__(
        self,
        speaker_order: list[int],
        total_rounds: int,
    ) -> None:
        self.order = speaker_order
        self.total_rounds = total_rounds
        self.current_idx = 0
        self.current_round = 1
        self.waiting_for_response = False
        self.finished = False
        self._entity_names: dict[int, str] = {}

    def system(self, world: Any, ctx: Any) -> None:
        """Enforce turn order by managing cooldowns."""
        if self.finished:
            return

        current_eid = self.order[self.current_idx]
        for eid, (agent,) in world.query(LLMAgent):
            if eid == current_eid and not self.waiting_for_response:
                agent.cooldown_until = 0
            else:
                agent.cooldown_until = ctx.tick_number + 100

    def on_query(self, eid: int, prompt_size: int, tick: int) -> None:
        """Mark that we're waiting for a response."""
        self.waiting_for_response = True

    def on_response(self, eid: int, latency: float, resp_size: int, tick: int) -> None:
        """Advance to next speaker after response harvested."""
        self.waiting_for_response = False
        self.current_idx += 1
        if self.current_idx >= len(self.order):
            self.current_idx = 0
            self.current_round += 1
            if self.current_round > self.total_rounds:
                self.finished = True

    def on_error(self, eid: int, error_type: str, error_msg: str, tick: int) -> None:
        """On error, release the current speaker to retry."""
        name = self._entity_names.get(eid, f"eid={eid}")
        print(f"  [T{tick:03d}] ERROR {name}: [{error_type}] {error_msg}")
        self.waiting_for_response = False

    def current_speaker_name(self) -> str:
        """Name of the agent whose turn it is."""
        if self.finished:
            return "(done)"
        eid = self.order[self.current_idx]
        return self._entity_names.get(eid, f"eid={eid}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def roundtable_parser(response: str, bb: Blackboard) -> None:
    """Parse panelist/moderator response and append to shared transcript."""
    cleaned = strip_code_fences(response)
    parsed: Any = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")

    bb.data["strategy"] = parsed

    # Build transcript entry
    role = bb.data.get("_role", "unknown")
    name = bb.data.get("_name", "Unknown")
    tick = bb.data.get("_tick", 0)
    current_round = bb.data.get("_round", 1)

    entry: dict[str, Any] = {
        "round": current_round,
        "speaker": name,
        "role": role,
        "tick": tick,
    }

    if role == "moderator":
        entry["statement"] = parsed.get("statement", "")
        entry["focus"] = parsed.get("focus", "")
        entry["summary"] = parsed.get("summary", "")
    else:
        entry["statement"] = parsed.get("statement", "")
        entry["addressing"] = parsed.get("addressing", "")
        entry["stance"] = parsed.get("stance", "")
        entry["key_point"] = parsed.get("key_point", "")

        # Track stance history on the blackboard
        stance_history: list[dict[str, Any]] = bb.data.setdefault(
            "stance_history", [],
        )
        stance_history.append({
            "round": current_round,
            "stance": parsed.get("stance", ""),
            "key_point": parsed.get("key_point", ""),
        })

    transcript.append(entry)


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def _tick_stamp_system(
    turn_manager: TurnManager,
) -> Any:
    """Create a system that stamps tick/round onto every blackboard."""

    def system(world: Any, ctx: Any) -> None:
        for eid, (bb,) in world.query(Blackboard):
            bb.data["_tick"] = ctx.tick_number
            bb.data["_round"] = turn_manager.current_round

    return system


# ---------------------------------------------------------------------------
# Context functions
# ---------------------------------------------------------------------------

def _format_transcript(entries: list[dict[str, Any]]) -> str:
    """Format transcript entries as a readable discussion log."""
    if not entries:
        return "(No discussion yet — you are opening the debate.)"

    lines: list[str] = []
    current_round = 0

    for entry in entries:
        r = entry["round"]
        if r != current_round:
            current_round = r
            lines.append(f"\n=== ROUND {r} ===")

        speaker = entry["speaker"]
        role = entry.get("role", "")
        statement = entry.get("statement", "")

        if role == "moderator":
            lines.append(f'Moderator: "{statement}"')
        else:
            stance = entry.get("stance", "")
            addressing = entry.get("addressing", "")
            addr_note = f" (to {addressing})" if addressing else ""
            lines.append(f'{speaker}{addr_note}: "{statement}" [stance: {stance}]')

    return "\n".join(lines)


def _analyze_panelist_history(
    stance_history: list[dict[str, Any]],
) -> list[str]:
    """Derive editorial observations from a panelist's stance history."""
    if len(stance_history) < 2:
        return []

    observations: list[str] = []

    # Detect repetitive stances
    recent_stances = [s["stance"] for s in stance_history[-3:]]
    if len(set(recent_stances)) == 1 and len(recent_stances) >= 3:
        observations.append(
            f"You have taken the '{recent_stances[0]}' stance for "
            f"{len(recent_stances)} consecutive rounds. "
            "Consider whether you're adding new substance or repeating yourself."
        )

    # Detect repetitive key points
    recent_points = [s["key_point"] for s in stance_history[-3:]]
    if len(recent_points) >= 2 and recent_points[-1] == recent_points[-2]:
        observations.append(
            "Your last two key points were identical. "
            "Try to advance the argument or respond to others' points."
        )

    return observations


def _moderator_context(world: Any, eid: int) -> str:
    """Build moderator context with full transcript and debate state."""
    parts: list[str] = []

    bb = world.get(eid, Blackboard) if world.has(eid, Blackboard) else None
    current_round = bb.data.get("_round", 1) if bb else 1
    topic = bb.data.get("_topic", DEFAULT_TOPIC) if bb else DEFAULT_TOPIC

    parts.append(f"TOPIC: {topic}")
    parts.append(f"CURRENT ROUND: {current_round}")
    parts.append("")

    # Full transcript
    parts.append("DISCUSSION SO FAR:")
    parts.append(_format_transcript(transcript))

    # Debate state summary for steering
    if transcript:
        stances_by_speaker: dict[str, list[str]] = {}
        for entry in transcript:
            if entry.get("role") != "moderator":
                speaker = entry["speaker"]
                stance = entry.get("stance", "")
                if stance:
                    stances_by_speaker.setdefault(speaker, []).append(stance)

        if stances_by_speaker:
            parts.append("\nDEBATE STATE:")
            for speaker, stances in stances_by_speaker.items():
                parts.append(f"  {speaker}: {' -> '.join(stances)}")

    if current_round == 1 and not transcript:
        parts.append(
            "\nThis is the opening round. Pose the topic as a clear, "
            "provocative question that invites debate."
        )
    else:
        parts.append(
            "\nSteer the discussion toward unexplored angles. "
            "Ask probing follow-up questions based on what has been said. "
            "If panelists are repeating themselves, challenge them to go deeper."
        )

    parts.append(
        "\nRespond ONLY with a JSON object in this exact format:\n"
        '{"statement": "<your question or prompt for this round>", '
        '"focus": "<what aspect to explore next>", '
        '"summary": "<brief recap of where the discussion stands>"}\n'
        "No markdown, no explanation, just the JSON object."
    )
    return "\n".join(parts)


def _panelist_context(world: Any, eid: int) -> str:
    """Build panelist context with full transcript and stance history."""
    parts: list[str] = []

    bb = world.get(eid, Blackboard) if world.has(eid, Blackboard) else None
    current_round = bb.data.get("_round", 1) if bb else 1
    topic = bb.data.get("_topic", DEFAULT_TOPIC) if bb else DEFAULT_TOPIC
    name = bb.data.get("_name", "Panelist") if bb else "Panelist"

    parts.append(f"TOPIC: {topic}")
    parts.append(f"CURRENT ROUND: {current_round}")
    parts.append(f"YOU ARE: {name}")
    parts.append("")

    # Full transcript
    parts.append("DISCUSSION SO FAR:")
    parts.append(_format_transcript(transcript))

    # Own stance history
    if bb:
        stance_history = bb.data.get("stance_history", [])
        if stance_history:
            parts.append(f"\nYOUR STANCE HISTORY:")
            for sh in stance_history:
                parts.append(
                    f"  Round {sh['round']}: [{sh['stance']}] {sh['key_point']}"
                )

            observations = _analyze_panelist_history(stance_history)
            if observations:
                parts.append("\nEDITORIAL NOTES:")
                for obs in observations:
                    parts.append(f"  * {obs}")

    parts.append(
        "\nEngage with what others have said. Reference specific speakers by name. "
        "Your position can evolve — you may concede points, double down, or shift. "
        "Respond ONLY with a JSON object in this exact format:\n"
        '{"statement": "<your contribution to the discussion>", '
        '"addressing": "<name of speaker you are primarily responding to>", '
        '"stance": "<agree|disagree|nuance|question|propose>", '
        '"key_point": "<one-sentence summary of your position>"}\n'
        "No markdown, no explanation, just the JSON object."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _print_entry(entry: dict[str, Any]) -> None:
    """Print a single transcript entry in a readable format."""
    speaker = entry["speaker"]
    role = entry.get("role", "")
    statement = entry.get("statement", "")
    r = entry["round"]

    if role == "moderator":
        focus = entry.get("focus", "")
        print(f"\n  [{speaker} | Round {r}]")
        print(f"  {statement}")
        if focus:
            print(f"  (Focus: {focus})")
    else:
        stance = entry.get("stance", "")
        addressing = entry.get("addressing", "")
        key_point = entry.get("key_point", "")
        addr = f" -> {addressing}" if addressing else ""
        print(f"\n  [{speaker}{addr} | Round {r} | {stance}]")
        print(f"  {statement}")
        if key_point:
            print(f"  >> {key_point}")


def _print_full_transcript(topic: str) -> None:
    """Print the complete formatted transcript."""
    print(f"\n{'='*70}")
    print("  COMPLETE ROUNDTABLE TRANSCRIPT")
    print(f"  Topic: {topic}")
    print(f"{'='*70}")

    current_round = 0
    for entry in transcript:
        r = entry["round"]
        if r != current_round:
            current_round = r
            print(f"\n{'─'*70}")
            print(f"  ROUND {r}")
            print(f"{'─'*70}")
        _print_entry(entry)

    print(f"\n{'='*70}")


def _print_stance_evolution(world: Any, entity_names: dict[int, str]) -> None:
    """Print how each panelist's stance evolved across rounds."""
    print(f"\n{'='*70}")
    print("  STANCE EVOLUTION")
    print(f"{'='*70}")

    for eid, (bb,) in world.query(Blackboard):
        name = entity_names.get(eid, f"eid={eid}")
        role = bb.data.get("_role", "")
        if role == "moderator":
            continue

        stance_history = bb.data.get("stance_history", [])
        if not stance_history:
            continue

        print(f"\n  {name}:")
        for sh in stance_history:
            print(f"    Round {sh['round']}: [{sh['stance']:>10s}] {sh['key_point']}")

    print(f"\n{'='*70}")


# ---------------------------------------------------------------------------
# Connectivity
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
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM Roundtable — Multi-Agent Structured Debate",
    )
    parser.add_argument(
        "--topic", default=DEFAULT_TOPIC,
        help=f"Discussion topic (default: '{DEFAULT_TOPIC}')",
    )
    parser.add_argument(
        "--rounds", type=int, default=4,
        help="Number of full rounds (default: 4)",
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
        "--endpoint", choices=["openai", "anthropic"],
        default="anthropic",
        help="Which endpoint format to use (default: anthropic)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  LLM ROUNDTABLE — Multi-Agent Structured Debate")
    print("=" * 70)
    print(f"  Topic:  {args.topic}")
    print(f"  Rounds: {args.rounds}")

    # Connectivity
    print(f"\n  Checking LM Studio at {args.base_url}...")
    models = _check_connectivity(args.base_url)
    model = _resolve_model(models, args.model)
    print(f"  Model:    {model}")
    print(f"  Endpoint: {args.endpoint}")

    # Client
    if args.endpoint == "openai":
        client = LMStudioOpenAIClient(
            model=model,
            base_url=args.base_url,
            temperature=0.8,
            max_tokens=512,
        )
    else:
        client = LMStudioAnthropicClient(
            model=model,
            base_url=args.base_url,
            temperature=0.8,
            max_tokens=512,
        )

    # Engine setup
    engine = Engine(tps=10, seed=42)
    world = engine.world

    world.register_component(Name)
    world.register_component(Panelist)
    world.register_component(LLMAgent)
    world.register_component(Blackboard)

    config = LLMConfig(
        max_queries_per_tick=1,
        max_queries_per_second=2,
        thread_pool_size=1,
        query_timeout=120.0,
    )
    manager = LLMManager(config)

    # --- Roles ---
    manager.define_role("moderator", (
        "You are the moderator of a structured roundtable discussion. "
        "Your job is to pose thought-provoking questions, steer the debate "
        "toward unexplored angles, and summarize the state of the discussion. "
        "You are neutral — you do not take sides. "
        "Ask probing follow-up questions that push panelists beyond surface-level arguments. "
        "If panelists are repeating themselves, redirect the conversation. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"statement": "<your question or prompt>", '
        '"focus": "<what aspect to explore next>", '
        '"summary": "<brief recap of the discussion so far>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))

    manager.define_role("advocate", (
        "You are a panelist in a structured debate. You argue the POSITIVE side "
        "of the topic — you believe in progress, opportunity, and the benefits "
        "of the idea being discussed. You push for forward-thinking solutions. "
        "However, you are intellectually honest: if another panelist makes a "
        "strong point, acknowledge it before countering. Your arguments should "
        "evolve over rounds — don't repeat the same points. "
        "Reference other speakers BY NAME when responding to their arguments. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"statement": "<your contribution>", '
        '"addressing": "<name of speaker you respond to>", '
        '"stance": "<agree|disagree|nuance|question|propose>", '
        '"key_point": "<one-sentence summary>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))

    manager.define_role("critic", (
        "You are a panelist in a structured debate. You are the SKEPTIC — "
        "you question assumptions, raise concerns, identify risks, and play "
        "devil's advocate. You challenge both the Advocate's optimism and the "
        "Synthesizer's compromises. You demand evidence and point out blind spots. "
        "However, you are fair: if someone addresses your concern well, "
        "concede the point and raise a NEW concern. Don't repeat yourself. "
        "Reference other speakers BY NAME when responding to their arguments. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"statement": "<your contribution>", '
        '"addressing": "<name of speaker you respond to>", '
        '"stance": "<agree|disagree|nuance|question|propose>", '
        '"key_point": "<one-sentence summary>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))

    manager.define_role("synthesizer", (
        "You are a panelist in a structured debate. You are the PRAGMATIST — "
        "you bridge opposing viewpoints, find middle ground, and propose "
        "concrete solutions that address both the Advocate's ambitions and the "
        "Critic's concerns. You look for frameworks and tradeoffs rather than "
        "binary positions. You draw on what both sides have said to build "
        "something new. Reference other speakers BY NAME. "
        "Your proposals should become more specific and actionable over rounds. "
        "You MUST respond with ONLY a valid JSON object in this exact format:\n"
        '{"statement": "<your contribution>", '
        '"addressing": "<name of speaker you respond to>", '
        '"stance": "<agree|disagree|nuance|question|propose>", '
        '"key_point": "<one-sentence summary>"}\n'
        "No markdown, no explanation, just the JSON object."
    ))

    # --- Personalities ---
    manager.define_personality("neutral", (
        "You are balanced and objective. You ask Socratic questions and "
        "ensure all voices are heard. You notice when the discussion stalls "
        "and redirect it productively."
    ))
    manager.define_personality("optimistic", (
        "You see potential and opportunity. You are enthusiastic but not naive — "
        "you back your optimism with reasoning. When challenged, you refine "
        "your position rather than simply repeating it."
    ))
    manager.define_personality("skeptical", (
        "You are analytically rigorous. You probe for weaknesses and "
        "unintended consequences. You respect strong arguments even when "
        "they counter your position."
    ))
    manager.define_personality("pragmatic", (
        "You are solution-oriented. You value workable compromises over "
        "ideological purity. You synthesize opposing views into actionable "
        "proposals and look for win-win scenarios."
    ))

    # --- Contexts ---
    manager.define_context("moderator_ctx", _moderator_context)
    manager.define_context("panelist_ctx", _panelist_context)

    # --- Parser ---
    manager.define_parser("roundtable", roundtable_parser)

    # --- Client ---
    manager.register_client(client)

    # --- Turn Manager ---
    # Speaker order: Moderator -> Advocate -> Critic -> Synthesizer
    # We'll create entities and set up the order after spawning

    entity_names: dict[int, str] = {}

    # Spawn entities
    moderator_eid = world.spawn()
    world.attach(moderator_eid, Name(value="Moderator"))
    world.attach(moderator_eid, Panelist(speaker_order=0))
    world.attach(moderator_eid, Blackboard(data={
        "_role": "moderator", "_name": "Moderator", "_topic": args.topic,
    }))
    world.attach(moderator_eid, LLMAgent(
        role="moderator",
        personality="neutral",
        context="moderator_ctx",
        parser="roundtable",
        query_interval=0,
        priority=10,
        max_retries=3,
        cooldown_ticks=0,
    ))
    entity_names[moderator_eid] = "Moderator"

    advocate_eid = world.spawn()
    world.attach(advocate_eid, Name(value="Advocate"))
    world.attach(advocate_eid, Panelist(speaker_order=1))
    world.attach(advocate_eid, Blackboard(data={
        "_role": "advocate", "_name": "Advocate", "_topic": args.topic,
    }))
    world.attach(advocate_eid, LLMAgent(
        role="advocate",
        personality="optimistic",
        context="panelist_ctx",
        parser="roundtable",
        query_interval=0,
        priority=5,
        max_retries=3,
        cooldown_ticks=0,
    ))
    entity_names[advocate_eid] = "Advocate"

    critic_eid = world.spawn()
    world.attach(critic_eid, Name(value="Critic"))
    world.attach(critic_eid, Panelist(speaker_order=2))
    world.attach(critic_eid, Blackboard(data={
        "_role": "critic", "_name": "Critic", "_topic": args.topic,
    }))
    world.attach(critic_eid, LLMAgent(
        role="critic",
        personality="skeptical",
        context="panelist_ctx",
        parser="roundtable",
        query_interval=0,
        priority=5,
        max_retries=3,
        cooldown_ticks=0,
    ))
    entity_names[critic_eid] = "Critic"

    synthesizer_eid = world.spawn()
    world.attach(synthesizer_eid, Name(value="Synthesizer"))
    world.attach(synthesizer_eid, Panelist(speaker_order=3))
    world.attach(synthesizer_eid, Blackboard(data={
        "_role": "synthesizer", "_name": "Synthesizer", "_topic": args.topic,
    }))
    world.attach(synthesizer_eid, LLMAgent(
        role="synthesizer",
        personality="pragmatic",
        context="panelist_ctx",
        parser="roundtable",
        query_interval=0,
        priority=5,
        max_retries=3,
        cooldown_ticks=0,
    ))
    entity_names[synthesizer_eid] = "Synthesizer"

    speaker_order = [moderator_eid, advocate_eid, critic_eid, synthesizer_eid]
    turn_manager = TurnManager(speaker_order, args.rounds)
    turn_manager._entity_names = entity_names

    # Bind callbacks
    manager.on_query(turn_manager.on_query)
    manager.on_response(turn_manager.on_response)
    manager.on_error(turn_manager.on_error)

    # --- Systems ---
    engine.add_system(turn_manager.system)
    engine.add_system(_tick_stamp_system(turn_manager))
    llm_system = make_llm_system(manager)
    engine.add_system(llm_system)

    # --- Run ---
    print(f"\n{'='*70}")
    print("  DEBATE BEGINS")
    print(f"{'='*70}\n")

    last_transcript_len = 0

    while not turn_manager.finished:
        engine.step()
        time.sleep(0.5)

        # Print new transcript entries as they arrive
        if len(transcript) > last_transcript_len:
            for entry in transcript[last_transcript_len:]:
                _print_entry(entry)
            last_transcript_len = len(transcript)

    # Drain any final pending responses
    for _ in range(20):
        engine.step()
        time.sleep(0.2)
        if len(transcript) > last_transcript_len:
            for entry in transcript[last_transcript_len:]:
                _print_entry(entry)
            last_transcript_len = len(transcript)

    llm_system.shutdown()

    # --- Final output ---
    _print_full_transcript(args.topic)
    _print_stance_evolution(world, entity_names)

    total_responses = len(transcript)
    expected = args.rounds * len(speaker_order)
    print(f"\n  Responses: {total_responses}/{expected} expected")
    if total_responses == expected:
        print("  ROUNDTABLE COMPLETE")
    else:
        print("  ROUNDTABLE PARTIAL — some responses may have timed out")
    print()


if __name__ == "__main__":
    main()
