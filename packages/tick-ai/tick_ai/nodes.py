"""BT node types and status enum."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    """Result of evaluating a BT node."""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


# --- Leaf nodes ---


@dataclass(frozen=True)
class Action:
    """Leaf: calls a registered action callback -> Status."""

    id: str
    action: str


@dataclass(frozen=True)
class Condition:
    """Leaf: calls a registered guard -> SUCCESS or FAILURE."""

    id: str
    condition: str


# --- Composite nodes ---


@dataclass(frozen=True)
class Sequence:
    """All children must succeed; fails on first failure."""

    id: str
    children: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Selector:
    """First child that succeeds wins; fallback chain."""

    id: str
    children: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Parallel:
    """Runs all children every tick. Policy: 'require_all' or 'require_one'."""

    id: str
    children: tuple[str, ...] = field(default_factory=tuple)
    policy: str = "require_all"


@dataclass(frozen=True)
class UtilitySelector:
    """Scores children via utility system, runs highest-scoring."""

    id: str
    children: tuple[str, ...] = field(default_factory=tuple)


# --- Decorator nodes ---


@dataclass(frozen=True)
class Inverter:
    """Flips SUCCESS <-> FAILURE. RUNNING passes through."""

    id: str
    child: str = ""


@dataclass(frozen=True)
class Repeater:
    """Repeats child up to max_count times.

    fail_policy: 'restart' (keep going on FAILURE) or 'fail' (propagate FAILURE).
    """

    id: str
    child: str = ""
    max_count: int = 1
    fail_policy: str = "fail"


@dataclass(frozen=True)
class Succeeder:
    """Always returns SUCCESS (unless child is RUNNING)."""

    id: str
    child: str = ""


@dataclass(frozen=True)
class AlwaysFail:
    """Always returns FAILURE (unless child is RUNNING)."""

    id: str
    child: str = ""


Node = (
    Action
    | Condition
    | Sequence
    | Selector
    | Parallel
    | UtilitySelector
    | Inverter
    | Repeater
    | Succeeder
    | AlwaysFail
)
