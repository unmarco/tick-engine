"""Components for the placement playground."""
from dataclasses import dataclass


@dataclass
class Structure:
    """Marks an entity as a placed structure."""
    name: str
