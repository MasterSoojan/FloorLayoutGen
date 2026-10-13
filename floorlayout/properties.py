"""Shared room/object form rules and furniture coordinate conversion; no GUI."""

from math import isfinite

from .colors import COLOR_MAP


def parse_shape_properties(name, x, y, width, height, color_name):
    """Validate dialog text and return the existing six-field property tuple."""
    name = name.strip()
    if not name:
        raise ValueError("Name is required.")
    try:
        values = tuple(float(value) for value in (x, y, width, height))
    except (TypeError, ValueError):
        raise ValueError("Coordinates and dimensions must be numbers.") from None
    if not all(isfinite(value) for value in values):
        raise ValueError("Coordinates and dimensions must be finite numbers.")
    if values[2] <= 0 or values[3] <= 0:
        raise ValueError("Width and height must be positive.")
    if color_name not in COLOR_MAP:
        raise ValueError("Choose a color from the list.")
    return (name, *values, COLOR_MAP[color_name])


def object_state_from_center(properties):
    """Forms use center coordinates; furniture/history use the lower-left corner."""
    name, x, y, width, height, color = properties
    return (name, x - width / 2, y - height / 2, width, height, color)


def object_state_to_center(state):
    name, x, y, width, height, color = state
    return (name, x + width / 2, y + height / 2, width, height, color)
