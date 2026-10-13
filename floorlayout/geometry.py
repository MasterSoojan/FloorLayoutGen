"""Pure interaction geometry in blueprint coordinates (feet)."""

from math import hypot, isfinite
from shapely.geometry import Polygon, box


def nearest_vertex(polygon, x, y, tolerance=0.5):
    if not isinstance(polygon, Polygon) or polygon.is_empty:
        return None
    distances = [hypot(px - x, py - y) for px, py in polygon.exterior.coords]
    index = min(range(len(distances)), key=distances.__getitem__)
    return index if distances[index] < tolerance else None


def resize_rectangle(polygon, handle, x, y):
    minx, miny, maxx, maxy = polygon.bounds
    if "right" in handle:
        maxx = x
    if "left" in handle:
        minx = x
    if "top" in handle:
        maxy = y
    if "bottom" in handle:
        miny = y
    return box(min(minx, maxx), min(miny, maxy), max(minx, maxx), max(miny, maxy))


def reshape_vertex(polygon, index, x, y):
    """Move an exterior vertex without losing holes; reject invalid previews."""
    if not isinstance(polygon, Polygon) or polygon.is_empty:
        return polygon
    coords = list(polygon.exterior.coords)
    if not 0 <= index < len(coords) or not all(isfinite(v) for v in (x, y)):
        return polygon
    coords[index] = (x, y)
    if index in (0, len(coords) - 1):
        coords[0] = coords[-1] = (x, y)
    # Subtraction can leave courtyards inside a room. Rebuilding from only the
    # exterior would silently fill them in. Keep those rings, and retain the last
    # valid shape if this drag crosses a hole or makes the outline self-intersect;
    # auto-repair could change the user's topology instead of just moving a vertex.
    candidate = Polygon(coords, holes=[list(ring.coords) for ring in polygon.interiors])
    return candidate if candidate.is_valid and candidate.area > 0 else polygon
