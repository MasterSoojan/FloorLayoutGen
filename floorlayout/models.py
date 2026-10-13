"""Geometry models; importing this module never starts a GUI."""

from shapely.geometry import Polygon, box, Point
from shapely.affinity import translate
from shapely.wkt import loads as wkt_loads
from .colors import DEFAULT_ROOM_COLOR, DEFAULT_FURNITURE_COLOR


class Room:
    """Represents a room as a polygon, with a specific color."""

    def __init__(self, name, geometry, color=DEFAULT_ROOM_COLOR):
        self.name = name
        self.polygon = geometry
        self.color = color

    @classmethod
    def from_box(cls, name, x, y, width, height, color=DEFAULT_ROOM_COLOR):
        return cls(name, box(x, y, x + width, y + height), color)

    @property
    def area(self):
        return self.polygon.area

    @property
    def bounds(self):
        return self.polygon.bounds

    @property
    def is_rectangular(self):
        return isinstance(self.polygon, Polygon) and self.polygon.equals(
            box(*self.polygon.bounds)
        )

    def get_state(self):
        return (self.name, self.polygon.wkt, self.color)

    def update_state(self, state):
        self.name, wkt, self.color = state
        self.polygon = wkt_loads(wkt)

    def contains(self, px, py):
        return self.polygon.contains(Point(px, py))

    def translate(self, dx, dy):
        self.polygon = translate(self.polygon, xoff=dx, yoff=dy)

    def get_resize_handle(self, px, py, tolerance=5):
        if not self.is_rectangular:
            return None
        minx, miny, maxx, maxy = self.bounds
        on_l, on_r = abs(px - minx) < tolerance, abs(px - maxx) < tolerance
        on_b, on_t = abs(py - miny) < tolerance, abs(py - maxy) < tolerance
        if on_t and on_l:
            return "top-left"
        if on_t and on_r:
            return "top-right"
        if on_b and on_l:
            return "bottom-left"
        if on_b and on_r:
            return "bottom-right"
        if on_t:
            return "top"
        if on_b:
            return "bottom"
        if on_l:
            return "left"
        if on_r:
            return "right"
        return None


# --- Data Class for a Blueprint Object (e.g., furniture) ---
class BlueprintObject:
    def __init__(self, name, x, y, width, height, color=DEFAULT_FURNITURE_COLOR):
        self.update_state((name, x, y, width, height, color))

    def get_state(self):
        return (self.name, self.x, self.y, self.width, self.height, self.color)

    def update_state(self, state_tuple):
        self.name, self.x, self.y, self.width, self.height, self.color = state_tuple

    def contains(self, px, py):
        return (
            self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height
        )

    def translate(self, dx, dy):
        self.x += dx
        self.y += dy
