"""The editor's existing four-room sample generator, not a design validator."""

import random

from .models import Room


def generate_rooms(rng=random):
    """Build detached rooms; callers decide whether to replace their document.

    Preserve the original ranges and random-draw order. Accepting a Random
    instance makes the layout reproducible in tests without changing global RNG
    state or introducing a different floor-planning algorithm.
    """
    living_width, living_height = rng.uniform(15, 22), rng.uniform(12, 18)
    living = Room.from_box("Living Room", 0, 0, living_width, living_height)
    kitchen_width, kitchen_height = rng.uniform(8, 14), rng.uniform(8, 14)
    kitchen = Room.from_box(
        "Kitchen",
        living_width,
        rng.uniform(0, living_height - kitchen_height),
        kitchen_width,
        kitchen_height,
    )
    bedroom_width, bedroom_height = rng.uniform(12, 18), rng.uniform(10, 15)
    bedroom = Room.from_box(
        "Master Bedroom",
        rng.uniform(0, living_width - bedroom_width),
        living_height,
        bedroom_width,
        bedroom_height,
    )
    bathroom_width, bathroom_height = rng.uniform(6, 9), rng.uniform(6, 9)
    bathroom = Room.from_box(
        "Bathroom",
        living_width,
        kitchen.bounds[3],
        bathroom_width,
        bathroom_height,
    )
    return [living, kitchen, bedroom, bathroom]
